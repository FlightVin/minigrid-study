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

## F6 — M3 development comparison and intervention screen (development data only)

Batch `20261030T214937-19577`: 56/56 jobs exited 0; 8 forks, and one fork hash per fork across its 6
branches. All metrics finite. Tables: `reports/m3_probes.csv`, `reports/m3_screen_branches.csv`.
Final evaluation per branch: dev_eval 32 layouts x 8 attempts (P1), dev bank 64 items x 2 (c).

Ordinary PPO (arm 00), final P1 per fork (seed 0 / seed 1):

| K, BC checkpoint | pi0 p | after 50k probe | arm 00 after +250k |
|---|---|---|---|
| K=1, 16k | 0.55 / 0.56 | 0.59 / 0.56 | 0.66 / 0.70 |
| K=1, 4k | 0.25 / 0.24 | 0.26 / 0.29 | 0.47 / 0.40 |
| K=3, 16k | 0.25 / 0.22 | 0.23 / 0.31 | 0.33 / 0.32 |
| K=3, 4k | 0.01 / 0.02 | 0.02 / 0.02 | 0.06 / 0.04 |

Mean over 8 forks: pi0 0.263 -> probe 0.284 -> arm 00 0.373. Ordinary PPO now improves in 7/8 forks.
The K=3 early-checkpoint forks are near the floor (12-15 training successes in the 50k probe).
Probe Delta-c: mean -0.039 (range -0.195 to +0.047); 64 items x 2 attempts, so single values are noisy.

Screen, paired final P1 difference versus arm 00 on the same fork (n = 8 forks):

| Arm | mean P1 | mean diff | SD diff | forks > 0 |
|---|---|---|---|---|
| 00 | 0.373 | — | — | — |
| 10, alpha 0.25 | 0.377 | +0.004 | 0.061 | 3 |
| 10, alpha 0.5 | 0.390 | +0.017 | 0.049 | 5 |
| 01, lambda 0.01 | 0.359 | -0.014 | 0.039 | 2 |
| 01, lambda 0.1 | 0.340 | -0.033 | 0.046 | 2 |
| 01, lambda 1.0 | 0.326 | -0.047 | 0.060 | 2 |

- No screened intervention separates from arm 00. The reset differences are within about 0.4 SD of
  the fork-to-fork spread. The preservation differences decrease monotonically with lambda; this is
  a development pattern, not a confirmed effect.
- Mean bank P1 (suffix competence): 00 0.52; 10/alpha 0.5 0.58; 01 0.53-0.54. Reset starts may raise
  suffix competence more than normal-start P1. This is a hypothesis for confirmation, not a result.
- Curves (normal P1, 32 x 2 attempts): arm 00 0.336 at 127k and 0.408 at 252k. Performance is still
  increasing at 250k; the arm ordering is similar at both points.
- Selection (prespecified rule, DECISIONS): alpha 0.5 vs 0.25 differ by 0.013 < 0.02, so the rule
  selects the weaker value, alpha* = 0.25. lambda* = 0.01 (highest; also the weakest).

## F7 — M3 four-arm development comparison and run-to-run noise (development data only)

Batch `20261030T232600-96083`: 16/16 exited 0. Arm 11 (alpha 0.25, lambda 0.01) on the 8 M3 forks, plus
one replicate of arm 00 per fork. Contrasts use the selected values only (arm 10 alpha 0.25, arm 01
lambda 0.01); `tools/summarize_branches.py --alpha 0.25 --kl-coef 0.01`. Tables: `reports/m3_branches.csv`
(all 72 branches), `reports/m3_contrasts.csv` (8 forks). Final P1 from dev_eval 32 x 8 attempts.

Paired contrasts over 8 forks (mean, SD across forks, forks > 0):

| Contrast | mean | SD | > 0 |
|---|---|---|---|
| reset Y10 - Y00 | +0.004 | 0.061 | 3/8 |
| preserve Y01 - Y00 | -0.014 | 0.039 | 2/8 |
| combined Y11 - Y00 | +0.003 | 0.043 | 4/8 |
| interaction | +0.013 | 0.066 | 5/8 |
| Y11 - Y10 | -0.001 | 0.051 | 5/8 |
| Y11 - Y01 | +0.017 | 0.040 | 7/8 |

