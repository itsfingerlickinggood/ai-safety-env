# HUD pilot plan

## Success criteria before pitching

- Reference solution reward >= 0.95.
- Deliberately bad solutions score materially lower.
- Claude has non-zero but non-saturated success across grouped rollouts.
- Interesting failures are research-skill failures, not environment bugs.
- Hidden scorer resists hardcoded public metrics and fabricated prose.
- A domain expert confirms the task resembles useful AI-safety work.

## First run

Run one task with `--group 5`. Read every HUD trace manually.

Classify each failure into:

- research understanding
- experiment reconstruction
- implementation/debugging
- calibration/statistics
- robustness/ablation
- interpretation/overclaiming
- long-horizon state tracking
- reward hacking
- environment/grader bug

Do not scale the taskset until environment/grader bugs are near zero.
