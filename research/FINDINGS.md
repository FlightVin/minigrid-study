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

## F2 — M2 canary probe collapsed from an optimization defect (exploratory, development)

Run: batch `20261030T205335-81100`, job m2-canary-probe-K1-u4000-s0 (MPS). K=1, early BC (u4000,
seed 0), config `experiments/m2/ppo-canary-v1.json` (actor/critic lr 3e-4, entropy 0.01, advantage
normalization, critic pre-fit 1,000 steps without early stopping). Evaluation: dev_eval 32 layouts
x 4 attempts; dev bank 64 x 2 attempts.

| | p | q | c (entry/retrieval/carrying) |
|---|---|---|---|
| pi0 | 0.25 | 1.00 | 0.27 (0.16/0.25/0.50) |
| after 50,176-action probe | 0.00 | 0.05 | 0.00 (0/0/0) |

- 0 successes in 428 probe episodes, although pi0 episodes succeeded ~25% of the time.
- First update: approx-KL 0.35, clip fraction 0.23, ratio range 0.00-13.6, actor grad norm 9.5.
  Entropy rose from 0.24 to ~1.3 and stayed there.
- Critic pre-fit was worse than a constant on held-out episodes (MSE 0.179 vs 0.108) and miscalibrated
  (carrying states: predicted 0.31, actual 0.10).
- Interpretation: large actor updates on normalized critic noise (most batches have no reward) plus an
  entropy bonus destroyed the BC policy. This is an optimization failure. It is **not** evidence of
  forgetting caused by missing stage practice, and the Delta-c of -0.27 is not a scientific result.
  Next: prespecified stability screen (DECISIONS 2026-10-30).

## F3 — Ordinary-PPO stability screen (M2, exploratory, development, seed 0)

Batch `20261030T205703-85741` (12/12 exited). Source table: `reports/m2_ppo_screen.csv`.
Probe 50k actions; dev_eval 32 layouts x 4 attempts; dev bank 64 x 2 attempts.
pi0: K=1 early p 0.25, q 1.00, c 0.27; K=3 extended p 0.25, q 0.45, c 0.64.

| Variant | K=1 early p/q/c after probe | K=3 extended p/q/c after probe | Probe successes (K1, K3) |
|---|---|---|---|
| S1 lr 3e-4, ent 0.01 | 0.00/0.08/0.04 | 0.00/0.00/0.00 | 6/431, 2/345 |
| S2 lr 1e-4, ent 0.01 | 0.00/0.03/0.02 | 0.00/0.03/0.10 | 4/431, 22/352 |
| S3 lr 1e-4, ent 0 | 0.00/0.00/0.00 | 0.00/0.00/0.11 | 9/432, 5/345 |
| S4 lr 3e-5, ent 0 | 0.22/0.94/0.28 | 0.17/0.43/0.55 | 79/464, 68/371 |
| S5 lr 1e-4, ent 0, target-KL 0.02 | 0.00/0.02/0.05 | 0.02/0.03/0.23 | 21/438, 15/350 |
| S6 lr 3e-4, ent 0, target-KL 0.02 | 0.00/0.00/0.03 | 0.00/0.00/0.00 | 2/429, 3/345 |

- Only the smallest actor step size (S4) avoids collapse. By the prespecified rule S4 is selected
  (mean post-probe p 0.195 vs <= 0.008). S4 does not improve p within 50k actions.
- With early-stopped pre-fit, the critic is only slightly better than a constant (held-out MSE 0.104 vs
  0.108 for K=1; 0.151 vs 0.156 for K=3): sparse binary returns from ~160 episodes carry little signal.
- Before any update, recomputed log-probabilities equal the rollout values (ratio 1 +/- 2e-5, CPU and
  MPS), so the collapse is optimization dynamics, not a ratio bug.
- Limitations: one seed, one 50k probe, 128 normal-start attempts per estimate (SE ~0.04 near p = 0.2).