- Arm 11 mean P1 0.376 (arm 00 0.373). On development data no arm differs from arm 00 by more than
  0.02 on average. Per-fork contrasts range from -0.08 to +0.11.
- Combined is positive at K=3 in 4/4 forks (+0.02 to +0.06) and negative at K=1 in 4/4 (-0.01 to
  -0.06). This is a pattern in 8 development forks, selected by nothing; it is a candidate for the
  per-stratum description in M4, not a hypothesis test.
- Run-to-run noise: arm 00 replicate minus original (same fork, config and seed; MPS nondeterminism
  only): mean +0.008, SD 0.027, range -0.027 to +0.059. About 30% of the variance of a paired contrast
  (SD 0.04-0.06) is therefore nondeterminism plus evaluation noise at 32 x 8; the rest is fork-level
  heterogeneity of the effect or of training.
- Error found and fixed during analysis: the first contrast table silently took the last of several
  arm 01 / arm 10 rows per fork. The summarizer now requires `--alpha/--kl-coef` and stops on duplicates.
  Only the corrected table is saved.

## F8 — Pre-M4 audit of M3 from raw artifacts (2026-10-31)

Tools: `tools/audit_m3.py` (does not import `bc2rl.evaluate`) and `tools/info_map.py`. Outputs:
`reports/m3_manifest.csv`, `reports/m3_recomputed.csv`, `reports/m3_selected_contrasts.csv` and
`reports/m3_info_map.csv`.

**Inventory.** The M3 batches `20261030T214937-19577` and `20261030T232600-96083` hold 72 jobs:
- 8 probes;
- 32 selected branches (arm 00; arm 10 with alpha 0.25; arm 01 with lambda 0.01; arm 11 with 0.25/0.01);
- 24 screen branches (alpha 0.5; lambda 0.1 and 1.0);
- 8 repeats of arm 00.

`reports/m3_branches.csv` has 64 branch rows (48 + 16) with blank `variant` fields and no role column. The
manifest replaces it as the analysis key. The manifest maps every job to its fork, role, arm, alpha, lambda,
source commit, fork hash, and the SHA-256 of `fork.pt`, `final.pt` and the BC checkpoint. Selection is by
explicit key; duplicates raise an error.

**Recomputation.**
- P1, q, c, C4, R4 and P(success | arrival) were recomputed from `attempts_final.jsonl` for all 64 branches.
  The largest difference from `summary.json` is 0.0.
- The selected contrasts reproduce `reports/m3_contrasts.csv` exactly, using the original arm-00 runs.
  Repeats are excluded by role.

**Selection rule timing.** The alpha/lambda rule is in commit `cacef2b` (17:49:26 EDT, 2026-10-30). The
screen batch ran from that commit and started at 17:49:37 EDT. The rule was recorded before any screen
outcome existed.

**Corrections to earlier records** (the original text is kept above):
- **C1 (F6, Review 2, STATE).** "Ordinary PPO improves in 7/8 forks" is wrong. Arm 00 final P1 is above pi0 p
  and above post-probe p in **all 8** forks. In the two K=3 early-BC forks the gain is +0.02 to +0.04, which is
  within evaluation noise. pi0/probe estimates use 32 x 4 attempts and the final uses 32 x 8 on the same
  dev_eval layouts.
- **C2 (F7).** Withdrawn: "MPS nondeterminism only" and "about 30% of the variance of a paired contrast is
  nondeterminism plus evaluation noise". What the data support:
  - The repeats used the same fork, configuration and seeds. All 8 ended with different weights (different
    `final.pt` SHA-256), so training is not bitwise repeatable. The source of the nondeterminism was not
    isolated.
  - A repeat-minus-original difference combines training-path divergence with evaluation sampling of two
    different policies.
  - E3a: re-evaluating one fixed policy with a new seed moved P1 by -0.031. The analytic Monte Carlo SE of
    one policy's P1 at 32 x 8 is 0.020, so the SD of a difference between two independent evaluations is
    about 0.029.
  - The observed repeat SD (0.027 over 8 pairs) is therefore not distinguishable from evaluation noise
    alone. No variance decomposition is supported by 8 pairs.
