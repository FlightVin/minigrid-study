# Findings

Status 2026-10-31: M0-M4 complete; post-M4 audit F11. Superseded interpretations are marked in place with
"[Superseded by F11 ...]"; the original text is kept.

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
  [Superseded by F11 (bank decomposition): this compares a mixed-progress bank with boundary arrivals. Planner
  entry-state c is close to own-arrival competence (mean gap +0.03; range -0.07 to +0.14); progress composition
  explains about 78% of the mixed-bank gap on average. No uniform mismatch.]
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
directional claim. [Superseded by F11: this holds for the prespecified equal-weight aggregate estimand only, not
for each condition.] The observed precision (95% half-widths 0.018-0.032) is close to the rho = 0 planning
scenario (0.031).

**Secondary (descriptive; pointwise 95% t-intervals, no claims).**
- Interaction and arm-11 vs arm-10 / arm-01 P1 contrasts: all within [-0.047, +0.025]; estimates -0.014 to +0.000.
- Access q: preservation raises q by +0.036 [+0.027, +0.045] at E250 and +0.040 [+0.027, +0.053] at E500, without
  a P1 change. Reset and combined q: +0.005 to +0.027, intervals include 0.
- Bank competence c: all three interventions +0.030 to +0.050; only combined at E500 excludes 0
  (+0.050 [+0.022, +0.079]). Higher planner-bank competence did not translate into normal-start P1 (F9: the
  bank is not the arrival distribution). [Superseded by F11: coexistence only; no causal link is established.]
- E500 - E250 change of contrasts: reset +0.014 [+0.006, +0.023], combined +0.024 [+0.000, +0.047], preservation
  +0.009 [-0.015, +0.033]. The small E250 deficits close by E500; no contrast becomes positive.
- Moderation D (K=3 minus K=1): estimates -0.034 to +0.040; only preservation at E250 reaches +0.040
  [+0.000, +0.079] (pointwise, 1 of 12 descriptive tests; not a claim).
- Arm 00 learning: E500 - E250 = +0.037 (95% +-0.024; every seed positive, +0.018 to +0.066). Mean arm-00 P1:
  E250 0.409, E500 0.446 on conf_final. (pi0 0.306 and post-probe 0.346 are on conf_select, a different
  layout set; not directly comparable.)
- Strata (arm 00, E250 -> E500): K1/4k 0.508 -> 0.551; K1/16k 0.729 -> 0.766; K3/4k 0.046 -> 0.062;
  K3/16k 0.355 -> 0.406. Per-stratum arm differences are all within the seed-to-seed spread.
  [Superseded by F11: wrong criterion. Paired seed differences show condition-level effects, e.g. preservation at
  K=3/early BC, E500: +0.045 [+0.035, +0.055], 5/5 seeds positive.]

**Resources.** M4 55.85M actions (data 0.45M + 5 seed batches 55.39M, 11.05-11.11M each, all below the 12.24M
estimate); 5.38 h of batch wall time. Ledger 93.02M including 3.45M estimated test actions.

## F11 — Post-M4 audit and interpretation revision (2026-10-31, owner instruction after M4)

Tool: `tools/postm4_audit.py` (no environment actions; reads raw attempt files, summaries, configs, saved states
by explicit job name). Outputs in `reports/postm4/`. Figure: `reports/postm4/effects.svg` (`tools/plot_postm4.py`).
Status labels: **prespecified** (freeze + Amendments 1-2), **secondary/descriptive** (freeze section 6, pointwise),
**post hoc** (chosen after M4 outcomes were seen).

**1. Primary aggregate result reproduced (prespecified).** Recomputed from raw attempts, independently of
`tools/analyze_m4.py`: identical estimates. Structure verified: 5 seed blocks (seeds 10-14), one BC run per seed
supplying both checkpoints (4k and 16k from `m4-bc-s<S>`), equal weights over the 4 strata, arms paired within a
fork (same fork hash, same layouts and attempt seeds), endpoints paired within a branch; episodes, checkpoints and
endpoints are never treated as replicates (df 4).

| Endpoint | Contrast | Estimate | 95% t | TOST t_L / p_L | TOST t_U / p_U | p_TOST | Holm-6 p (directional) |
|---|---|---|---|---|---|---|---|
| E250 | reset | -0.0107 | [-0.0306, +0.0091] | 5.49 / 0.0027 | -8.49 / 0.0005 | 0.0027 | 1.00 |
| E250 | preservation | -0.0062 | [-0.0285, +0.0162] | 5.45 / 0.0028 | -6.98 / 0.0011 | 0.0028 | 1.00 |
| E250 | combined | -0.0199 | [-0.0473, +0.0075] | 3.05 / 0.0191 | -7.08 / 0.0011 | 0.0191 | 0.68 |
| E500 | reset | +0.0036 | [-0.0163, +0.0235] | 7.49 / 0.0009 | -6.48 / 0.0015 | 0.0015 | 1.00 |
| E500 | preservation | +0.0031 | [-0.0146, +0.0208] | 8.32 / 0.0006 | -7.34 / 0.0009 | 0.0009 | 1.00 |
| E500 | combined | +0.0036 | [-0.0282, +0.0354] | 4.68 / 0.0047 | -4.05 / 0.0077 | 0.0077 | 1.00 |

- TOST: two one-sided t-tests (df 4) against -0.05 and +0.05; p_TOST = max(p_L, p_U). Each is an
  equivalence test at 0.05; it is a separate procedure from the Holm-6 directional family.
- Joint statement "all six are within ±0.05": intersection-union test, rejected-null when every p_TOST < 0.05
  (max 0.0191), level 0.05 without adjustment. Holm over the six TOST p-values also keeps all six (largest
  adjusted 0.0191).
- Uncertainty scope: the t-interval is conditional on the fixed evaluation panel (64 conf_final layouts per K,
  shared by all seeds); it covers training-path and attempt noise. The crossed bootstrap also resamples layouts.
  Bootstrap agreement is a sensitivity check, not replication.
- Bootstrap note: conf_final layouts are matched across K (item i has the same generator seed and suffix for K=1
  and K=3). The frozen bootstrap resampled K=1 and K=3 layout indices independently. A matched-index bootstrap
  gives nearly the same intervals (largest endpoint difference 0.0014; `primary.csv`). The frozen result stands.
- Wording that survives: "At the tested strengths and budgets, the equal-weight average intervention effects were
  practically equivalent to ordinary PPO within an absolute ±0.05 P1 margin." It does not cover each condition,
  learning curves, other doses, other tasks or budgets beyond 501,760.

**2. Condition-level effects (paired seed differences; `strata.csv`, `strata_seeds.csv`).** Per-stratum contrasts are
secondary/descriptive in the freeze (section 6); section 8 calls a per-stratum statement exploratory and requires
its own t-interval to exclude 0. Multiplicity, post hoc: Holm over the 24 arm-vs-00 contrasts (3 x 4 x 2), and over
the 48 contrasts examined in F10's stratum table (BH as well).
- **Preservation, K=3/early BC, E500: +0.0453, 95% t [+0.0353, +0.0554], t = 12.5, p = 0.00023; 5/5 seeds
  positive.** Holm-24 p 0.0056, Holm-48 p 0.011, BH-48 q 0.011. Baseline P1 0.062 -> +73% relative.
  Exact sign-flip p 0.0625 (the smallest attainable with 5 seeds). The t-based p depends on near-normal seed
  differences and on a seed SD (0.008) estimated from 5 values; the sign-flip test cannot reach 0.05 with 5 seeds.
- Preservation, K=1/early BC, E250: -0.0480 [-0.0768, -0.0193], p 0.0097 (Holm-24 0.22); at E500 -0.0008. Access is
  unchanged (q ~ 1); the deficit is in arrival-conditioned completion and closes by E500 (change +0.047 [+0.016,
  +0.079]).
- Preservation, K=3/extended BC, E500: -0.0273 [-0.0572, +0.0025], p 0.064.
- At K=3/early BC all three interventions are positive at both endpoints (E500: reset +0.031 [-0.010, +0.072],
  combined +0.043 [-0.001, +0.087]; these share the arm-00 baseline and are not independent tests).
- No other contrast reaches pointwise p < 0.05. The F10 statement "within the seed-to-seed spread" used an unpaired
  criterion and is withdrawn.
