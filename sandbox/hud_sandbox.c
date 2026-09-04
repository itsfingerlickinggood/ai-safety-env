#define _GNU_SOURCE

#include <errno.h>
#include <grp.h>
#include <libgen.h>
#include <linux/sched.h>
#include <seccomp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <unistd.h>

static int deny_syscall(scmp_filter_ctx ctx, int syscall_number) {
    if (syscall_number == __NR_SCMP_ERROR) {
        return 0;
    }
    return seccomp_rule_add(ctx, SCMP_ACT_ERRNO(EPERM), syscall_number, 0);
}

static void install_filter(void) {
    scmp_filter_ctx ctx;
    int blocked[] = {
        SCMP_SYS(socket), SCMP_SYS(socketpair), SCMP_SYS(connect),
        SCMP_SYS(bind), SCMP_SYS(listen), SCMP_SYS(accept),
        SCMP_SYS(accept4), SCMP_SYS(sendto), SCMP_SYS(recvfrom),
        SCMP_SYS(sendmsg), SCMP_SYS(recvmsg), SCMP_SYS(ptrace),
        SCMP_SYS(process_vm_readv), SCMP_SYS(process_vm_writev),
        SCMP_SYS(mount), SCMP_SYS(umount2), SCMP_SYS(pivot_root),
        SCMP_SYS(setns), SCMP_SYS(unshare), SCMP_SYS(setsid),
        SCMP_SYS(setpgid), SCMP_SYS(bpf),
        SCMP_SYS(keyctl), SCMP_SYS(perf_event_open), SCMP_SYS(kexec_load),
        SCMP_SYS(kexec_file_load), SCMP_SYS(pidfd_getfd),
        SCMP_SYS(io_uring_setup), SCMP_SYS(io_uring_enter),
        SCMP_SYS(io_uring_register), SCMP_SYS(userfaultfd),
        SCMP_SYS(open_by_handle_at), SCMP_SYS(name_to_handle_at)
    };
    unsigned long namespace_flags[] = {
        CLONE_NEWCGROUP, CLONE_NEWIPC, CLONE_NEWNET, CLONE_NEWNS,
        CLONE_NEWPID, CLONE_NEWTIME, CLONE_NEWUSER, CLONE_NEWUTS
    };
    size_t i;

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        perror("sandbox: PR_SET_NO_NEW_PRIVS");
        exit(126);
    }
    ctx = seccomp_init(SCMP_ACT_ALLOW);
    if (ctx == NULL) {
        fputs("sandbox: seccomp_init failed\n", stderr);
        exit(126);
    }
    for (i = 0; i < sizeof(blocked) / sizeof(blocked[0]); ++i) {
        if (deny_syscall(ctx, blocked[i]) < 0) {
            fputs("sandbox: seccomp rule failed\n", stderr);
            seccomp_release(ctx);
            exit(126);
        }
    }
    /* Make libc fall back to clone(2) for ordinary threads, while rejecting
       every clone(2) request that asks for a new namespace. */
    if (seccomp_rule_add(ctx, SCMP_ACT_ERRNO(ENOSYS), SCMP_SYS(clone3), 0) < 0) {
        fputs("sandbox: clone3 seccomp rule failed\n", stderr);
        seccomp_release(ctx);
        exit(126);
    }
    for (i = 0; i < sizeof(namespace_flags) / sizeof(namespace_flags[0]); ++i) {
        if (seccomp_rule_add(
                ctx,
                SCMP_ACT_ERRNO(EPERM),
                SCMP_SYS(clone),
                1,
                SCMP_A0(SCMP_CMP_MASKED_EQ, namespace_flags[i], namespace_flags[i])) < 0) {
            fputs("sandbox: clone namespace rule failed\n", stderr);
            seccomp_release(ctx);
            exit(126);
        }
    }
    if (seccomp_load(ctx) < 0) {
        perror("sandbox: seccomp_load");
        seccomp_release(ctx);
        exit(126);
    }
    seccomp_release(ctx);
}

static void set_limits(void) {
    struct rlimit cpu = {300, 300};
    struct rlimit address_space = {2147483648ULL, 2147483648ULL};
    struct rlimit files = {128, 128};
    struct rlimit processes = {256, 256};
    struct rlimit file_size = {33554432, 33554432};
    (void)setrlimit(RLIMIT_CPU, &cpu);
    (void)setrlimit(RLIMIT_AS, &address_space);
    (void)setrlimit(RLIMIT_NOFILE, &files);
    (void)setrlimit(RLIMIT_NPROC, &processes);
    (void)setrlimit(RLIMIT_FSIZE, &file_size);
}

static int shell_mode(char *argv[]) {
    set_limits();
    install_filter();
    argv[0] = (char *)"bash";
    execv("/bin/bash", argv);
    perror("sandbox: exec /bin/bash");
    return 126;
}

static int grader_mode(int argc, char *argv[]) {
    uid_t uid;
    gid_t gid;
    char *end = NULL;

    if (argc < 6 || strcmp(argv[1], "--uid") != 0 || strcmp(argv[3], "--gid") != 0) {
        fputs("usage: hud-sandbox-exec --uid UID --gid GID COMMAND [ARG ...]\n", stderr);
        return 125;
    }
    uid = (uid_t)strtoul(argv[2], &end, 10);
    if (end == argv[2] || *end != '\0') {
        fputs("sandbox: invalid uid\n", stderr);
        return 125;
    }
    gid = (gid_t)strtoul(argv[4], &end, 10);
    if (end == argv[4] || *end != '\0') {
        fputs("sandbox: invalid gid\n", stderr);
        return 125;
    }
    set_limits();
    if (setgroups(0, NULL) != 0 || setgid(gid) != 0 || setuid(uid) != 0) {
        perror("sandbox: privilege drop");
        return 126;
    }
    if (clearenv() != 0 || setenv("PATH", "/usr/local/bin:/usr/bin:/bin", 1) != 0 ||
        setenv("HOME", "/tmp", 1) != 0 || setenv("TMPDIR", "/tmp", 1) != 0 ||
        setenv("PYTHONDONTWRITEBYTECODE", "1", 1) != 0) {
        perror("sandbox: environment");
        return 126;
    }
    install_filter();
    execv(argv[5], &argv[5]);
    perror("sandbox: exec grader command");
    return 126;
}

int main(int argc, char *argv[]) {
    char *program = basename(argv[0]);
    if (strcmp(program, "bash") == 0) {
        return shell_mode(argv);
    }
    return grader_mode(argc, argv);
}