- **C3 (freeze section 8).** The precision and power statement assumed independent strata within a seed.
  That is wrong. Within a seed, the four stratum contrasts share one BC run (both checkpoints lie on one
  training path, and both K use one BC model), and all seeds share the same evaluation layouts (crossed
  design). The power claim is withdrawn. Planning scenarios are in the freeze amendment.
- **C4 (freeze section 5).** pi0 and post-probe diagnostics were planned on `conf_final`, the same layouts as
  the final evaluation. The amendment moves them to a separate diagnostic role.
- **C5 (ledger).** About 2.75M environment actions ran outside the runner (tests and interactive checks) and
  were not in the ledger. They are now a conservative ledger line of 3.1M (DECISIONS, 01:05 EDT).
  - The 17 runner batches are otherwise complete: 7 M0 canary batches (5 stopped by design, 0 environment
    actions), 1 failed probe (23,097 actions, counted from partial records) and 9 completed batches.
  - Planner BFS computation and BC updates are not environment actions and are reported separately.

**Contract audit (code review plus empirical checks on 67,200 raw M3-era attempts).** No defect found.
- Reward is 1 only on delivery; every attempt ends in success or deadline. 0 successes without crossing.
- Restored bank states keep the original clock (start_step = snapshot step_count in all 28,352 bank
  attempts). Arrival remaining = limit - tau in all 38,848 normal attempts.
- Snapshots carry the full grid, inventory, agent pose, clock and flags (restore tests in `tests/test_task.py`).
- The bank is matched across K by donor (64/64). Reset-bin sizes are identical across K for entry, retrieval
  and carrying.
- Registry check passes (hash `1c2af199...`). 0 layout structures are shared between roles, and evaluation
  suffixes are unique.
- One BC path per seed; checkpoints 4k and 16k come from the same run.
- Fork state holds actor, critic, both Adam states, the torch generator, numpy RNG, sampler streams,
  in-flight environments and counters. There is no LR scheduler.
- The KL reference is pi0 from the same BC checkpoint, stored in the fork.
- GAE cuts at success and deadline and bootstraps only at batch ends (`tests/test_ppo.py`).
- All branches ran exactly 251,904 continuation actions. Only arm, alpha, lambda, K, checkpoint, seed and
  fork differ between branch configurations.
- **Engineering limitation (not a correctness defect):** branch `final.pt` holds weights and counters only,
  so M3 branches cannot be resumed. Existing 250k results are unaffected. Fixed for new runs (complete
  hashed state; exact CPU resume test).

**Intervention activity (E3c, 0 actions).**
- Anchor KL to pi0 at 251,904 for arm 01 vs arm 00: lower in 8/8 forks (0.057-0.107 vs 0.096-0.217;
  ratio 0.41-0.95, median 0.59). Arm 11 vs arm 10: lower in 8/8.
- The gradient norm of 0.01 x KL at arm-01 endpoints is 0.044-0.067, against a logged pre-clip actor gradient
  norm of 1.9-3.1 (about 1.5-3.5%). The preservation gradient is small per update, but its direction is
  consistent, and the KL it produces is clearly lower.
- Realized assisted-episode fraction in arms 10/11: 0.244-0.258 (alpha 0.25); assisted steps 10-19% of
  training steps.
- lambda = 0.01 is active. alpha = 0.25 is active.

**Evaluation repeatability (E3a).** Same seed: 384/384 attempts identical (MPS evaluation is deterministic
for a fixed checkpoint). New seed: P1 0.301 vs 0.332, c 0.609 vs 0.594. Layout heterogeneity is large (SD
of per-layout P1 0.36), so a single policy's P1 has a layout-sampling SE of about 0.064 at 32 layouts.

## F9 — Development campaign 2026-10-31: 500k runs, arrival states, repeatability (exploratory)