- **Checkpoint dependence within K (post hoc).** At K=3, E500: preservation effect at 4k minus at 16k = +0.073
  [+0.038, +0.108], p 0.0045; combined +0.063 [+0.024, +0.103], p 0.011. At K=1, E250: preservation -0.044
  [-0.070, -0.018], p 0.0094. Averaging the two checkpoints hides these opposite-signed effects.

**3. K=3/early-BC preservation subgroup audit (`k3early_subgroup.json`).**
- Rows: `m4-K3-u4000-s<S>-00` vs `m4-K3-u4000-s<S>-01-kl0p01`, S = 10-14; fork hashes match; conf_final K=3, 64
  layouts x 8 attempts = 512 attempts per branch; equal layout weights.

| Seed | P1 00 | P1 01 | Diff | q 00 | q 01 | Arrivals 00 / 01 |
|---|---|---|---|---|---|---|
| 10 | 0.1562 | 0.2012 | +0.0449 | 0.445 | 0.545 | 228 / 279 |
| 11 | 0.0723 | 0.1309 | +0.0586 | 0.348 | 0.443 | 178 / 227 |
| 12 | 0.0801 | 0.1211 | +0.0410 | 0.283 | 0.475 | 145 / 243 |
| 13 | 0.0000 | 0.0371 | +0.0371 | 0.000 | 0.186 | 0 / 95 |
| 14 | 0.0020 | 0.0469 | +0.0449 | 0.072 | 0.262 | 37 / 134 |

- Seed 13's arm 00 has zero arrivals and zero successes at both endpoints. It is valid data and is kept
  (its post-probe access was already 0.062, against 0.156 at pi0).
- Crossed seed x layout bootstrap 95%: [+0.022, +0.074]; layouts only (seeds fixed): [+0.027, +0.065].
- Per layout (mean over seeds): 36 positive, 12 negative, 16 zero of 64. The top 5 layouts carry 40% of the net
  gain, the top 10 carry 66%: broad but uneven. Leave-one-seed-out means 0.042-0.047. Leave-one-layout-group-out
  (8 groups of 8): 0.040-0.052, every 95% t-interval excludes 0.
- Mechanism (descriptive): the gain accompanies **greater access** (q higher in every seed, by +0.10 to +0.19).
  Arrival timing is similar (median tau 82 vs 84; median remaining 65 vs 62.5). Pooled arrival-conditioned
  completion is similar (0.270 vs 0.281). Per-seed decomposition: access part +0.020 to +0.051, completion part
  -0.010 to +0.035; seed 13 is unsupported (q = 0 for arm 00).
- Fixed states, longitudinal (conf_bank, the same 64 states throughout; 4 attempts per state at pi0, probe and the
  endpoints, 1 at the curve points): entry c is pi0 0.278, post-probe 0.234, arm 00 0.259 (E250) and 0.258 (E500),
  arm 01 0.311 and 0.369. Retrieval c: pi0 0.481, arm 00 0.391, arm 01 0.544 at E500. Normal starts on conf_select
  (the same layouts throughout; 64 x 2 at pi0/probe, 64 x 1 at curves): pi0 0.052, probe 0.039; arm 00 0.047 and
  0.053 at 126,976 / 376,832; arm 01 0.072 and 0.097. Reading: ordinary PPO in this condition stays near the
  pi0 level on fixed states and loses access in some seeds. Preservation keeps retrieval/carrying competence near
  or above pi0 and raises entry competence beyond pi0. conf_select and conf_final scores are not compared with
  each other.
- Ordinary PPO drifts furthest from pi0 in this condition (final anchor KL 0.363 vs 0.16-0.20 in the other strata).

**4. Competence-bank decomposition (`bank_m4.csv`, `bank_dev.csv`, `bank_dev_meta.json`).** The planner bank is
32 entry, 16 retrieval and 16 carrying states per K, equal weight per state, so mixed c = 0.5 entry + 0.25 retrieval
+ 0.25 carrying. Entry states have 104 steps remaining by construction.
- Example verified (M3, K=3/16k, seed 0, arm 00): mixed c 0.594, entry 0.391, retrieval 0.750, carrying 0.844; own
  arrival bank 0.385. Gap mixed - own = 0.209, entry - own = 0.006: progress composition explains 97% of it.
- Development own-arrival banks (pi0, 00, 11; seeds 0, 1): mixed - own 0.053 to 0.234 (mean 0.146); entry - own
  -0.072 to +0.141 (mean 0.032), so composition explains about 78% on average. Arrival competence exceeds planner
  entry competence for arm 11 seed 0 (0.588 vs 0.516) and pi0 seed 0 (0.517 vs 0.516). Arrival banks are small
  (29-43 states on 18-27 dev_eval layouts, 2 attempts each; SE about 0.06), and they use different layouts from
  the planner bank (dev_bank). Remaining time at arrival: median 90-98, 10th percentile 22-81 (planner entry: 104).
- M4 (planner entry c on conf_bank vs own-arrival r on conf_final, different layout sets): K=1 mean r - entry =
  -0.004, mixed - entry = +0.079; K=3 mean r - entry = -0.056, mixed - entry = +0.102. r exceeds entry c in 33/80
  K=1 and 15/78 K=3 branch-endpoints (2 have no arrivals; r undefined). K=3 arrivals have less remaining time
  (median 57-94) than planner entry states (104).
- Conclusion: the F9 "arrival competence below planner c for every policy" was mainly a progress-composition
  effect. After progress matching, planner entry competence is close to actual-arrival competence at K=1 and is
  moderately higher at K=3, where arrivals have less time and come from different layouts. Time and layout
  differences are not separated by existing data. The mixed bank remains a valid declared nu; its score is a
  distribution-specific measure, not completion from boundary entry. No causal link between bank scores and the
  small average P1 effects is established.

**5. Access vs arrival-conditioned completion (`decomposition.csv`, `decomposition_branches.csv`).** Per branch,
p = q x r holds exactly (every success crosses the boundary; checked on all 160 records).
- Aggregate figures verified: E500 arm 00 mean p 0.4463, mean q 0.7057, p/q 0.6324; arm 01 0.4494, 0.7459,
  0.6025. Weighting: every branch has 512 attempts, so p/q = total successes / total arrivals, an arrival-weighted
  r in which K=1 (q ~ 1) dominates. Means of per-branch r are 0.571 and 0.549 (arm 00 has one undefined branch).
- Within seed x stratum, delta p = delta q x mean r + delta r x mean q; equal-weight mean over 20 cells.

| Endpoint | Contrast | delta p | access part | completion part | unsupported (q0 = 0) |
|---|---|---|---|---|---|
| E250 | reset | -0.0107 | -0.0043 | -0.0076 | +0.0012 |
| E250 | preservation | -0.0062 | +0.0054 | -0.0130 | +0.0015 |
| E250 | combined | -0.0199 | -0.0044 | -0.0177 | +0.0021 |
| E500 | reset | +0.0036 | +0.0048 | -0.0044 | +0.0032 |
| E500 | preservation | +0.0031 | +0.0080 | -0.0067 | +0.0019 |
| E500 | combined | +0.0036 | +0.0013 | -0.0010 | +0.0033 |

  Preservation's access gain and lower arrival-conditioned completion partly cancel. r averages over
  policy-dependent arrival states, so a lower r is not evidence that a fixed skill deteriorated.

**6. Secondary outcomes, curves, optimization (`secondary.csv`, `checkpoint_interaction.csv`, `training.csv`).**
- C4 and R4 (freeze section 6 secondary; pointwise, unadjusted; 24 pooled secondary-metric contrasts). Preservation,
  E500: C4 +0.0329 [+0.0098, +0.0560], R4 -0.0189 [-0.0366, -0.0012]. E250: C4 +0.0240 [+0.0020, +0.0460]. Combined,
  E250: R4 -0.0386 [-0.0720, -0.0053]. Preservation q: +0.036 (E250) and +0.040 (E500), both excluding 0. These
  describe a redistribution of success across layouts (more layouts with at least one success, fewer with all
  successes), not generalization, policy-support expansion or broad skill retention.
- Curves: endpoint equivalence does not establish curve equivalence. Contrast changes E250 -> E500: reset +0.014
  [+0.006, +0.023], combined +0.024 [+0.000, +0.047]; at K=1/early BC, preservation +0.047 [+0.016, +0.079] and
  combined +0.039 [+0.010, +0.068]. Early deficits close later in some conditions. No area-under-curve test and no
  per-arm best checkpoint are used.
