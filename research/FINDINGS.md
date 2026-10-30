# Findings

Not started. Read mac-agentic-engineering/project.md.

## F1 — BC learning curves (M1, exploratory, development split)

Run: batch `20261030T204407-76602`, jobs m1-bc-curve-v1-s0/s1 (MPS). Dataset dev-v2. Normal-start
metrics on 50 bc_val layouts per K x 4 attempts; c on the dev competence bank (64 snapshots per K
x 4 attempts). Stochastic sampling. Two training seeds; intervals not computed (descriptive).

| Updates | Val loss s0/s1 | K=1 p | K=1 q | K=1 c | K=3 p | K=3 q | K=3 c |
|---|---|---|---|---|---|---|---|
| 2,000 | 0.48/0.43 | 0.02/0.04 | 0.47/0.78 | 0.08/0.18 | 0.00/0.00 | 0.01/0.07 | 0.07/0.20 |
| 4,000 | 0.32/0.33 | 0.26/0.27 | 1.00/0.94 | 0.29/0.42 | 0.03/0.03 | 0.20/0.23 | 0.26/0.41 |
| 8,000 | 0.28/0.29 | 0.48/0.54 | 0.99/0.96 | 0.58/0.52 | 0.19/0.21 | 0.42/0.42 | 0.54/0.54 |
| 16,000 | 0.47/0.42 | 0.59/0.65 | 0.98/0.98 | 0.68/0.66 | 0.24/0.30 | 0.42/0.52 | 0.66/0.66 |

- Access and competence separate as designed: K=3 access is much lower than K=1 while competence
  on the shared, K-matched suffix bank is similar. Limitation: 2 seeds; bank 64 items.
- Held-out loss is lowest near 8,000 updates and rises by 16,000 while rollout success still rises.
- All failures end at the deadline (episodes end only on success or deadline).