Batch `20261031T050016-80407` (commit `424354c`): 20 jobs exited 0. The batch was then stopped for budget
when `e2-bc-s2` started; that job executed 0 environment actions, and 5 E2 jobs never started
(DECISIONS 01:05). Campaign spend: 5,033,926 actions. Tables: `reports/dev2_long_evals.csv`,
`reports/dev2_long_contrasts.csv`, `reports/dev2_path_repeats.csv`. Figure: `reports/dev2_curves.svg`.
**Scope:** K=3, extended BC (16k), seeds 0 and 1 only. Every 500k run is a fresh run from the hashed M3 fork
(executed 501,760; states saved at 251,904 and 501,760).

**E1 — normal-start P1** (32 x 8 at 251,904 and 501,760):

| Seed | Arm | M3 original 251,904 | New path 251,904 | New path 501,760 | q 501,760 | bank c 501,760 |
|---|---|---|---|---|---|---|
| 0 | 00 | 0.332 | 0.402 | 0.406 | 0.652 | 0.688 |
| 0 | 10 | 0.324 | 0.328 | 0.367 | 0.688 | 0.648 |
| 0 | 01 | 0.273 | 0.352 | 0.398 | 0.660 | 0.664 |
| 0 | 11 | 0.375 | 0.355 | 0.398 | 0.750 | 0.656 |
| 1 | 00 | 0.324 | 0.320 | 0.398 | 0.727 | 0.766 |
| 1 | 10 | 0.348 | 0.309 | 0.418 | 0.754 | 0.758 |
| 1 | 01 | 0.348 | 0.379 | 0.430 | 0.770 | 0.734 |
| 1 | 11 | 0.363 | 0.312 | 0.461 | 0.836 | 0.727 |

- **Learning continues, slowly.** From 251,904 to 501,760 on the same path, P1 rose in 8/8 arm-runs (+0.004
  to +0.149; mean +0.065). Ordinary PPO: +0.004 and +0.078. Access q rose most in arm 11 (+0.12, +0.25).
  Curve points at 32 x 2 are too noisy to show shape (for example arm 00, seed 0: 0.40 -> 0.31 -> 0.41).
- **Paired contrasts at 501,760** (seed 0 / seed 1; within-seed layout 95% interval in brackets):
  - reset: -0.039 [-0.12, 0.04] / +0.020 [-0.10, 0.14]
  - preserve: -0.008 [-0.15, 0.14] / +0.031 [-0.05, 0.11]
  - combined: -0.008 [-0.11, 0.09] / +0.062 [-0.05, 0.18]
  - interaction: +0.039 / +0.012
  - Y11 - Y10: +0.031 / +0.043
  - Y11 - Y01: 0.000 / +0.031

  No contrast agrees in sign and size across the two seeds at >= 0.05. Inconclusive. Longer training did
  not reveal a separating effect in this condition.
- **Training-path variation.** New path minus M3 original at 251,904 (same fork, configuration and seeds):
  -0.051 to +0.078, SD 0.048 over 8 arm pairs. A difference of two independent evaluations of one fixed
  policy has SD of about 0.029 (F8). Seven times the variance ratio (0.048/0.029)^2 = 19 on 7 df gives
  p of about 0.01 under that evaluation-only null (approximate; assumes normality). So training-path
  variation is real and comparable in size to the contrasts.
- **The M3 K=3 combined benefit did not reproduce on the same forks.** Y11 - Y00 at 251,904 was +0.043 (seed 0)
  and +0.039 (seed 1) on the M3 paths, but -0.047 and -0.008 on the new paths.
  - The extended-BC-only moderation D(ext) = (Y11 - Y00)[K=3] - (Y11 - Y00)[K=1] at 250k was +0.055 / +0.086
    with M3 K=3 paths, and -0.035 / +0.039 with the new K=3 paths (K=1 unchanged; no K=1 rerun).
  - The two-checkpoint D_seed at 250k (M3 only) was +0.065 / +0.084.
  - D cannot be computed at 501,760 (no K=1 runs). The moderation pattern is not robust to the training path.