- Optimization: actor lr 3e-5; gradient-norm clipping at 0.5 is active in 100% of updates (median pre-clip norm
  about 2.4); PPO clip fraction about 0.027 and approx KL about 0.003 per update. Anchor KL to pi0 grows from 0.09 to
  0.22 (arm 00) and to 0.10 (preservation arms); P1 still rises between endpoints. These are consistent with small
  per-update policy changes, but no learning-rate or clipping ablation was run at this stage. "Step-size-limited"
  is a hypothesis, not a diagnosis.

**7. Selection value (`selection.csv`; not an RQ2 result).** Hindsight in-sample reference: best observed arm per
condition, averaged, vs best observed fixed arm: E500 0.46035 vs 0.44990 (arms 10 and 11 tie), gap 0.01045; E250
0.41660 vs 0.40938 (arm 00), gap 0.00723. This is optimistic (it selects on the same noisy means) and is not a
population upper bound. Leave-one-seed-out condition-identity rule (choose per K x checkpoint on 4 seeds, apply to
the 5th; same conditions, new training replicates): E500 +0.0006 vs the fixed arm chosen the same way, -0.0036
[-0.026, +0.019] vs ordinary PPO; E250 -0.0055 [-0.019, +0.008]. Demonstrated headroom is about 0.01 P1 in hindsight
and about 0 out of sample, before any diagnostic cost. An early-measurement selector would have to beat the
zero-cost condition-identity rule.

**8. Execution verification (`execution.json`).** 20 forks, 160 branch-endpoint records, no problems: probe lineage
(`@/m4-bc-s<S>`, bc_update, bc_seed, diag_role conf_select, eval_role conf_final); fork hashes recomputed from
fork.pt; all 160 saved states (state_251904 and state_501760 of 80 branches) rehashed and equal to their summaries; every evaluation's
per-item time limits match the declared layout role (pi0, probe and curves on conf_select; endpoints on conf_final);
P1, q, c, C4, R4 and P(success | arrival) recomputed for all 160 records. Pairwise role overlap (structure hash,
generator seed, suffix signature) among conf_select, conf_bank, conf_final and every dev-v2 role: 0 in all 24 pairs.
conf_bank: 32/16/16 per K, 64 layouts, matched across K; conf_final matched across K. Missing conditional
statistics: 2 branch-endpoints with no arrivals (P(success | arrival) reported as missing), 1,193 layout cells with
no arrivals.

**F11 addendum (self-review 2026-10-31 19:05; `reports/postm4/extras.json`).**
- Three-way intervention x K x checkpoint (post hoc; [(4k - 16k) at K=3] - [(4k - 16k) at K=1] of each contrast; 6
  tests): preservation E500 +0.069 [+0.005, +0.132], p 0.040; reset E250 +0.088 [+0.016, +0.159], p 0.027; the other
  four p >= 0.063. Neither survives Holm over these 6 (smallest adjusted 0.16).
- K=3/early-BC arrival states: in both arms every first crossing carries the yellow key (inventory identical);
  arrival timing is similar (F11 section 3). The access gain is therefore not a change in arrival inventory.
- Descriptive curves (means over 5 seeds). conf_select points (pi0 64 x 2, post-probe 64 x 2, 126,976 and 376,832
  64 x 1) and conf_final endpoints (64 x 8) are different layout sets and are not differenced across sets. K=3/early
  BC, conf_select: pi0 0.052, probe 0.039, arm 00 0.047 -> 0.053, arm 01 0.072 -> 0.097, arm 10 0.056 -> 0.119, arm
  11 0.053 -> 0.116. Full table in `extras.json`.
- Diagnostic cost: the probe's pi0 + post-probe evaluations cost 37k-73k actions per condition (7-15% of a 501,760
  continuation). The probe itself is shared by every method in the manuscript's RQ2 accounting and is not a
  selection cost. Against a demonstrated out-of-sample selection gain of about
  0 (hindsight 0.01), no diagnostic-based selector is supported by M4.

## F12 — R1 focused replication (2026-11-01; Amendment 3, prespecified)

Tool: `tools/analyze_r1.py --check-states` (frozen at `01beef9`). Outputs: `reports/r1/r1_summary.json`,
`r1_seeds.csv`, `r1_branches.csv`, `r1_curves.csv`. Full write-up: `reports/REPORT.md` section R1.

- Design complete: 8/8 seeds (15-22), 32 branches, no exclusions, no problems; all metrics recompute from raw
  attempts; fork hashes, saved-state hashes and step counters all check.
- **H1** (preservation effect, K=3/early BC, 501,760): +0.0403, 95% t [+0.0042, +0.0764], p 0.033, **Holm p
  0.067: not supported**. 6/8 seeds positive. Seed SD 0.043. Sign-flip p 0.055. Crossed bootstrap [+0.006, +0.075].
- **H2** (checkpoint interaction, early minus extended): +0.0391, 95% t [-0.009, +0.087], **Holm p 0.096: not
  supported**. Extended-BC effect +0.001 [-0.022, +0.025].
- Frozen interpretation cell: **inconclusive** (H1 upper bound 0.076 > M4 estimate 0.045). Not a failure to
  replicate. Magnitude: not distinguishable from the 0.05 practical threshold.
- 251,904 (descriptive): preservation ahead with both checkpoints (early +0.030, 8/8; extended +0.042, 7/8). With
  extended BC, ordinary PPO catches up by 501,760.
- Secondary (early, 501,760): the gain is mainly access q (+0.038 [+0.012, +0.065]); bank c +0.029 is unresolved.
  Anchor KL is lower in arm 01 as intended.
- Against M4 (separate, not pooled): +0.040 vs +0.045. The M4 subgroup's seed SD (0.008) understated the spread
  by a factor of about 5. That subgroup was selected after the fact, which explains it.
- M4 aggregate equivalence (F10, F11 section 1) is unchanged.
- Cost: 25,471,099 actions (89.7% of 28.4M). One deterministic failure (telemetry race) was fixed and rerun, and
  is kept in the record.

## F13 — Targeted R1 audit and corrected interpretations (2026-11-01; before R2)

Tool: `tools/audit_r1.py` (independent of `tools/analyze_r1.py`; no environment actions). Outputs:
`reports/r1/audit.json`, `reports/r1/decomposition.csv`, `reports/r1/m4_decomposition.json`. Full text: REPORT R1.10.
- Inventory exact: 8 complete BC + 1 failed BC (kept), 16 probes, 32 branches, **64 endpoint records** (512 normal +
  256 bank attempts each), one identical panel equal to the r1_final K=3 registry. "48 branch summaries" in F12/
  REPORT was a documentation error (16 probe + 32 branch summaries).
- Statistics reproduce exactly with an independent t CDF (H1 p 0.0335, Holm 0.0670; H2 0.0957).
- Actions: step records 25,471,227 vs ledger 25,471,099; the failed seed 17 BC job ran 128 actions after its last
  metrics row. Ledger fixed; R1 spend 25,471,227.
