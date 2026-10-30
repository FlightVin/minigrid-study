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

## F4 — Four-arm continuation canary (M2, exploratory, development, ONE seed)

Batch `20261030T211303-98764`; fork from the S4 probe (K=3, extended BC u16000, seed 0; fork hash
de2f397a...). 250,368 continuation actions per arm. Final evaluation: 32 dev_eval layouts x 16 attempts;
dev bank 64 x 4 attempts. pi0: p 0.25, q 0.45, c 0.64; post-probe: p 0.17, q 0.43, c 0.55.

| Arm | P1 | q | c | C4 | R4 | Success given arrival | Training successes / episodes |
|---|---|---|---|---|---|---|---|
| 00 | 0.21 | 0.52 | 0.50 | 0.42 | 0.06 | 0.40 | 414 / 2,238 |
| 10 | 0.24 | 0.60 | 0.59 | 0.36 | 0.14 | 0.40 | 1,278 / 3,147 (881 assisted) |
| 01 | 0.41 | 0.71 | 0.70 | 0.63 | 0.20 | 0.58 | 735 / 2,390 |
| 11 | 0.41 | 0.70 | 0.62 | 0.69 | 0.17 | 0.59 | 1,577 / 3,336 (1,042 assisted) |

- Engineering checks passed: finite updates; fork hashes verified in every arm; exact action allowance;
  throughput ~1,100/s (arms 00/10) and ~1,030/s (KL arms), flat over ~17 min of continuous MPS work.
- Ordinary PPO did not clearly improve over 250k actions (curve p 0.20, 0.14, 0.20, 0.23, 0.25; 64
  attempts per point) and drifted from pi0 (anchor KL 0.20 -> 0.30). KL arms stayed near pi0 (~0.03).
- One seed, one condition: no intervention claim. Competing explanation to test first: the 4 x 128
  rollout batch (~4 episodes per update) may make ordinary PPO noise-limited, so preservation may only
  stabilize a poorly configured baseline. Next: rollout-size check on arm 00 only.
- Audit (F4): arm 01 metrics recomputed independently from `attempts_final.jsonl` (32 layouts x 16
  attempts; 64 bank items x 4): P1 0.4102, C4 0.6337, R4 0.2026, c 0.6992, identical to the summary.
  All successes crossed the boundary; every failure is a deadline timeout. Source tables:
  `reports/m2_canary_branches.csv`, `reports/m2_canary_contrasts.csv`.

## F5 — Rollout-size check: ordinary PPO learns with 16-environment batches (M2b, development, seed 0)

Batch `20261030T213118-9288` (10/10 exited); arm 00 only. Tables: `reports/m2b_rollout_arm00.csv`,
`reports/m2b_rollout_probes.csv`. Final: dev_eval 32 x 16 attempts. pi0 p = 0.25 in both conditions.

| Setting | K=1 early: probe p -> final P1 (curve) | K=3 extended: probe p -> final P1 | Mean final P1 |
|---|---|---|---|
| R1 4 envs, lr 3e-5 | 0.00 -> 0.00 (collapsed) | 0.17 -> 0.21 (F4 arm 00) | 0.10 |
| R2 16 envs, mb 512, lr 3e-5 | 0.27 -> 0.44 (0.20, 0.33, 0.36, 0.39, 0.48) | 0.34 -> 0.37 | 0.41 |
| R3 16 envs, mb 512, lr 1e-4 | 0.30 -> 0.36 | 0.02 -> 0.25 | 0.30 |

- With 2,048-action batches and small actor steps, ordinary PPO improves from p = 0.25 (K=1: 0.44;
  K=3: 0.37). The F4 canary baseline was therefore weakened by its small rollout batch; F4's apparent
  preservation advantage must not be carried forward.
- MPS nondeterminism: R1 and S4 K=1 probes had identical settings and seeds (pi0 evaluation identical;
  critic MSE equal to 4 decimals) but ended at p 0.00 vs 0.22. Runs are not bitwise reproducible on MPS;
  unstable settings amplify the difference. Replication must rely on independent seeds.
- R2 also trains ~2.3x faster (~2,400 actions/s; 250k in ~105 s).
