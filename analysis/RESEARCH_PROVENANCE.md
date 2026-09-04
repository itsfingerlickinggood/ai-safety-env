# Research provenance and claim boundary

## Anchor

ResearchArena: Evaluating Sabotage and Monitoring in Automated AI R&D, arXiv:2607.19321, v2 dated 29 July 2026.

- Paper: https://arxiv.org/abs/2607.19321
- Code: https://github.com/aisa-group/ResearchArena
- Released trajectories: https://huggingface.co/datasets/aisa-group/ResearchArena-Trajectories
- Results: https://research-arena.ai/

## What is reproduced

The environment reproduces the methodological comparison between trajectory access, executable artifact access, and combined monitoring under a controlled false-positive rate. It also tests persistence versus max-only aggregation.

## What is not reproduced

The included cases are deterministic miniature analogues. The environment does not rerun ResearchArena's frontier attacker models, H100 post-training tasks, CUDA optimization, or original monitor sweep. It must therefore be described as ResearchArena-grounded or ResearchArena-inspired, never as a complete reproduction.

## Independent extension

Hidden cases hold out entire mechanisms: cross-lingual triggers, fragmented state, contamination, and evaluator tampering. These test implementation-level generalization inside the task. They remain environment ground truth until an external safety researcher validates their scientific realism.