- Exact decomposition dp = dq (r1+r0)/2 + dr (q1+q0)/2 (arithmetic, not mediation), K=3/early BC at E500:
  R1 access +0.0115 (SD 0.010), completion +0.0288 (SD 0.038), sum +0.040; M4 subgroup (4 seeds with r defined;
  seed 13's ordinary arm never arrived) access +0.033, completion +0.015. The split differs between the studies.
- Corrections to F12: "the gain is mainly access q" is withdrawn (it compared significance across measures on
  different scales); "8 seeds cannot confirm" -> power was limited (~0.62 for H1 alone), not zero; the larger SD is
  not attributed to subgroup selection alone (small-sample SD estimation, panel, training variability); R1 is
  described as compatible with a positive effect similar to M4's, without treating interval overlap as replication.
  R1's frozen Holm-2 verdict (not supported) is unchanged.

## F14 — R2 20-seed replication (2026-11-01; Amendment 4, prespecified; R2 data only)

Tool: `tools/analyze_r2.py --check-states` (frozen before R2 data). Outputs: `reports/r2/r2_summary.json`,
`r2_seeds.csv`, `r2_branches.csv`, `r2_decomposition.csv`, `r2_curves.csv`, figures `endpoints.svg`,
`paired_effects.svg`. Seeds 23-42 all complete (20/20, none excluded, no problems, all saved states match hashes,
step counters equal summaries). 20 batches exited 0 at 0.925-0.973 of their conservative cost. First read of any
aggregate R2 outcome: after the 20th seed finished.
- **Primary (E500, n = 20):** d = P1(01) - P1(00) = **+0.0097**, seed SD 0.028, 95% t-interval
  **[-0.0035, +0.0229]**, t = 1.53, df 19, **p = 0.142**. 12/20 seeds positive. Baseline (00) P1 0.093.
  Frozen decision: **not supported**; magnitude cell: **informative — the interval excludes the 0.03 planning
  effect** (and the M4 estimate 0.045). One-sided descriptive p against 0.03: 0.998; against 0.05: >0.999.
- Sensitivity (not the decision rule): exact sign-flip p 0.146; crossed seed x layout bootstrap 95%
  [-0.0071, +0.0260] (agrees). The layouts-only bootstrap [0.0019, 0.0177] ignores training-seed variation and is
  not a valid interval for the estimand.
- The observed SD (0.028) is below every planning SD (0.035-0.06); the null result is not a power failure.
- E250 (descriptive): +0.0099 [-0.0033, +0.0230], almost the same as E500.
- Exact decomposition at E500 (20/20 defined): access +0.0036 (SD 0.013), completion +0.0061 (SD 0.026). Both
  are small and neither interval excludes 0. No access-versus-completion claim.
- Descriptive R1+R2 precision-weighted mean +0.014 (approx. 95% [0.003, 0.026]); no p-value; adaptive study
  selection disclosed (R1 and R2 exist because M4's post hoc subgroup looked positive). Not a test.
- Interpretation: under the frozen protocol, preservation (lambda 0.01) at K=3 with early BC does not produce an
  improvement of 0.03 or more in normal-start P1 at 501,760 actions. A small positive effect (below about 0.023)
  is not excluded. The M4 post hoc subgroup estimate (+0.045) did not replicate at its size; R1's +0.040 was
  probably an overestimate (consistent with selection after M4 and with sampling variation). M4 (F10) and R1 (F12)
  frozen verdicts are unchanged. Per the owner instruction, this replication stops here; no further R2 testing.

## F15 — E1 cross-panel re-evaluation (2026-11-01; Amendment 4, exploratory)

Tool: `tools/analyze_crosspanel.py`; outputs `reports/crosspanel/` (summary, per-policy CSV, `cells.svg`). 26 saved
501,760 actors (M4 seeds 10-14, R1 seeds 15-22; K=3, early BC, arms 00 and 01) evaluated on conf_final (64 K=3
layouts) and r1_final (128) with 4 attempts each and a new attempt seed (969000). No records overwritten. 0 missing,
0 problems. 2,810,699 actions (ceiling 4M).

| cohort / panel | P1 00 | P1 01 | d (95% t) | seed SD | n pos |
|---|---|---|---|---|---|
| M4 / conf_final | 0.064 | 0.105 | +0.041 [+0.017, +0.065] | 0.019 | 5/5 |
| M4 / r1_final | 0.066 | 0.123 | +0.058 [+0.025, +0.091] | 0.026 | 5/5 |
| R1 / conf_final | 0.108 | 0.133 | +0.025 [-0.006, +0.056] | 0.037 | 5/8 |
| R1 / r1_final | 0.128 | 0.148 | +0.020 [-0.008, +0.048] | 0.033 | 6/8 |

- The M4-R1 difference in d follows the **cohort (the trained policies)**, not the panel: on the same panel the R1
  policies show a smaller d (-0.016 on conf_final, -0.038 on r1_final). Within a cohort the panel change is small
  (M4 +0.017 [-0.007, +0.042]; R1 -0.005 [-0.029, +0.020]). Panel difficulty does not explain the SD difference
  either: the R1 SD stays 0.033-0.037 on both panels.
- Re-evaluation with new attempt seeds: per-policy P1 correlates 0.93 (M4) and 0.95 (R1) with the original final
  records; mean absolute change 0.020 and 0.015. The R1 cohort's own-panel d fell from +0.040 (original) to +0.020
  (new attempts on the same policies and panel). About half of R1's original estimate was therefore attempt-level
  evaluation noise with a favourable draw; the M4 cohort's d (+0.045 -> +0.041) was stable.
- Interpretation: the M4 subgroup effect is a property of those five trained policy pairs, and it holds on a
  different panel. It did not transfer to new training seeds (R1 +0.020 on re-evaluation; R2 +0.0097 with 20 seeds,
  F14). Exploratory; already observed policies; not a replication.

## F16 — E2 anchor components (2026-11-01; Amendment 4, exploratory, 3 seeds, development panel)

Tool: `tools/analyze_comp.py --check-states`; outputs `reports/comp/` (summary, per-branch CSV, `contrasts.svg`).
Forks of R1 early-BC probes, seeds 15-17; arms 00, 01p (prefix term only, 0.0025), 01s (suffix term only, 0.0075),
01 (both); 251,904 actions; evaluation 32 r1_select layouts x 4 and r1_bank 64 x 2 (seed 979000). 12/12 branches,
states match hashes, lineage correct. 3,359,919 actions (ceiling 4M). P1 contrasts (per seed 15/16/17; mean, 95% t df 2):

| contrast | per seed | mean [95% t] |
|---|---|---|
| prefix (01p - 00) | -0.008, +0.008, -0.031 | -0.010 [-0.059, +0.038] |
| suffix (01s - 00) | +0.055, +0.047, +0.063 | +0.055 [+0.035, +0.074] |
| both (01 - 00) | +0.016, -0.039, -0.008 | -0.010 [-0.079, +0.058] |
| interaction | -0.031, -0.094, -0.039 | -0.055 [-0.139, +0.030] |

- The suffix-only arm was higher in all 3 seeds, while the full penalty ("both", the R1/R2 arm) was not. Arm means:
  00 0.070, 01p 0.060, 01s 0.125, 01 0.060. Suffix decomposition (access, completion): s15 +0.009/+0.046, s16
  +0.067/-0.020, s17 +0.031/+0.032 — no consistent stage.
- Training: the suffix term lowered suffix-state anchor KL (01s 0.082, 01 0.074 vs 00 0.138); the prefix term at
  0.0025 hardly moved prefix KL (01p 0.125 vs 00 0.128). Training access/success rates were similar across arms.
- Caution: 3 seeds, 128 normal attempts per branch (binomial SE ~0.02 per arm), development panel, 4 contrasts
  without correction, one checkpoint. The small seed SD of the suffix contrast (0.008) is itself poorly estimated.
  The pattern (suffix-only positive, both null) has no mechanism that this design can identify; "both" contains the
  same suffix term. Hypothesis-generating only. A component effect here describes this penalty implementation,
  not a skill or pathway.
- Engineering: the 00 and 01 branches did not reproduce the R1 branches' 251,904 state hashes (not required; the
  Amendment 4 anchor RNG stream and MPS execution change the trajectories).

## F17 — Programme cost and execution (2026-11-01; Amendment 4)

Spend 39,643,852 of the 50M budget (start 118,670,430; total 158,314,282). Reserve not used.

| study | measured | conservative plan | ceiling |
|---|---|---|---|
| R2 (data, tests, smoke est., canary, 20 seeds) | 33,404,912 | 35,133,360 | 38M |
| E1 cross-panel | 2,810,699 | 2,900,248 | 4M |
| E2 components | 3,359,919 | 3,399,624 | 4M |
| final tests | 62,290 | 100,000 | (audit 0.3M) |
| development test before freeze (outside runner) | 6,032 | - | - |

R2 smoke is the conservative estimate (250,000; point 219,343) after the lost step record (IMPLEMENTATION).
Every batch exited 0 at 0.925-0.976 of its conservative estimate. Failures: none in any job. Deviations: (1) lost
r2-smoke step record (fixed, estimated); (2) run_program completion detection (fixed at Review 8, no effect on
jobs); (3) xp-r1 refused at start because of an uncommitted file (agent error, 0 actions, rerun unchanged).
Final runner test job: 274 passed, 3 skipped. Independent verification (`tools/verify_program.py`,
`reports/program/verification.json`): R2, E1 and E2 numbers reproduce from raw attempts; no problems.

## F18 — Interpretation corrections and component-code audit (2026-11-01b; owner instruction, before A3)
- R2 (F14) verdict and interval unchanged. "Not a power failure" is replaced: the achieved 95% interval
  [-0.0035, +0.0229] is narrow enough to constrain effects of the originally motivating size (0.03, 0.045) under the
  tested protocol.
- E1 (F15): the R1 re-evaluation (+0.020 vs original +0.040) does not identify a share of noise; both evaluations
  have sampling error. Cohort difference in d on the same panel: conf_final -0.016 (Welch 95% [-0.050, +0.019]),
  r1_final -0.038 ([-0.075, -0.000]). Within-cohort panel change: M4 +0.017 [-0.007, +0.042], R1 -0.005
  [-0.029, +0.020]. Panel effects of ~0.02-0.04 are not excluded. "The effect follows the trained policies, not the
  panel" and "about half was noise" are withdrawn.
- E2 (F16): the statement that suffix-only benefit conflicts with a null mixed arm is withdrawn. Losses add at a fixed
  parameter vector; outcomes after nonlinear optimisation through shared parameters need not.
- Component code audit (Amendment 5 B): no defect; E2 and R2 results unaffected. Shared action/permutation generator
  documented (arm-invariant consumption).
- Literature (manuscript section 3.1): forward-KL preservation on stored pretraining states and the frequent/rare
  state distinction are established (Wolczyk et al. 2024); reset curricula are established (Florensa et al. 2017,
  Uchendu et al. 2023, Tao et al. 2024). A3 adds only controlled evidence: within one stored demonstration bank,
  whether allocating the same penalty to post-boundary states changes normal-start success, separated from a
  uniform strength reduction, on 24 independent seeds.

## F19 — A3 confirmatory component study (2026-11-01b; Amendment 5; 24 seeds, fresh roles)

Tools: `tools/analyze_a3.py --check-states` (frozen), `tools/verify_program2.py` (independent; agrees on every
quantity), `tools/plot_program.py --which a3`. Outputs: `reports/a3/` (summary, CSVs, `paired_effects.svg`,
`diagnostics.svg`), `reports/program2/verification.json`. Seeds 43-66, K=3, early BC (4,000 updates), five arms
forked from the same probe per seed. Evaluation: a3_final 128 x 4 normal starts and a3_bank 64 x 4, eval seed 959000.

**Execution.** 24/24 seeds, no exclusions or problems. 240 saved states match their hashes, all branches use one
identical panel, and 144/144 step records equal their summaries. A3 spend 88,138,774 (ceiling 103M); every batch was
under its conservative cost (about 0.92 of it).

**Primary (H1, C−A at 251,904): supported.** d = +0.0106, 95% t [+0.0019, +0.0193], p 0.019, 17/24 seeds positive.
Exact sign-flip p 0.014. Layouts-only bootstrap [+0.0035, +0.0175]. **The crossed seed × layout bootstrap
[−0.0014, +0.0235] includes 0.** That bootstrap is a prespecified sensitivity analysis, not the decision rule, so the
decision stands. The disagreement means the evidence is modest once uncertainty over the layout panel is included.
Arm means at 251,904: A 0.066, C 0.076, a relative change of about +16% on a low base. The effect is about one-third
of the 0.03 planning value and one-fifth of the 3-seed E2 estimate (+0.055, F16), which was inflated.

**Gate (H2a C−D, H2b C−E; Holm): neither supported.** C−D +0.0007 [−0.0079, +0.0093], C−E −0.0003
[−0.0101, +0.0094], Holm p 1.0 for both. Adding the prefix term (D) did not reduce the suffix benefit. The E2 pattern
"suffix positive, both null" did not replicate: D−A was +0.0098 [+0.0014, +0.0183]. C and E have the same total
effective coefficient (0.0075). E puts 25% of it on prefix rows and so carries 0.75× C's suffix coefficient. Their
equality means this study does not identify a dose response or an allocation effect within this range. The intervals
exclude differences larger than about ±0.01.

**Secondary (descriptive, 95% t, no multiplicity claim).**

| contrast | 251,904 | 501,760 |
|---|---|---|
| B−A (prefix only) | −0.0037 [−0.0117, +0.0042] | +0.0007 [−0.0101, +0.0116] |
| C−A (suffix only) | +0.0106 [+0.0019, +0.0193] | +0.0160 [+0.0054, +0.0265] |
| D−A (both) | +0.0098 [+0.0014, +0.0183] | +0.0087 [−0.0024, +0.0198] |
| E−A (both, 0.75×) | +0.0109 [+0.0013, +0.0205] | +0.0142 [+0.0025, +0.0260] |
| D−C | −0.0007 [−0.0093, +0.0079] | −0.0072 [−0.0191, +0.0047] |
| interaction D−B−C+A | +0.0030 [−0.0050, +0.0110] | −0.0080 [−0.0244, +0.0084] |

- Persistence: the suffix effect did not shrink from 250k to 500k (C−A +0.016 at 501,760; arm means A 0.095,
  C 0.110). D−A at 501,760 (+0.0087) agrees with the R2 estimate for the same full-penalty arm (+0.0097, F14). The
  two studies are separate and are not pooled.
- Prefix-only preservation at 0.0025 had no detectable effect. It is a weak manipulation: training prefix anchor KL
  was 0.122 for B against 0.129 for A. This result does not test prefix preservation at a strength that changes
  prefix behaviour.
- Mechanism (exact decomposition, C−A): at 251,904 the completion part was +0.0069 [+0.0017, +0.0121] (18/23
  positive) and the access part +0.0042 [−0.0029, +0.0113]. At 501,760 they were +0.0153 [+0.0073, +0.0233] and
  +0.0013. Fixed-bank boundary-entry competence rose (C−A +0.023 at 250k, +0.032 at 500k), and so did bank c.
  Suffix preservation acts mainly through success after arrival, not through more arrivals.
- Training diagnostics (means to 251,904): the suffix term lowered suffix-row anchor KL from about 0.14 (A) to about
  0.08 (C, D, E). Update size was the same in every arm to within about 2%: actor norm about 0.053, successive-policy
  KL on prefix rows about 0.0033 and on suffix rows about 0.004. PPO approx-KL and entropy did not differ either. The
  applied penalty was at most 0.0008 per update. The penalty redirects updates on suffix states; it does not slow
  learning.

**Interpretation.** In this regime (K=3, early BC, normal starts, P1 about 0.07–0.11), preserving the BC policy on
suffix states improved normal-start success by about one percentage point at 250k. The pre-registered test supports
the improvement, and it persisted to 500k. It is small in absolute terms. Its support weakens when layout-panel
uncertainty is added, and it should not be generalized beyond this task, K and BC checkpoint. The full penalty and
the 0.75× split performed as well as suffix-only, so restricting the anchor to suffix states is not necessary within
this range.

## F20 — Initialization calibration (2026-11-01b; Amendment 5 C; development roles; seeds 67-69)

Tools: `tools/analyze_cal.py` (frozen), `tools/verify_program2.py` (agrees), `reports/cal/` (`cal_summary.json`,
`cal_variants.csv`, `access_entry.svg`). 9 BC jobs (rho 0.2 / 0.5 / 0.8 × 3 seeds), checkpoints 4,000 and 8,000,
1,475,592 actions.

| variant (three-seed means) | K1 q | K1 entry | K1 P1 | K3 q | K3 entry | K3 P1 | qualifies |
|---|---|---|---|---|---|---|---|
| rho 0.2, 4k | 0.865 | 0.315 | 0.293 | 0.047 | 0.307 | 0.013 | no (entry, K3 q) |
| rho 0.2, 8k | 0.962 | 0.604 | 0.577 | 0.205 | 0.604 | 0.110 | **yes (selected)** |
| rho 0.5, 4k | 0.920 | 0.190 | 0.207 | 0.167 | 0.167 | 0.040 | no (entry) |
| rho 0.5, 8k | 0.985 | 0.516 | 0.540 | 0.385 | 0.456 | 0.200 | no (entry −0.03 / −0.09) |
| rho 0.8, 4k | 0.998 | 0.060 | 0.058 | 0.287 | 0.049 | 0.010 | no (entry) |
| rho 0.8, 8k | 1.000 | 0.229 | 0.247 | 0.525 | 0.188 | 0.108 | no (entry, K3 q) |

- **Answer to objective 5.** An initialization with high boundary-entry competence and low K3 access exists.
  Sampling prefix states less (rho 0.2) and training longer (8k) gave entry about 0.60 in both conditions with K3
  access 0.21.
- **Trade-off.** Across variants, more prefix sampling raised access and lowered entry competence. More updates
  raised both.
- **Fragility.** Only 1/3 seeds meets every target on its own: s67 has K3 entry 0.531; s68 has K1 P1 0.645, above
  the room limit. K1 P1 0.577 leaves little room for normal-start learning. The selection is on means, as frozen.

## F21 — Calibrated-regime pilot (2026-11-01b; Amendment 5 D; exploratory; 3 seeds × K1, K3)

Tools: `tools/analyze_pilot.py --check-states` (frozen before the runs), `tools/verify_program2.py` (agrees on all
8 contrasts), `reports/pilot/` (`pilot_summary.json`, `pilot_branches.csv`, `contrasts.svg`). Forks of the selected
calibration checkpoints (rho 0.2, 8k). Arms 00, 10 (resets, alpha 0.25), 01s (suffix KL, effective 0.0075) and
11s. 251,904 actions. pl_final 64 × 4 per K; pl_bank 64 × 4. 24/24 branches, no problems. 7,601,832 actions.

Normal-start P1 (arm means; contrasts with 95% t, df 2):

| K | 00 | 10 | 01s | 11s | 10−00 | 01s−00 | 11s−00 |
|---|---|---|---|---|---|---|---|
| 1 | 0.711 | 0.729 | 0.710 | 0.716 | +0.018 [−0.092, +0.129] | −0.001 [−0.075, +0.072] | +0.005 [−0.124, +0.134] |
| 3 | 0.240 | 0.241 | 0.242 | 0.255 | +0.001 [−0.078, +0.080] | +0.003 [−0.082, +0.087] | +0.016 [−0.052, +0.084] |

- **K1 is at a ceiling.** Normal-start access was about 1.0 in every arm and P1 about 0.71. Interventions that act
  on access or post-boundary retention have little to change.
- **K3 normal-start P1 showed no detectable difference.** The intervals (about ±0.08) are compatible with effects
  several times the A3 size. The pilot cannot detect a 1–2 point effect.
- **K3 boundary-entry competence on the fixed bank was higher in every intervention arm:** 00 0.500, 10 0.586,
  01s 0.633, 11s 0.599. The shared post-probe policy scored 0.505 and pi0 scored 0.591; the probe drop is mostly
  s69, 0.547 → 0.336. 01s−00 was +0.133 [−0.003, +0.269], positive in 3/3 seeds (+0.07, +0.17, +0.16). Bank c rose
  by +0.08 to +0.09. The gain did not appear in normal-start completion r (+0.007): within 251,904 actions, better
  competence on fixed boundary states did not translate into normal-start success.
- **Training records.** Assisted (reset) and normal episodes are reported separately. In K3 the assisted success rate
  was about 0.70–0.72 and the normal success rate about 0.16–0.18 in every arm. Resets used about 9% of K3 training
  steps and 15% of K1 steps. The suffix term lowered suffix-row anchor KL (K3 0.102 → 0.052).
- **RQ2 hindsight (in-sample, 3 seeds).**
  - Best arm per K: K1 10, K3 11s.
  - Best fixed arm: 11s (mean P1 0.486).
  - The condition-identity rule gives 0.492, a headroom of +0.0065.
  - The K1−K3 differences of each contrast were between −0.023 and +0.017, and their per-seed signs were mixed.
  - Choosing by condition identity has no demonstrated value here.

## F22 — Programme synthesis and costs (2026-11-01b; Amendment 5 F–G)

**RQ1 (does preserving BC behaviour on chosen states help, and where?)**
1. Suffix-only preservation helps on independent seeds, by a small amount. H1 was supported at +0.011 (A3, 24
   seeds). The crossed bootstrap includes 0.
2. Allocation versus a weaker coefficient: not distinguished. C (suffix 0.0075) and E (prefix 0.001875 + suffix
   0.005625; same total) differ by −0.0003 ± 0.010.
3. Adding the prefix component did not reduce the suffix benefit (C−D +0.0007 ± 0.009). The E2 contrast
   "suffix-only positive, full penalty null" (F16) did not replicate.
4. The effect persisted to 501,760 (C−A +0.016, descriptive). The full penalty's 500k estimate (+0.009) matches R2's
   (+0.0097). R2's "not supported" verdict for the full penalty and A3's supported suffix-only result do not
   contradict each other: the estimates are similar, and A3 tested at 251,904 with 24 seeds.
5. The gain acts mainly through completion after arrival, not through access.
6. In the calibrated regime, neither resets nor suffix preservation changed normal-start P1 detectably (3 seeds). Both
   raised K3 boundary-entry competence on the fixed bank.

**RQ2 (should the intervention be chosen per condition?)**
- Variation across conditions was small and inconsistent between seeds. The hindsight headroom was 0.0065 even
  in-sample.
- q, entry competence and delta-c separate the regimes descriptively: K1 has q about 1, so there is no access deficit.
  None of them predicted a normal-start gain.
- The cost of a selector would exceed any demonstrated benefit. Training a selector is not justified on this
  evidence.

**Novelty.** State-selective retention on stored demonstration states is an established remedy (Wołczyk et al.
2024; LITERATURE.md). This programme adds controlled evidence from one task family on four points:
- with the bank, sampler, estimator and PPO fixed, restricting the forward-KL penalty to post-boundary states gives
  no measurable advantage over the full or reduced mixed penalty;
- all three preserve about +1 point of normal-start success at 250k in this regime;
- the gain comes through completion after the boundary;
- gains in boundary-state competence do not necessarily appear as normal-start success within the budget.

**Costs (start ledger 158,314,282; budget 130M).**
- Spent 97,351,286 (74.9% of the budget):
  - A3 88,138,774 (ceiling 103M; data, tests and canary included);
  - calibration 1,475,592 and pilot 7,601,832 (development 9,077,424; ceiling 15M);
  - final tests 63,782.
- The 12M protected reserve was not used.
- Every batch was under its conservative cost: A3 seeds about 0.92, pilot about 0.84.
- No failures, retries or exclusions. Final suite 289 passed, 3 skipped.

## F23 — Interpretation corrections (2026-11-01c; owner instruction section 3; before A4)

No result, interval or verdict changes. Wording corrected in REPORT (headline and section Q, marked
"corrected 2026-11-01c"); F19-F22 stay as written and are read with these corrections.
- **A3 H1 (F19).** The prespecified result stays "supported": +0.0106 [+0.0019, +0.0193]. That t-interval is
  conditional on the evaluated panel of 128 a3_final layouts. Under broader layout uncertainty the crossed seed x
  layout bootstrap [-0.0014, +0.0235] includes 0, so the effect is not resolved for new layout panels.
- **Allocation (F19, F22).** "The state restriction is not needed" and similar categorical wording are replaced by:
  no superiority of the suffix restriction over the full or 0.75x mixed penalty was demonstrated at the tested
  strengths (C-D, C-E within about ±0.01). The prefix-only arm (B) was a weak manipulation.
- **K1 in the pilot (F21).** Access was at its ceiling (q about 1), not success: P1 about 0.71 leaves room.
- **Pilot competence (F21).** Fixed-bank boundary-entry competence improved without a resolved normal-start effect.
  This does not establish that transfer will occur with more training. A4 tests that possibility.
- **Decomposition (F19, F22).** The access/completion split is descriptive. "Acts mainly through completion after
  arrival" is replaced by "most of the difference fell in the completion term"; no causal attribution to a skill.

## F24 — A4 confirmatory result (2026-11-02; owner instruction 2026-11-01c; Amendment 6)

Design as frozen: K=3, BC rho 0.2 / 8,000 updates, seeds 70-89 (20, all kept). A = ordinary PPO and C = suffix-only
preservation (effective 0.0075) were forked from the same post-probe state per seed. Normal starts: 256 a4_final
layouts x 2 attempts, common to all seeds, arms and endpoints. The analysis was blinded until 20/20. The 40 branch jobs
completed without pauses or retries, and the state hashes were checked. `tools/verify_a4.py` recomputed everything
independently; all checks agree and it found no problems.

- **H1 (primary), d = P1(C) - P1(A) at 1,001,472:** +0.0047, 95% t [-0.0152, +0.0246], p 0.63, 11/20 positive, seed
  SD 0.042. Exact sign-flip p 0.64. **Not supported.** The interval excludes ±0.03 and ±0.05: under the
  panel-conditional t, a benefit of 0.03 or more at 1M is incompatible with the data. Sensitivity: the crossed seed x
  layout bootstrap gave [-0.020, +0.029]; the layouts-only bootstrap gave [-0.007, +0.017].
- **H2 (gated):** not tested, because H1 is not supported. An increasing benefit is not supported. Descriptive:
  d(1M) - d(250k) = -0.015 [-0.040, +0.009], p 0.21.
- **d by endpoint (secondary, descriptive):**
  - E250: +0.020 [+0.003, +0.037], p 0.024 (consistent in direction and size with A3, +0.011).
  - E500: +0.012 [-0.004, +0.028].
  - E1M: +0.005.

  The estimate fell with longer training.
- **Arm means of P1 (A / C):**

  | Endpoint | A | C |
  |---|---|---|
  | E250 | 0.186 | 0.206 |
  | E500 | 0.262 | 0.274 |
  | E1M | 0.390 | 0.395 |

  The post-probe median was 0.121. Both arms more than tripled P1, mostly through access: q rose from 0.21 to
  0.61. r rose from about 0.54 to 0.64.
- **Access and completion (C - A):**
  - E250: q +0.027 [+0.003, +0.051].
  - E500: r +0.025 [+0.004, +0.046].
  - E1M: q +0.005 [-0.011, +0.020] and r +0.004 [-0.021, +0.029].

  The decomposition gave the following terms (descriptive, not mediation, defined for 20/20):

  | Endpoint | Access term | Completion term |
  |---|---|---|
  | E250 | +0.014 | +0.006 |
  | E500 | +0.004 | +0.008 |
  | E1M | +0.002 | +0.002 |
- **Planner-entry bank versus actual-arrival bank (C - A):**

  | Endpoint | Entry bank | Arrival bank |
  |---|---|---|
  | E250 | +0.035 [+0.003, +0.067] | +0.024 [+0.000, +0.047] |
  | E500 | +0.030 [+0.010, +0.050] | +0.019 [-0.006, +0.044] |
  | E1M | +0.016 [-0.001, +0.033] | -0.006 [-0.026, +0.014] |

  Relative to pi0, the changes at E1M were:
  - entry bank: A +0.015, C +0.031;
  - arrival bank: A +0.061, C +0.055.

  The arrival-bank gains in both arms were larger than the entry-bank gains. The preservation advantage on planner
  entry states persisted longer than on actual-arrival states. It did not show up in normal-start success at 1M.
- **Manipulation activity.** Suffix anchor KL in arm A rose to 0.088, then 0.126, then 0.166 (per interval). In arm C
  it stayed at 0.055, then 0.066, then 0.077. Prefix anchor KL was the same in both arms (0.13 to 0.23). The applied
  penalty was small (0.0004 to 0.0006 per update). Entropy, suffix visitation (7.4% to 16.4% of steps) and batch
  successes (2.1 to 5.4 per rollout) were similar in both arms. The preservation constraint held the suffix policy
  closer to BC throughout. Ordinary PPO reached the same normal-start success without it.
- **Outcome pattern (descriptive, not a unique explanation):** early benefit, then catch-up. Ordinary PPO gained more
  after 251,904. Other explanations remain possible: the constraint limits later suffix improvement, or the E250
  difference was partly noise. These data do not separate them.
- **Arrival timing and inventory:** mean arrival time tau and remaining time were similar in both arms (tau 76 and
  remaining time 68 at E1M). The inventory at arrival was the yellow key in all but two arrivals.

## F25 — A4 cohort, costs, interruptions and recommendation (2026-11-02)

- **Cohort.** BC at 8,000 met all calibration targets in 3/20 seeds. Per target:
  - K3 access 20/20, K3 room 20/20, K3 entry 17/20;
  - K1 access 20/20, K1 entry 17/20, K1 room 6/20.

  The K1 room failure means K1 P1 exceeded 0.60 (mean 0.624). The cohort does not fully match the intended profile,
  so A4 tests the fixed rho 0.2 / 8k procedure, not the calibrated profile. On the K=3 margins that the online phase
  uses, the profile mostly held. pi0 medians (a4 roles): q 0.148 (0.031 to 0.289), entry 0.615, arrival bank 0.596,
  P1 0.082. Post-probe medians: q 0.215, entry 0.561, arrival bank 0.565, P1 0.121.
- **Cohort stability (descriptive).** d(1M) was +0.006 in the 17 seeds that met the K3 entry target and -0.003 in the
  other 3. Its correlation with pi0 q across seeds was -0.03. By pi0 q halves, d(1M) was -0.004 (low) and +0.015 (high).
  No subgroup was prespecified, and none is claimed.
- **Costs.** 55,727,013 of 70M (79.6%). The ledger is now 311,392,581.

  | Item | Actions |
  |---|---|
  | Data | 110,066 |
  | Arrival bank | 71,265 |
  | Tests | 298,334 |
  | 20 seed batches | 55,054,684 (mean 2.75M each; 91-95% of the conservative 2.97M) |
  | Final tests (306 passed, 6 skipped) | 63,782 |

  Protection was never used. The planned allowance of 1,001,472 continuation actions per branch and all required
  evaluation artifacts are complete.
- **Interruptions.** There were none. The battery stayed at 82-85% on AC, and the guard never paused. The first
  final-tests submission was refused by the runner because the tree was dirty: the analysis outputs were uncommitted.
  It used 0 actions and was resubmitted after a commit. One push got a GitHub 500 error and succeeded on retry. The
  verifier needed a JSON serialization fix (numpy bool), with no change to any metric.
- **Recommendation (decisive).** Do not adopt suffix-only preservation as a method for improving final normal-start
  success in this setting. At 1M actions its effect is +0.005 [-0.015, +0.025], and any benefit of 0.03 or more is
  incompatible with the data. The early advantage (+0.020 at 250k here; +0.011 in A3) is at most a modest,
  transient speed-up that ordinary PPO catches up with. Do not extend A4. Do not build an RQ2 per-condition selector,
  because no condition has a resolved long-run benefit. If any further work is funded, it should target access (q),
  which drove most of the improvement in both arms, rather than preservation of post-boundary behaviour.

## F26 — Remaining A4 interpretation corrections (2026-11-02; owner instruction section 2; no new actions)

The A4 primary comparison (F24) is unchanged.
- **Learning gain.** F24 and REPORT S compared the post-probe median (a4_select panel) with the E1M mean (a4_final)
  as a learning gain. That comparison mixes panels and summary statistics and is withdrawn.
- **Within-panel learning.** Source: `reports/a4/longitudinal.md`. The panel is a4_final, attempt-pooled, with means
  over 20 seeds and 95% t-intervals.

  | Arm | p (E250 → E500 → E1M) | q at E1M | r at E1M |
  |---|---|---|---|
  | A | 0.186 → 0.262 → 0.390 | 0.606 | 0.635 |
  | C | 0.206 → 0.274 → 0.395 | 0.610 | 0.639 |

  For A, the change from E250 to E1M was +0.204 [+0.178, +0.230]. Its exact decomposition gives an access term of
  +0.162 [+0.141, +0.183] and a completion term of +0.042 [+0.028, +0.055]. This is descriptive, not mediation.
- **Failure accounting.** At E1M, failures before the boundary were 0.63 [0.58, 0.68] of all failures in A. This is
  accounting. It does not show that any access intervention would recover those failures.
- **Cohort.** The "3/20 met all targets" statement in F25 is not a reason to discount A4. The failures of the full
  profile were K=1 (room 6/20), and A4 trained online only at K=3. On the K=3 targets, access was met in 20/20 seeds,
  entry competence in 17/20 and room in 20/20; all three were met in 17/20.
- **Preservation.** Suffix preservation may give a small early advantage (+0.020 at 251,904). Its long-budget benefit
  in this test was +0.005 [-0.015, +0.025]: unresolved, and bounded below 0.03.

## F27 — Reset-placement pilot and the frozen gate (2026-11-02; owner instruction 2026-11-02 sections 4-7; Amendment 7 D)

This is a development comparison (6 seeds, 90-95). It is not confirmatory evidence. Sources: `reports/p5/pilot.md`,
`reports/p5/pilot_summary.json`, `reports/p5/gate.json`, `reports/p5/gate_verification.json`.
- **Design as frozen.** Every seed used joint BC (rho 0.2, 8,000 updates) and a K=3 probe, then four branches of
  501,760 continuation actions each:
  - A: ordinary PPO.
  - B: post-boundary resets.
  - C: static uniform module-entry resets.
  - D: backward curriculum (module 3, then 2, then 1, then normal).
  Assisted starts used alpha 0.25 during the first 376,320 actions and stopped after that. Evaluation was on p5_eval
  (64 K=3 layouts × 4 attempts) plus a fixed entry bank. All 24 branches finished. There were no problems, retries
  or exclusions.
- **Normal-start success P1** (means over 6 seeds):

  | Arm | P1 @251,904 | P1 @501,760 | q @501,760 | finishable q | r | entry bank | assisted-step fraction |
  |---|---|---|---|---|---|---|---|
  | A | 0.170 | 0.213 | 0.420 | 0.364 | 0.488 | 0.584 | 0 |
  | B | 0.183 | 0.221 | 0.441 | 0.391 | 0.487 | 0.619 | 0.072 |
  | C | 0.179 | 0.225 | 0.460 | 0.406 | 0.467 | 0.600 | 0.162 |
  | D | 0.165 | 0.241 | 0.467 | 0.413 | 0.493 | 0.603 | 0.162 |
- **Paired P1 contrasts at 501,760** (seeds 90..95; mean, 95% t with df 5, positive seeds):

  | Contrast | Per seed | Mean [95% t] | Positive |
  |---|---|---|---|
  | B − A | −0.039, +0.062, +0.020, +0.004, +0.035, −0.035 | +0.008 [−0.034, +0.050] | 4/6 |
  | C − A | −0.035, +0.035, +0.039, −0.047, +0.047, +0.031 | +0.012 [−0.032, +0.055] | 4/6 |
  | D − A | +0.016, +0.047, +0.055, −0.008, +0.023, +0.035 | +0.028 [+0.004, +0.052] | 5/6 |

  At 251,904 the contrasts were +0.013 (B), +0.009 (C) and −0.005 (D). All three intervals include 0.
- **Gate decision (exact).** The frozen rule needs a mean advantage of at least 0.05 at 501,760, positive in at least
  4/6 seeds, passing checks, and a confirmation that fits the budget. No method qualified. Checks passed, and the
  confirmation (36,356,960 conservative) would have fit. The failure was on the size criterion: the largest mean was
  D at +0.028. The independent recomputation agrees. **Selected: none. The confirmation (seeds 96-115) was not run.**
  No doses, schedules or seeds were added (section 7).
- **Secondary measures at 501,760** (paired m − A; descriptive, development):
  - **Access q:** B +0.021 [−0.066, +0.109]; C +0.040 [−0.024, +0.104]; D +0.048 [−0.003, +0.098]. At 251,904,
    q was higher for C (+0.053 [+0.012, +0.095]) and D (+0.047 [+0.001, +0.092]).
  - **Completion after arrival r:** B −0.001, C −0.021, D +0.005. No arm changed it clearly.
  - **Fixed entry bank:** B +0.035, C +0.016, D +0.019. All intervals include 0. No arm lost later-stage competence.
  - **Room progress:** reach rates for modules 1/2/3 were A 1.00/0.92/0.57 and D 1.00/0.92/0.60. Door-open rates
    were A 0.93/0.58/0.42 and D 0.92/0.61/0.47.
- **Allocation (training).** Assisted share of continuation steps: B 0.072, C 0.162, D 0.162. Training success on
  assisted starts: B 0.70 (post-boundary states are near the goal), C 0.28, D 0.29. Training success on normal
  starts: A 0.146, B 0.164, C 0.167, D 0.167. Training-time rates differ in state mix. They are not evaluation
  measures, and they are not pooled with them.
- **Reading.** Module-entry starts (C, D) moved access up by about 0.04-0.05 on average. Completion after arrival
  did not change, so the P1 gain was at most about 0.03. The pattern fits a small access effect. It is far smaller
  than the headroom in the diagnostics (reference 1 − P1 = +0.31 at the A4 final checkpoints). With 6 seeds it is
  not resolved. D was the only arm whose P1 interval excluded 0. That interval is a development estimate among
  three comparisons, with no multiplicity control, and it is below the prespecified size.
- **Interpretation limits** (section 9). Assisted starts change the training state distribution, the reward
  exposure and the update mix together. They do not isolate exploration. q and r come from a fixed panel, and the
  identity p = q × c is not assumed for a fixed bank. No novelty claim is made. The base levels are not comparable
  to A4 (different seeds and panel).

## F28 — Diagnostic synthesis, costs, interruptions and recommendation (2026-11-02; owner instruction section 11)

- **Diagnostics** (A4 arm 00, seeds 70-73; probe and final checkpoints; d5_trace 64 K=3 layouts × 2; DECISIONS
  2026-11-02). At the final checkpoints:
  - **Arrivals are mostly finishable.** Certified impossible: 3-6% of attempts. Unresolved: 0. Feasible arrivals
    completed at r = 0.63-0.80.
  - **Access is the binding stage.** Reference 1 (planner prefix, learned suffix) was 0.73-0.79, against P1 of
    0.27-0.58. Reference 2 (learned prefix, planner suffix from the actual arrival) equals finishable q (0.44-0.72).
  - **Where the failures are.** Pre-boundary failures ended mostly in the middle module (0.11-0.41 of attempts) and
    in the last module (0.09-0.10).
  - **What failed attempts look like.** Per failed attempt: 9-23 toggles on a locked door and 38-61 no-ops; the
    pose-repeat fraction was 0.61-0.67. 26-42% of failed attempts picked up a wrong key at least once.
  - **Caveat.** This is accounting on a traced sample, not causal attribution.
- **Synthesis.** The diagnostics showed large access headroom. Reset placement (B, C, D) at alpha 0.25 for 376,320
  actions captured only a small part of it. Each module-entry start gives the agent practice in a module from its
  entry. Failed normal-start attempts mostly loop at a locked door, often after holding a wrong key. A reasonable,
  untested explanation is that more practice from module entry does not fix that error. The diagnostics do not
  separate the key choice from door navigation as the binding decision.
- **Costs** (programme ledger, 70M budget from 311,392,581; `tools/run_program5.py --status`):

  | Phase | Actions |
  |---|---|
  | Preparation: data r5-v1 104,251 (includes planner trajectories and entry banks); tests 458,042; local tests outside the runner and ledger adjustments (A4 smoke gap 74,997) | 715,495 |
  | Diagnostics: failed batch 20,498; rerun 199,824 (certification replays 10,019); local tests and adjustments (p5 local smoke 84,711) | 331,554 |
  | Pilot canary s90 | 2,636,241 |
  | Pilot seeds 91-95 (2.59-2.64M each; 83-85% of the conservative 3.11M) | 13,088,800 |
  | Final tests (308 passed, 10 skipped) | 63,782 |
  | **Total** | **16,835,872 (24.1% of 70M)** |

  The confirmation reserve (36.36M) and the protected 8M were not used. Ledger total: 328,228,453.
- **Failures, interruptions and exclusions.** One deterministic failure occurred: diagnostics batch
  20261102T102002-57224 hit an arrival with no remaining time. It used 20,498 actions (counted). Certification was
  fixed (now "impossible"), a test was added, and the rerun got a new run ID. The battery guard never paused (87-90%,
  AC). There were no retries and no exclusions. Every seed was kept.
- **Recommendation (decisive).** Do not adopt post-boundary, static module-entry or backward-curriculum reset
  placement for normal-start success in this setting. None reached the prespecified 0.05 at 501,760. The best
  development estimate (D, +0.028) is small compared with the measured access headroom. Do not add doses, schedules or
  seeds to these methods.
- **Proposed next question (not launched).** Which decision inside the module limits access: key choice, or reaching
  and opening the correct door? A cheap counterfactual can answer this before any training intervention, with
  about 0.3-0.5M evaluation actions:
  - Use the frozen A4 and pilot checkpoints.
  - Correct only one sub-decision with the planner, either the key pickup or the door approach.
  - Measure the change in P1 and q under the same clock accounting.

  Only if one sub-decision bounds a gain of 0.05 or more should a targeted training method be designed and gated.
  This needs a new owner instruction.
