# Core Reproduction v1 protocol

The paper is redacted only where it would reveal outcomes. Forecast from the retained methods and experimental setup, not from unavailable result artifacts.

The phase-two study retains the paper's nine-cell 3x3 analysis structure:
low, mid, and high crossed with binary, ordinal, and bounded-continuous
scores. In this independent MMLU study, `low`/`mid`/`high` are
pre-registered challenge strata, not pre-collection claims about observed
model performance. The final analysis must report whether the collected
outcomes support the intended ordering. It uses a current-model trace
collection, fixed item IDs, four epochs per item, and no network access during
the HUD rollout.

The first Core v1 inputs are drawn from public MMLU material. Treat possible
benchmark contamination as a required limitation: this task measures the
stopping analysis on a controlled score matrix, not a contamination-free
frontier-capability estimate.

Forecasts must state probabilities for binary claims and calibrated distributions for numerical claims. The later result may support replication, be undecided, or not support a claim; do not treat non-replication as a task failure.