**E3b — arrival-state banks** (K=3, extended BC, 250k M3 policies). First crossings from 64 normal starts per
source:
- Seed 0: pi0 30, arm 00 39, arm 11 40 crossings, on 18-27 of 32 layouts; seed 1: 29 / 43 / 43.
- Every crossing has pose (13,4) facing east, carrying the yellow key, the same as the planner-bank entry
  states. The difference is remaining time (q10 22-81 vs 104) and the prefix-room configuration.

| Bank (seed 0 / seed 1) | pi0 | probe | 00 | 01 | 10 | 11 |
|---|---|---|---|---|---|---|
| pi0 arrivals | .52/.53 | .57/.50 | .55/.43 | .45/.52 | .47/.57 | .63/.57 |
| arm-00 arrivals | .41/.42 | .38/.43 | .38/.49 | .38/.52 | .38/.59 | .50/.58 |
| arm-11 arrivals | .56/.45 | .53/.44 | .56/.42 | .54/.50 | .51/.47 | .59/.50 |
| planner bank c (64 x 2) | .64/.64 | .66/.69 | .59/.64 | .64/.66 | .67/.69 | .64/.73 |

- Competence on actual arrival states (0.38-0.63) is below planner-bank c (0.59-0.73) for every policy.
  It agrees better with P(success | arrival) from normal attempts (arm 00: 0.46 / 0.50).
- The "clock_extended" condition (a separate task condition: same states, remaining set to 104) raises P1
  by 0.00 to +0.06 (mean +0.03). Remaining time explains only a small part of the gap.
- The remaining candidates are the prefix-room configuration (positions of opened doors and dropped keys
  differ from the demonstrations) and layout selection. Not tested.
- Policy ranking changes with the source bank and the seed. With 29-43 states x 2 attempts the SE is about
  0.06-0.08, so no arm is better on arrival states.
- Note: on the seed-0 arm-00 bank, five policies have the same total (30/78). The attempt files differ
  (54 of 78 attempts match arm 00); the equal totals are a coincidence.

**Regimes (information map, `reports/m3_info_map.csv`).** Assigned only where the measurements allow it:

| Condition | pi0 p / q / c | Supported regime | Not supported or too noisy |
|---|---|---|---|
| K=1, 16k | .55 / .99 / .68 | Access saturated; limited by suffix completion | Deterioration (c .65-.73 at 250k) |
| K=1, 4k | .25 / .98 / .27-.45 | 2: low initial suffix competence; most PPO gain (+.16-.21) | — |
| K=3, 16k | .23 / .46 / .64 | 1: low access, useful competence. 4: arrival competence below the bank, mostly not explained by time | 6: still learning at 500k (+.07) |
| K=3, 4k | .02 / .24 / .31-.41 | 1 + 2; late arrivals (median remaining 55-71). 3 in one fork: probe Delta-c -0.195 at seed 1, about 5.6 Monte Carlo SE at fixed bank states (SE 0.035); arm 00 c 0.31 vs pi0 0.41 at 250k | Near floor; one fork of 8, so not a general pattern |

- Regime 3 (deterioration): seen in one fork (K=3, 4k, seed 1); not consistent across the 8 forks.
- Regime 5 (optimization): no instability. Approx KL per update 0.002-0.006; explained variance
  0.60-0.88. The pre-clip actor gradient norm (1.9-3.1) exceeds the clip (0.5) on every minibatch, so
  clipping scales every step. That is identical across arms.

## F10 — M4 confirmation: no intervention changes P1 at 251,904 or 501,760 (confirmatory, 2026-10-31)

Design: PROTOCOL_FREEZE + Amendments 1 and 2. 5 seeds (10-14) x K {1, 3} x BC {4k, 16k} x 4 arms; one trajectory
per branch, endpoints E250 = 251,904 and E500 = 501,760 continuation actions; conf_final 64 x 8 + conf_bank 64 x 4
at each endpoint, common random numbers. Batches `20261031T144443-65814`, `...154838-81881`, `...165349-92672`,
`...175829-2090`, `...190210-20242` (105 jobs, all exited 0; 21 per seed) plus data batch `...144204-65491`.
Analysis `tools/analyze_m4.py` (committed `c53b63f` before outcomes); outputs `reports/m4_*.csv`, `m4_summary.json`.

**Completeness and audit (section 12).** 20/20 forks complete; every arm matches its probe's fork hash; no
exclusion, no retry, no missing value. P1, q, c recomputed from every attempt file equal the summaries. Independent
recomputation (P1, C4, R4, c; 8 branches x 2 endpoints sampled with RNG 20261031): maximum difference 0.0.

**Primary contrasts (P1; estimate, 95% t-interval df 4, crossed bootstrap 95%, Holm-6 p, verdict).**

| Endpoint | Contrast | Estimate | t 95% | Bootstrap 95% | 90% t (TOST) | p Holm-6 | Verdict |
|---|---|---|---|---|---|---|---|
| E250 | reset 10-00 | -0.011 | [-0.031, +0.009] | [-0.032, +0.011] | [-0.026, +0.005] | 1.00 | practically equivalent |
| E250 | preservation 01-00 | -0.006 | [-0.029, +0.016] | [-0.029, +0.016] | [-0.023, +0.011] | 1.00 | practically equivalent |
| E250 | combined 11-00 | -0.020 | [-0.047, +0.007] | [-0.046, +0.006] | [-0.041, +0.001] | 0.68 | practically equivalent |
| E500 | reset 10-00 | +0.004 | [-0.016, +0.023] | [-0.018, +0.025] | [-0.012, +0.019] | 1.00 | practically equivalent |
| E500 | preservation 01-00 | +0.003 | [-0.015, +0.021] | [-0.019, +0.024] | [-0.010, +0.017] | 1.00 | practically equivalent |
| E500 | combined 11-00 | +0.004 | [-0.028, +0.035] | [-0.025, +0.031] | [-0.021, +0.028] | 1.00 | practically equivalent |

Conclusion: at both budgets, every effect larger than 0.05 P1 in either direction is excluded (TOST). No
directional claim. The observed precision (95% half-widths 0.018-0.032) is close to the rho = 0 planning
scenario (0.031).

**Secondary (descriptive; pointwise 95% t-intervals, no claims).**
- Interaction and arm-11 vs arm-10 / arm-01 P1 contrasts: all within [-0.047, +0.025]; estimates -0.014 to +0.000.
- Access q: preservation raises q by +0.036 [+0.027, +0.045] at E250 and +0.040 [+0.027, +0.053] at E500, without
  a P1 change. Reset and combined q: +0.005 to +0.027, intervals include 0.
- Bank competence c: all three interventions +0.030 to +0.050; only combined at E500 excludes 0
  (+0.050 [+0.022, +0.079]). Higher planner-bank competence did not translate into normal-start P1 (F9: the
  bank is not the arrival distribution).
- E500 - E250 change of contrasts: reset +0.014 [+0.006, +0.023], combined +0.024 [+0.000, +0.047], preservation
  +0.009 [-0.015, +0.033]. The small E250 deficits close by E500; no contrast becomes positive.
- Moderation D (K=3 minus K=1): estimates -0.034 to +0.040; only preservation at E250 reaches +0.040
  [+0.000, +0.079] (pointwise, 1 of 12 descriptive tests; not a claim).
- Arm 00 learning: E500 - E250 = +0.037 (95% +-0.024; every seed positive, +0.018 to +0.066). Mean arm-00 P1:
  E250 0.409, E500 0.446 on conf_final. (pi0 0.306 and post-probe 0.346 are on conf_select, a different
  layout set; not directly comparable.)
- Strata (arm 00, E250 -> E500): K1/4k 0.508 -> 0.551; K1/16k 0.729 -> 0.766; K3/4k 0.046 -> 0.062;
  K3/16k 0.355 -> 0.406. Per-stratum arm differences are all within the seed-to-seed spread.

**Resources.** M4 55.85M actions (data 0.45M + 5 seed batches 55.39M, 11.05-11.11M each, all below the 12.24M
estimate); 5.38 h of batch wall time. Ledger 93.02M including 3.45M estimated test actions.
