# Protocol freeze — M4 core confirmation (RQ1)

Frozen 2026-10-30, before any confirmation layout, bank or outcome exists. Evidence used: development
findings F1-F7 only (`research/FINDINGS.md`). The manuscript's Preliminary experiments were not used.
Manuscript SHA-256 `38326ef009986ea7a1c3e2e5a68492977952ad2a957a03914bd8557c596f92b4`.
This file is fixed by the commit that adds it. Later changes go in a dated amendment section below,
with a reason, and never after confirmation outcomes have been read.

## 1. Task and splits

- Task `src/bc2rl/task.py`: 21 x 9 canvas, K in {1, 3} prerequisite rooms, common suffix, prefix slack
  24, suffix allowance 80, H_x = L_prefix + 24 + 80, time scaled by H_NORM 200. Reward 1 on delivery only.
- Split registry SHA-256 `1c2af199e44fc2d8cf1293bd227915d0bf8c223f4dcb705492eaff88661e0c6c`
  (`src/bc2rl/splits.py`; same `registry_counts` as dev-v2).
- Confirmation data: dataset `conf-v1` (`experiments/m4/data-conf-v1.json`), generated after this commit.
  It regenerates the dev-v2 roles and adds `conf_final` (32 layouts per K) and `conf_bank` (64 snapshots
  per K, 50/25/25 entry/retrieval/carrying, matched across K). `conf_select` stays ungenerated (RQ2).
  **Gate:** `traj_*.npz` for bc_train, bc_val, reset_donor, anchor_donor and `banks_index.npz` must be
  byte-identical (SHA-256) to dev-v2. If not, stop and report; do not run M4.

## 2. BC (fixed rule from F1)

`src/bc2rl/bc.py`, `experiments/m4/bc-v1.json`: Adam lr 3e-4, batch 256, K-balanced sampler, no
label smoothing. Early checkpoint = 4,000 updates, extended = 16,000, from one run per seed.
**Replicate seeds 10, 11, 12, 13, 14** (new; seeds 0 and 1 were development). BC evaluation uses bc_val
and dev_bank only.

## 3. PPO, probe and arms (F3, F5, F6)

`src/bc2rl/rl.py`, `experiments/m4/conf-v1.json`. Separate actor and critic. 16 envs x 128 steps,
4 epochs, minibatch 512, actor lr 3e-5, critic lr 3e-4, entropy 0, clip 0.2, gamma 1, GAE 0.95, grad
clip 0.5, batch advantage normalization. Critic pre-fit on 16k pi0 actions with early stopping.
Probe: 50,000 ordinary-PPO actions; probe seed = BC seed. The full post-probe state is hashed and
copied into all four arms.

| Arm | Starts | Preservation |
|---|---|---|
| 00 | normal | none |
| 10 | alpha* = **0.25** demonstration-state starts (entry/retrieval/carrying 0.5/0.25/0.25) | none |
| 01 | normal | forward KL to pi0, lambda* = **0.01**, anchors 25% prefix / 75% suffix |
| 11 | alpha* = 0.25 | lambda* = 0.01 |

alpha* and lambda* were chosen by the prespecified M3 rule (DECISIONS, 2026-10-30).

**Endpoint: 250,000 continuation actions per branch** (executed actions; 251,904 = 123 updates of 2,048).
Reason: on the remaining budget, 500k at five seeds costs ~50M actions and does not fit beside a 20%
reserve; project.md says to shorten the endpoint before reducing replication. Development curves show
arm 00 still rising at 250k (F6), so results describe a fixed 250k budget, not convergence.

## 4. Matrix

5 seeds x K {1, 3} x BC {4k, 16k} = 20 forks; 20 probes and 80 branches. Device MPS, one job at a time.
MPS runs are not bitwise reproducible (F5, F7); the paired design and seed replication carry the
inference. Job order is shuffled with a fixed seed recorded in the batch file.

## 5. Evaluation

All evaluation uses common random numbers (eval_seed 939000; bank seed 939001) and the same layouts,
snapshots and attempt seeds for every arm.
- Final (primary): `conf_final`, 32 layouts per K x **16** sampled attempts per branch.
- Final competence: `conf_bank`, 64 snapshots per K x **4** attempts.
- pi0 and post-probe: conf_final 32 x 4, conf_bank 64 x 4 (delta-c).
- Curves at 126,976 and 251,904 actions: 32 x 2 and bank 64 x 1. Descriptive only.
- Greedy behaviour is not evaluated.

## 6. Outcomes and estimands

Primary outcome Y_ab = final normal-start P1 (mean over layouts of z/n). For each seed, a contrast is the
equal-weight mean over the four strata (K x BC checkpoint). The estimand is the mean over seeds.
- **Primary contrasts (family of 3):** reset Y10-Y00; preservation Y01-Y00; combined Y11-Y00.
- **Secondary:** interaction (Y11-Y01)-(Y10-Y00); Y11-Y10; Y11-Y01; the same contrasts in c, q, C4,
  R4; P(success | arrival) where arrivals exist; per-stratum contrasts.
- Descriptive diagnostics: pi0 p/q/c, delta-c, arrival times, training successes, anchor KL, PPO KL.

## 7. Uncertainty

- **Primary interval:** t-interval over the 5 seed-level contrasts (df 4).
- **Companion interval:** crossed cluster bootstrap. Resample seeds (5) and evaluation layouts (32 per
  K) independently, keep each seed's four arms and both checkpoints together, 10,000 replicates,
  percentile, RNG seed 20261031. Episode-only intervals, if shown, are labelled as such.
- Both intervals are reported for every contrast. A directional claim needs both 95% intervals to
  exclude 0. No multiplicity correction; claims are limited to the three primary contrasts, and
  everything else is descriptive.

## 8. Decision thresholds

Smallest effect of interest delta = **0.05 P1** (project.md planning value). For each primary contrast:

| Verdict | Condition |
|---|---|
| Useful benefit | both 95% lower bounds > 0 and point estimate >= 0.05 |
| Benefit below the useful threshold | both 95% lower bounds > 0 and point estimate < 0.05 |
| Harm | both 95% upper bounds < 0 |
| Practically equivalent | 90% t-interval inside [-0.05, +0.05] (TOST at 5%) |
| Inconclusive | none of the above |

A practical-equivalence verdict and a benefit-below-threshold verdict can both apply; report both.
Per-stratum results (5 seeds each) are descriptive. A per-stratum statement such as "reset helps at
K=3" is labelled exploratory and needs its own t-interval to exclude 0.

**Precision check (planning, development data).** Paired fork-level contrast SD 0.04-0.06 (F7); run-to-run
SD 0.027. If strata are independent, the seed-level SD is ~0.025 and the SE over 5 seeds is ~0.011. That
gives a 95% half-width of ~0.03 and roughly 80% power for an effect of about 0.04. Equivalence at ±0.05 can be
shown when |estimate| is below ~0.025. Sample sizes are not changed after final outcomes are seen.

## 9. Budget and stop rules

Used at freeze: 28.69M of 80M actions (35.9%), 3.25 h of batch wall time. M4 estimate: ~32M (data
replay ~1M, BC evaluation ~0.9M, probes ~2.5M, 80 branches x ~0.345M). Projected total ~61M. A reserve
of at least 10.3M (20% of the remaining 51.3M) is kept for audit and failures. **Stop rule:** no new
submissions once the ledger passes 72M; report instead.

## 10. Failures and missing data

- A deterministic failure gets a code fix and a new run ID. A verified transient infrastructure failure
  gets one documented retry. No seed, stratum or arm is dropped for its result.
- A fork whose four arms are not hash-matched is excluded from contrasts and reported.
- Missing conditional statistics (no arrivals) are reported as missing, never as zero.

## 11. RQ2

Development evidence shows no intervention separating from arm 00 (F6, F7), and the remaining budget
after M4 (~19M) cannot fund the expanded held-out-condition design. M5 is therefore planned as a costed
proposal unless M4 shows reproducible, useful heterogeneous effects. Even then, an amendment from the
owner is needed to fund it.

## 12. Audit

After M4: hash check of all forks; independent recomputation of P1/C4/R4/c from `attempts_final.jsonl`
for a random sample of 8 branches (RNG seed 20261031); per-bin bank counts; ledger and wall time.

## Amendments

### Amendment 1 — 2026-10-31 (APPROVED by the owner on 2026-10-31, with Amendment 2)

Approval: the owner chose option A and added the 500k endpoint (verbatim at the end of
`mac-agentic-engineering/project.md`). The text below is as proposed. Where Amendment 2 differs
(A3 endpoint, A6 multiplicity, A7 planning table, A8 budget), Amendment 2 replaces it.

Basis: the pre-M4 development campaign (DECISIONS 2026-10-31; FINDINGS F8, F9). Sections 1-12 above stay
as frozen on 2026-10-30. Where this amendment differs, it replaces them once approved. No confirmation data
or outcome was used.

**A1. Task, data roles, seeds.** Task, H_x rule, dev-v2 training roles and BC seeds 10-14 are unchanged.
- `conf_final` count goes from 32 to 64 layouts per K. `conf_final` is last in the role order, so this only
  appends layouts; all earlier roles and the first 32 `conf_final` layouts are unchanged (test
  `test_enlarging_last_role_keeps_every_earlier_entry`). The new registry hash is recorded at generation.
- pi0 and post-probe diagnostics move to `conf_select` (`diag_role`; declared use "confirmation
  selection/diagnostic normal starts"). Final layouts are then used only for the curve-free final
  evaluation.
- The training-role byte-identity gate of section 1 still applies.

**A2. Checkpoints and pipeline.** BC rule and PPO settings are unchanged (section 3), alpha* 0.25, lambda* 0.01.
Each branch saves its complete hashed learner state at 251,904. That allows a separately approved later
extension of the same trajectories without a restart. It does not change the endpoint.

**A3. Endpoint.** Kept at **251,904** continuation actions. Reasons (F9):
- From 251,904 to 501,760, P1 rose by +0.065 on average (K=3, extended BC, 2 seeds), but no paired contrast
  separated: estimates -0.04 to +0.06, all within-seed layout intervals include 0.
- Training-path variation is large (same-fork repeat SD 0.048). Independent seeds, not length, limit
  precision.
- A 500k full matrix does not fit (option B in the report).

**A4. Evaluation sizes** (same attempt totals as the freeze; layouts doubled):

| Point | Normal starts | Bank |
|---|---|---|
| pi0, post-probe | conf_select 64 x 2 | conf_bank 64 x 4 |
| 126,976 (descriptive curve) | conf_select 64 x 1 | conf_bank 64 x 1 |
| 251,904 final (primary) | **conf_final 64 x 8** | conf_bank 64 x 4 |

Reason: one policy's P1 has a Monte Carlo SE of 0.020 at 32 x 8, but a layout-sampling SE of 0.064
(per-layout SD 0.36; F8). The layouts are shared across seeds, so their component does not average out
over seeds. 64 layouts x 8 attempts costs the same as 32 x 16. C4 and R4 use n = 8 per layout.
Secondary: P(success | arrival) and arrival remaining-time quantiles from the same attempts. The
arrival-state bank (E3b) stays a development diagnostic.

**A5. Hypotheses and estimand.** As section 6: three primary contrasts, two-sided, no expected direction.
Development data gave no directional evidence. Estimand: mean over seeds of the equal-weight mean over the
four strata.

**A6. Uncertainty, multiplicity, equivalence** (replaces sections 7-8 where different):
- Pointwise: a 95% t-interval over the 5 seed-level contrasts (df 4) for every contrast, plus the crossed
  seed x layout cluster bootstrap. Both are reported.
- Directional claims: only for the three primary contrasts. A claim needs the Holm-adjusted t-test (family
  of 3, alpha 0.05) to reject and the bootstrap 95% interval to exclude 0.
- Practical equivalence: TOST at ±0.05 per contrast, i.e. the 90% t-interval inside [-0.05, +0.05].
- Verdict labels as section 8, with "useful benefit" requiring the Holm-adjusted directional claim and an
  estimate >= 0.05. All secondary and per-stratum results are descriptive.

**A7. Precision planning** (replaces the withdrawn section 8 statement). These are scenarios, not power
claims. sigma = SD of one stratum's paired contrast from training-path and evaluation noise; development
gives about 0.05 (same-fork path repeats 0.048; M3 fork contrasts 0.04-0.06; 8 values each, so sigma could
plausibly be 0.035-0.09). rho = within-seed correlation of the four stratum contrasts (shared BC run). The
layout component shared across seeds is not included.

| rho | seed-level SD | SE (5 seeds) | 95% half-width | effect with 80% power | equivalence shown if abs(estimate) < |
|---|---|---|---|---|---|
| 0 | 0.025 | 0.011 | 0.031 | 0.042 | 0.026 |
| 0.25 | 0.033 | 0.015 | 0.041 | 0.055 | 0.018 |
| 0.5 | 0.040 | 0.018 | 0.049 | 0.066 | 0.012 |

Formulas: seed SD = sigma x sqrt((1 + 3 rho) / 4); half-width = 2.776 SE; 80%-power effect =
(2.776 + 0.941) SE; equivalence bound = 0.05 - 2.132 SE. With sigma = 0.09, every value scales by 1.8.
Interpretation: M4 can probably detect effects of about 0.05-0.07. It can show equivalence at ±0.05 only if
the true effects are near 0.

**A8. Budget controls** (replace the 72M rule).
- Conservative M4 cost: 32.95M (per-job maxima; A4 keeps attempt totals). Ledger at amendment: 36.82M,
  including 3.10M for tests run outside the runner. Reserve: 10.26M. Margin: 80 - 36.82 - 32.95 - 10.26 =
  -0.03M, i.e. the reserve would be 10.23M at worst. Measured means give ~31.5M, leaving a reserve of ~11.7M.
- Execution: one batch per seed (BC, 4 probes, 16 branches in a fixed shuffled order). Before each batch:
  ledger + conservative cost of all remaining M4 batches <= 69.77M (80M minus a reserve of at least 10.23M).
  If not, stop and report. Never drop a seed or stratum to fit.
- RL smoke tests run only with `BC2RL_SMOKE=1`, once before the M4 code is launched; their actions are added
  to `research/ledger_adjustments.json`.

**A9. RQ2.** Unchanged: costed proposal only.

### Amendment 2 — 2026-10-31 (in force; owner decision of 2026-10-31)

Owner decision, verbatim: "Don't worry about the cap. Do A but for both 250K as well as 500K." Written before
confirmation data exist; no confirmation outcome has been seen. Amendment 1 stays in force except where this
amendment replaces it.

**B1. Design.** Option A (section 4 matrix: 5 seeds x K {1, 3} x BC {4k, 16k} x 4 arms = 80 branches) on one
trajectory per branch with **two endpoints**: **E250 = 251,904** and **E500 = 501,760** continuation actions
(config `continuation_actions` 500,000 executes 501,760). Each branch is one uninterrupted run; the E250
evaluation does not touch the training streams (evaluation uses its own RNG and environments). Complete
hashed learner state is saved at both endpoints.

**B2. Evaluation schedule** (`experiments/m4/conf-v1.json`; common random numbers, eval_seed 939000, bank
939001; the same attempt seeds at both endpoints, so endpoint changes are paired as well):

| Point | Normal starts | Bank | Use |
|---|---|---|---|
| pi0, post-probe | conf_select 64 x 2 | conf_bank 64 x 4 | diagnostics, delta-c |
| 126,976 | conf_select 64 x 1 | conf_bank 64 x 1 | descriptive curve |
| **E250** 251,904 | **conf_final 64 x 8** | conf_bank 64 x 4 | endpoint |
| 376,832 | conf_select 64 x 1 | conf_bank 64 x 1 | descriptive curve |
| **E500** 501,760 | **conf_final 64 x 8** | conf_bank 64 x 4 | endpoint |

conf_final is used only at the two endpoints.

**B3. Hypotheses and multiplicity** (replaces A6 where different).
- Confirmatory family: the three primary contrasts (reset, preservation, combined) at both endpoints, i.e.
  **6 tests**. A directional claim needs the Holm-adjusted two-sided t-test over the 6 tests (alpha 0.05,
  df 4 each) to reject, and the crossed bootstrap 95% interval to exclude 0.
- Why one family of 6: the two endpoints come from the same trajectories and are both confirmatory;
  separate families would let either endpoint carry a claim at an uncontrolled family-wise error rate.
- Pointwise 95% t-intervals and bootstrap intervals are reported for every contrast at both endpoints.
- Equivalence: TOST at ±0.05 per contrast and endpoint (90% t-interval inside [-0.05, +0.05]).
- Verdict labels as section 8 per contrast and endpoint, with "useful benefit" requiring the Holm-adjusted
  claim (family of 6) and an estimate >= 0.05.
- Descriptive, not confirmatory: the change E500 - E250 of each contrast (per seed, t-interval); every
  section 6 secondary and per-stratum result at both endpoints; D_seed moderation at both endpoints.

**B4. Precision planning** (replaces the A7 table; scenarios, not power claims). Same sigma 0.05 and rho as
A7. Correction to A7: its "80% power" column used the unadjusted critical value 2.776; a Holm claim needs
the first-step critical value. For one true effect among nulls, the first Holm step is the binding one:
t(4) two-sided at 0.05/6 = 4.851 (at 0.05/3: 3.961).

| rho | SE (5 seeds) | 95% half-width | effect with 80% power, Holm 6 | (Holm 3, for reference) | equivalence shown if abs(estimate) < |
|---|---|---|---|---|---|
| 0 | 0.011 | 0.031 | 0.065 | 0.055 | 0.026 |
| 0.25 | 0.015 | 0.041 | 0.086 | 0.072 | 0.018 |
| 0.5 | 0.018 | 0.049 | 0.102 | 0.087 | 0.012 |

80%-power effect = (t_crit + 0.941) SE. With sigma 0.09 every value scales by 1.8. Interpretation: a
confirmatory directional claim needs an effect of roughly 0.065-0.10 P1; smaller true effects will probably
be "inconclusive" or "benefit below the useful threshold" by the pointwise intervals only.

**B5. Budget** (replaces section 9 and A8 budget rules). The owner removed the 80M cap as a stop rule for M4.
Conservative M4 cost from measured per-job maxima:
- Branches: 501,760 train + 2 curve points (K=1 22,453 / K=3 29,042 each) + 2 endpoints at 69,148 / 94,272
  each = 684,962 / 748,388; x 40 each = 57.33M.
- Probes 2.84M (diagnostic attempt totals unchanged by A4); BC evaluation 0.90M; data 0.50M.
- Total **61.57M**. Ledger before M4: 36.82M + test actions (added to `research/ledger_adjustments.json`).
  Projected total ~99M.
- Stop rule: report to the owner, and submit nothing new, if the ledger passes the projected total by more
  than 10% (109M), or if any batch costs more than 1.25 x its conservative estimate. Resource limits
  (4 cores, 6 GiB, 1 job) are unchanged.

**B6. Execution order.** Data conf-v1 -> training-role gate (section 1, plus identical rl_train, dev_eval and
dev_bank layouts; `tools/data_gate.py`) -> RL smoke tests once (`BC2RL_SMOKE=1`) -> one M4 batch per seed,
seeds 10-14 in order (`experiments/m4/seed-s<S>.batch.json` from `make_batches.py`: BC, 4 probes, 16
branches; probe and branch order shuffled with seed 20261031 + S). Section 10 failure rules apply. No seed, stratum, arm or
endpoint is dropped for its result.

### Amendment 3 — 2026-10-31 (in force): R1 focused replication (owner approval of 2026-10-31)

Owner instruction recorded verbatim in `mac-agentic-engineering/project.md` (harness commit `4d4fc31`).
Frozen before any R1 data exist (no r1-v1 dataset, no R1 run). Evidence used: M4 (F10) and the post-M4 audit
(F11). The M4 primary analysis and its conclusions are unchanged by R1, whatever R1 shows.

**C1. Scope.** K=3 only. BC checkpoints early (4,000 updates) and extended (16,000) from one BC run per seed.
Fresh training seeds 15-22 (8). Arms: ordinary PPO `00` (lambda 0) and preservation `01` (lambda 0.01); both
use normal starts only (alpha 0; `experiments/r1/r1-v1.json` sets alpha 0.0 and only arms 00/01 run). The
preservation reference is each seed's own BC checkpoint (pi0 of the fork). Primary endpoint 501,760 post-probe
actions; descriptive checkpoint 251,904. Everything else unchanged from conf-v1/M4: task, model, reward,
horizon, BC config (`experiments/m4/bc-v1.json`, the joint dataset conf-v1 = dev-v2 training roles, K-balanced
sampler; no K=3-only BC), critic preparation, 50k-action probe, PPO settings, anchor bank and anchor rule,
state saves at both checkpoints. No doses, architectures, K=1 or longer endpoint.

**C2. Data and roles.** Dataset `r1-v1` (`experiments/r1/data-r1-v1.json`): every conf-v1 file and layout role
copied unchanged (`base_dataset`); new roles from new namespaces 112-114 (`src/bc2rl/splits.py`, appended at the
end of ROLE_ORDER so no earlier role changes): `r1_select` (64 layouts; pi0/probe diagnostics and curve points),
`r1_bank` (64 bank snapshots, entry/retrieval/carrying 32/16/16 as conf_bank) and `r1_final` (128 layouts; final
panel). K=1 items are generated only because the bank procedure is matched across K; they are never evaluated.
**Gate** (`tools/data_gate.py --r1 data/r1-v1`): dev-v2 training files byte-identical (unchanged-training-data
gate), every conf-v1 file and role identical, r1 role counts as planned for K=3, and zero structure-hash,
generator-seed and suffix-hash overlap of each r1 role with every earlier role (training, development,
confirmation) and with each other; r1_bank bins equal conf_bank bins. If the gate fails: stop, fix, regenerate
under a new dataset id; no R1 training on a failed gate.

**C3. Evaluation.** Final normal starts: r1_final 128 layouts x 4 attempts (512 attempts) per policy, plus the
r1_bank 64 x 4, at 251,904 and 501,760. Curve points 126,976 and 376,832 and the pi0/probe diagnostics: r1_select
64 x 1 (curves) or 64 x 2 (pi0/probe), bank 64 x 1 (curves) or 64 x 4 (pi0/probe). The same panel and the same
attempt-seed schedule (`default_rng([939000, item, attempt])`; bank 939001) for every arm, checkpoint and seed.
C4 and R4 become "any of 4" and "all 4" per layout (descriptive only; less precise per layout than with 8
attempts, while P1 keeps 512 attempts over twice as many layouts).

**C4. Hypotheses and analysis** (`tools/analyze_r1.py`, tests `tests/test_analyze_r1.py`; committed here).
Unit: training seed (n = 8). Per seed i at 501,760: d_early_i = P1(01, early) - P1(00, early);
d_ext_i = P1(01, extended) - P1(00, extended); inter_i = d_early_i - d_ext_i.
- H1: mean d_early = 0. H2: mean inter = 0. Two-sided paired t-tests, df 7; Holm over {H1, H2} at 0.05.
  "Supported" means Holm-adjusted p < 0.05. 95% t-intervals.
- Conditional vs layout inference: the t-test and t-interval treat the frozen 128-layout panel as fixed.
  Layout sampling is addressed by a crossed seed x layout bootstrap (10,000 replicates, RNG 20261101,
  same item indices for every seed, arm and checkpoint) and a layouts-only bootstrap. Bootstrap agreement and
  the exact sign-flip test (256 patterns) are sensitivity checks, not replication and not the decision rule.
- Direction, magnitude and practical importance are reported separately. Magnitude rule for d_early: lower
  95% bound > 0.05 "exceeds the practical threshold"; upper bound < 0.05 "below it"; otherwise "not
  distinguishable from it". No requirement that R1 equal +0.045 or +73%: the M4 estimate came from a post hoc
  selected subgroup and is probably inflated.
- If H1 is not supported: upper bound < 0.0227 (half the M4 estimate) = informative failure to replicate;
  < 0.0453 = excludes the original estimate but not half of it; otherwise inconclusive.
- Interpretation cells: as owner section 6 (both / H1 only / H2 only / neither).
- 251,904: same statistics, descriptive, unadjusted, no claims; no best checkpoint is chosen.
- Secondary, descriptive, by checkpoint and arm: P1; q; P(success | arrival) (undefined with no arrivals, never
  imputed; differences only over seeds where both arms are defined); C4/R4; fixed-bank entry, retrieval and
  carrying and their change from pi0 and the probe on the same bank; arrival timing and inventory; anchor KL,
  training visitation and optimization diagnostics; curves separated by layout role. p = q x r is kept apart from
  bank competence. An access gain is not read as protection of a suffix skill.
- The M4 post hoc estimate (+0.0453 [0.0353, 0.0554], 5 seeds, 64 x 8) is shown in a separate block, never pooled.
- Exclusion: a seed with a missing branch or a fork-hash mismatch is reported and excluded from the paired
  tests, never replaced; the report then states that the design is incomplete.

**C5. Power and precision** (`tools/power_r1.py` -> `reports/r1/power.json`, `power.md`; M4 inputs only).
Seed SD of the paired preservation effect over the 8 M4 cells: min 0.0081 (the selected K=3/early E500
subgroup, unusually small and not the planning value), median 0.0281, max 0.0572. Results (P(H1 supported) under
Holm-2, conditional on the panel, rho 0): true +0.045 -> 0.97 (median SD), 0.42 (max SD); +0.03 -> 0.62 / 0.17;
+0.0227 -> 0.38 / 0.11. Adding the M4 layout component (panel SE at 128 layouts 0.002 corrected, 0.007 raw)
changes these little. Approximate 80%-power effect at the Holm worst case: 0.037 (median SD), 0.076 (max SD).
So 80% power is not promised: R1 is well powered only if the true early effect is near the M4 estimate and the
seed SD is not much above the M4 median.

**C6. Budget and admission** (`tools/run_r1.py`). Hard incremental budget 28.4M environment actions for all R1
work (data replay, tests, diagnostics, training, evaluation, failures and retries). It supersedes the 109M
submission stop line for R1 only. Starting ledger total **93,199,203** (`tools/ledger.py`, before any R1 job).
Per-job conservative cost = M4 K=3 maxima with evaluation parts x 1.10 (new panel); expected = M4 means:
BC 166,032 / 147,934; probe early 151,898 / 140,824; probe extended 130,078 / 122,151; branch early 746,654 /
715,246; branch extended 696,417 / 668,697. Per seed 3,333,150 conservative, 3,171,900 expected. Total for 8
seeds 26.67M conservative (25.38M expected) + data 0.10M + test-suite runs 0.20M = **26.97M conservative**,
25.54M expected; 1.43M below the budget at the conservative cost. The complete design fits; no shortfall.
Admission before each batch (all of its jobs at once, so every job is admitted with its conservative cost):
spent + conservative(batch) + expected(later planned batches) + audit 0.2M + reserve <= 28.4M, with reserve
2.0M until completion is secure (spent + conservative of everything remaining + audit <= 28.4M). After a batch:
exit 0 and cost <= 1.10 x conservative, else stop and report.

**C7. Execution order.** Freeze commit (this) -> data batch r1-v1 -> gate -> test suite as a runner job
(`experiments/r1/tests.batch.json`; heavy tests and environment checks go through the runner) -> one engineering
canary batch (`canary-s15.batch.json`: r1-bc-s15, r1-probe-K3-u4000-s15, r1-K3-u4000-s15-01-kl0p01; a design
job, kept) -> `tools/r1_canary_check.py` (configs, hashes, counters, telemetry, schemas; prints no outcome) ->
`seed-s15-rest.batch.json` (written after the canary with its batch id) -> seeds 16-22 in order (BC, 2 probes,
4 branches; order shuffled with seed 20261031 + S). Resources: 4 cores, 6 GiB, one job at a time. The canary's
outcome is not read before all seeds finish and is never used to retune or resize.

**C8. Failures and stopping.** Section 10 applies: a deterministic failure gets a fix and a new run ID; a verified
transient infrastructure failure gets one documented retry; no seed is replaced or dropped for its behaviour
(floor performance and zero arrivals are kept). Stop only for execution, correctness, resource or budget
problems, never for interim effects. No change to seeds, lambda, panels or training length in response to
results. Reviews may fix defects, not adapt the design. After R1: stop scientific execution and report.

**C9. Reproduction.** Harness (local only, no remote): branch `mac-host-fixes`, HEAD `4d4fc31` at freeze; the
runner change used since M4 is `b53f29a`. Each batch manifest records project and harness SHAs. The harness
commits are not available remotely, so remote reproducibility is not claimed.

### Amendment 4 — 2026-11-01 (in force): R2 final replication, E1 cross-panel, E2 anchor components

Owner instruction recorded verbatim in `mac-agentic-engineering/project.md` (harness commit `000fd83`). Frozen
before any R2, E1 or E2 data exist. M4's aggregate equivalence result and R1's Holm-2 verdict are unchanged, and no
R2 result can change them. R2 is a new study. It is an RQ1 intervention study, not RQ2 selection.

**A. Authority and budget.** New hard incremental budget: **50,000,000** environment actions for everything under
this instruction (generation, tests, training, diagnostics, evaluation, failures, retries). Start: corrected
ledger total **118,670,430** (`tools/ledger.py` after the R1-audit correction of +128 actions; the agent note in
project.md gave 118,670,302 before that correction). The unused R1 allowance is not added. This replaces the R1
28.4M budget and the 109M M4 submission stop line. There is no wall-time limit; resource limits stay (4 cores,
6 GiB, one job, native MPS under the runner). Allocation ceilings: R2 38M (guidance; R2 may use the reserve for
failures), E1 4M and E2 4M (hard), reserve 4M for validation, failures and completion, audit 0.3M.

**B. Admission** (`tools/run_program.py`, plan `experiments/program/plan.json`). Before each batch, with
committed = conservative cost of every other incomplete R2 batch + audit 0.3M:
R2 batch: spent + conservative(batch) + committed <= 50M. Exploratory batch: spent + conservative(batch) +
committed + 4M reserve <= 50M, its study's spend + conservative(batch) <= 4M, and no R2 batch incomplete (R2
finishes first). After a batch: exit 0 and cost <= 1.10 x conservative, else stop and report.
Conservative per-job costs (R1 early-job maxima; evaluation x 1.10; train exact; warm-up bound 17,100): BC to 4k
95,906; probe 153,954; branch 740,904; per seed 1,731,668; 20 seeds 34,633,360. Data 0.1M, tests 0.1M, smoke
tests 0.3M. E1: 26 policies x 111,548 (hard bound: every episode at its limit) = 2,900,248. E2: 12 x 283,302
(hard bound) = 3,399,624. Projected conservative total 41.84M (+0.3M audit) <= 50M; the complete design fits.

**C. R2 design.** One question: does preservation (lambda 0.01) improve normal-start P1 at K=3 with early BC after
501,760 continuation actions?
- 20 fresh seeds 23-42 (fixed; never reduced, extended or replaced). K=3 only. Early BC (4,000 updates) only.
- BC: unchanged joint conf-v1 dataset, K-balanced sampler, architecture, constant lr 3e-4, batch 256
  (`experiments/r2/bc-r2.json` = bc-v1 with checkpoints [4000]; no lr schedule exists, so the 4k checkpoint
  procedure is unchanged; BC evaluation as before).
- Probe, critic preparation, PPO settings, anchor bank and weights, task, reward, horizon, observation: as conf-v1
  / r1-v1 (`experiments/r2/r2-v1.json` differs from r1-v1 only in dataset r2-v1, roles r2_*, eval seed 949000).
- Arms: 00 (lambda 0) and 01 (lambda 0.01, the original mixed loss), both alpha 0, forked from one hash-verified
  post-probe state. Reference = the seed's own BC checkpoint.
- Data: dataset r2-v1 (`experiments/r2/data-r2-v1.json`) copies every r1-v1 file and role (which include every
  conf-v1 file and role) and appends r2_select (64), r2_bank (64; bins 32/16/16) and r2_final (128) from new
  namespaces 115-117. Gate `tools/data_gate.py --r1 data/r1-v1 --r2 data/r2-v1`: training files byte-identical,
  every earlier role identical, zero structure/seed/suffix overlap of r2 roles with every earlier role and each
  other, r2_bank bins equal conf_bank's. A failed gate stops R2 (fix, new dataset id).
- Evaluation: r2_final 128 K=3 layouts x 4 attempts and r2_bank 64 x 4 at 251,904 (descriptive) and 501,760
  (primary); curves on r2_select (64 x 1) at 126,976 and 376,832; pi0/probe on r2_select (64 x 2) and r2_bank
  (64 x 4). One panel and attempt schedule (`default_rng([949000, item, attempt])`, bank 949001) for every arm
  and seed. States saved at 251,904 and 501,760 (actor, critic, optimizers, RNGs, sampler and in-flight
  environments, counters, pi0), hashed. Remaining time is kept on every restoration.

**D. R2 inference** (`tools/analyze_r2.py`, tests `tests/test_analyze_r2.py`; committed here).
- Unit: training seed (n = 20). d_i = P1(01_i) - P1(00_i) at 501,760. One two-sided paired t-test at 0.05
  (df 19) and its 95% t-interval. R2 data only; M4 and R1 are never pooled into it.
- Decision cells: lower > 0 -> positive effect supported (magnitude: lower > 0.05 "exceeds 0.05"; > 0.03
  "exceeds 0.03"; else "positive; not shown to exceed 0.03"). upper < 0 -> negative effect supported.
  Otherwise not supported: upper < 0.03 -> informative (excludes the 0.03 planning effect); upper < 0.0453 ->
  excludes the M4 estimate but not 0.03; else inconclusive. One-sided p-values against 0, 0.03 and 0.05 are
  reported as descriptive uncertainty only.
- Sensitivity, not the decision: crossed seed x layout bootstrap (10,000, RNG 20261102; same item indices for
  both arms; assumes seeds and layouts exchangeable), layouts-only bootstrap, exact sign-flip (2^20 patterns;
  assumes symmetric d under the null). 251,904 is descriptive.
- Blinding: the script computes no primary statistic, paired difference or arm mean until all 20 seeds are
  complete. Progress checks use execution health only (exit status, counters, finite losses, telemetry).
- Exclusion: a seed with a missing branch, a fork-hash/lineage mismatch or a saved-state hash mismatch after the
  failure policy is exhausted is excluded and reported; the design is then incomplete (`--final-incomplete` only
  after the campaign has ended). Very poor or zero-success seeds are valid and kept.
- Planning effect 0.03 (`tools/power_r2.py` -> `reports/r2/power.md`). It does not replace M4's ±0.05
  equivalence margin. P(lower > 0) at true 0.03: 0.95 / 0.84 / 0.72 / 0.57 for seed SD 0.035 / 0.043 / 0.05 /
  0.06 (normal; heavy-tailed and R1-shaped differences similar). At true 0.03 the chance to show "exceeds 0.03" is
  about 0.025, so an "exceeds" statement needs a larger true effect. No power is computed from R2's observed
  effect.
- Synthesis (separate, descriptive): an R1+R2 precision-weighted mean with an approximate interval and no p-value,
  disclosing adaptive study selection; M4 excluded. Never presented as the confirmatory test.
- If R2 is inconclusive: report and stop. No further replication is scheduled.

**E. Execution order and failure policy.** Freeze commit (this) -> data batch -> gate -> test batch (suite + RL
smoke incl. exact CPU resume) -> runner interruption drill (sleep canary with children, stopped with `mae stop`;
verify status and child cleanup) -> canary (`canary-s23`: r2-bc-s23, probe, branch 01; first planned seed) ->
`tools/r2_canary_check.py` engineering check without outcomes (configs, hashes, counters, telemetry,
schemas, finite losses) -> `seed-s23-rest` (branch 00, written with the canary batch id) -> seeds 24-42 (one batch
each: BC, probe, both branches; branch order shuffled with 20261101 + S) -> E1 -> E2 -> final runner tests ->
independent audit -> report. Code is frozen at this commit; only correctness fixes, each with the affected runs
identified. Failure policy (section 10): a deterministic failure gets a fix and a new run ID; a verified transient
infrastructure failure gets one documented retry. An interrupted job (battery stop, owner stop, crash) is rerun in
full from its latest complete input checkpoint (BC checkpoint -> probe; fork -> branch) under a new batch ID;
partial outputs and their actions are kept. A seed is never replaced and never selected by outcome; an operational
interruption does not change the sample or permit analysis of a subset.

**E1. Cross-panel study (exploratory)** (`src/bc2rl/diag.py crosspanel`, `experiments/crosspanel/`,
`tools/analyze_crosspanel.py`). The saved 501,760 actors of the K=3/early-BC arms 00 and 01 of M4 (seeds 10-14)
and R1 (seeds 15-22), 26 policies, each evaluated on conf_final (64 K=3 layouts) and r1_final (128) with **4
attempts** per layout (the 4M hard bound is 2.90M, so the 4-attempt preference holds; frozen before outcomes) and a
new common eval seed 969000. New records only. Cells: cohort x panel (4). Reported: arm means, paired effect
(mean, seed SD, t-interval, n positive), q, r, C4/R4, the decomposition, cohort and panel contrasts, and
own-panel repeatability against the original records. Exploratory; it cannot attribute residual differences to
subgroup selection, hardware or training seeds.

**E2. Anchor-component experiment (exploratory)** (`experiments/comp/`, `tools/analyze_comp.py`). Forks: the R1
early-BC probes of seeds 15, 16, 17 (fixed rule: the first three R1 seeds). Four contemporaneous branches per fork,
normal starts, PPO settings unchanged, 251,904 continuation actions: 00 (no preservation), 01p (prefix rows only),
01s (suffix rows only), 01 (both = the original loss). Penalty `src/bc2rl/ppo.anchor_penalty`: the same sampled
anchor batch (0.25 prefix / 0.75 suffix weights, batch 128); removed rows are zeroed and the sum is divided by
the full batch size, so the expected penalty is 0.0025 E_prefix KL, 0.0075 E_suffix KL, or both; no
renormalization. Tests: "both" equals the original loss and gradients exactly; prefix + suffix = both; every
arm leaves the action, permutation, anchor and start-sampler RNG states identical (anchor draws use their own
RNG, which no other part of training uses). Evaluation (development-only, frozen): the first 32 K=3 r1_select
layouts x 4 attempts and r1_bank 64 x 2 at 251,904, eval seed 979000; state saved at 251,904. Reported per seed:
prefix, suffix, both and interaction contrasts (01 - 01p - 01s + 00) for P1, q, r, C4/R4, c and bins, the
decomposition, bank change from pi0/probe on the same bank states, anchor KL by stage and applied penalty. Three
seeds: exploratory; a component effect identifies that penalty term's contribution in this implementation, not
a skill or pathway; the 251,904 endpoint does not explain the 501,760 effect.

**F. Stage measurements.** As section 8 of the instruction: p, q, r on normal starts; fixed-bank entry,
retrieval, carrying and mixed c; changes from pi0/probe on the same states; arrival timing, inventory; anchor KL and
penalty; visitation and reward exposure. Effect sizes with uncertainty; no stage ranking by p-values; p = q x c is
never assumed; normal-start values on r2_select are never differenced against r2_final values as learning.
No shaped rewards, demonstration resets, new architectures, larger lambda or other BC depths.

**G. Monitoring.** Battery watch `tools/battery_watch.py` (5-minute checks; below 20% it writes STOP to the
running batch and exits 2). Batch watcher `tools/watch_batch.py` bound to the driver PID and create time. Two-hour
research reviews (session cron). State for a fresh session: `research/STATE.md`, `research/CHECKLIST.md`,
`experiments/program/plan.json`, `tools/run_program.py --status`.

**H. Reproduction.** Harness branch `mac-host-fixes`, HEAD `000fd83` at this freeze (local only). Package versions
`reports/r2/pip_freeze.txt`. Each batch manifest records project and harness SHAs.

### Amendment 5 — 2026-11-01b (in force): A3 anchor-allocation study, initialization calibration, calibrated-regime pilot

Owner instruction of 2026-11-01 (second of that date; verbatim in `mac-agentic-engineering/project.md`, harness
`7ed7285`). Closed studies (M4, R1, Amendment 4: R2, E1, E2) keep their verdicts. This amendment supersedes the
Amendment 4 completion stop and REPORT P8 as a stop rule. Frozen before any A3, calibration or pilot outcome.

**A. Authority and budget.** Hard incremental budget 130,000,000 environment actions from the ledger total
158,314,282 (end of Amendment 4; nothing ran between). Unused earlier allowances are not added. Everything counts:
generation, tests (also local tests outside the runner, through `.mae/unmanaged_actions`), training, diagnostics,
evaluation, failures, retries. Planning allocation: about 3M preparation, about 100M A3, up to 15M calibration +
pilot, about 12M protected for audit, failures and completion. Admission (`tools/run_program2.py`, plan
`experiments/program2/plan.json`): before every batch, committed = conservative cost of all other incomplete
required A3 batches and the final test batch + 0.3M audit; A3/final batches need spent + batch + committed <= 130M;
calibration/pilot batches also hold the 12M reserve, stay within 15M, and start only after every required A3 batch
is complete. After a batch: exit 0 and cost <= 1.10 x conservative, else stop and report. Conservative per job:
A3 BC 95,906, probe 153,954, branch 740,904 (R2 maxima; A3 drops the curve evaluations, so this over-holds);
calibration BC 200,000; pilot probe 153,954, pilot branch 340,000. Required conservative total ~97.3M; pilot ~9.1M.

**B. Focused implementation audit (before any new run).** Checked in source and by tests
(`tests/test_ppo.py`, `tests/test_bc_sampler.py`):
- Stage labels: anchors are the anchor_donor prefix rows then suffix rows of `banks_index.npz`; `is_prefix` marks
  the first block. Stage = environment stage at the saved state (0 = prefix; > 0 = suffix).
- Sampling: each actor minibatch draws 128 anchor rows with replacement, prefix mass 0.25 spread uniformly over
  prefix rows and 0.75 over suffix rows (weights normalised once). Component arms zero the other stage's rows and
  divide by 128 (no renormalisation). The expected penalty equals c_pre E_prefix[KL] + c_suf E_suffix[KL]
  (exact-expectation test).
- Coefficients: base coefficient = config kl_coef (0.01) x arm scale (01w: 0.75); effective (prefix, suffix):
  00 (0, 0); 01p (0.0025, 0); 01s (0, 0.0075); 01 (0.0025, 0.0075); 01w (0.001875, 0.005625); 11s (0, 0.0075).
  Recorded in each branch summary as `kl_coef` and `kl_effective_prefix_suffix`. Test: B + C = D and E = 0.75 D
  in value and in gradient on fixed states and parameters; C with base 0.01 differs from the double-weighted
  0.0075-on-suffix estimator.
- Teacher: pi0 = the original BC checkpoint stored in the fork (`st["pi0"]`), parameters frozen; reference
  log-probabilities computed once under `torch.inference_mode()` and cloned (no gradient path).
- KL: exact forward categorical KL(pi0 || pi_theta) over the 7 actions (test against torch).
- Actor/critic: separate networks and optimisers; the penalty enters only the actor loss; value targets exclude it.
- RNG streams: anchors `np_rng([seed, 11])` (used only for anchors; same draws in every arm); start sampler
  three streams `[seed, 31, i]` (coin, layout, bank); action sampling and minibatch permutation share
  `torch_gen(seed)`. Without `target_kl` (not set) every arm consumes that generator identically, so the k-th action
  uniform is the same in every arm forked from one state. This is a shared, not an independent, stream; it is valid
  and arm-invariant, and it is not changed (changing it would break comparability with R2/E2). No defect.
- Fork/checkpoint state: actor, critic, both optimisers, torch_gen, np_rng, sampler RNGs, environment snapshots,
  assisted flags, counters and pi0; all enter the state hash; branches assert the loaded hash equals the fork.
- No hidden change: the PPO loss, GAE, reward, horizon and clocks are unchanged since R2; the only training-path
  additions are (i) arm 01w/11s identities and (ii) `update_diagnostics` (KL between successive policies on 256 fixed
  prefix + 256 fixed suffix anchor rows and the actor parameter-change norm, computed without RNG or gradient). Test:
  enabling the diagnostics leaves parameters, optimiser and every RNG stream bitwise unchanged.
- Earlier results affected: none (no defect found). E2 used the same component code.

**C. A3 study (confirmatory; new study with its own provenance).**
Question: does suffix-only preservation improve normal-start P1 on independent training seeds, and does any
advantage reflect anchor allocation, a weaker coefficient, or both?
Design: K=3; early BC 4,000 updates (`experiments/a3/bc-a3.json`: unchanged conf-v1 joint dataset, sampler,
architecture, lr); 24 fresh seeds 43-66 (all kept; no replacement or extension); critic preparation and 51,200-action
ordinary-PPO probe as R2; five branches from each complete fork: A 00, B 01p, C 01s, D 01, E 01w (expected losses
in B). Normal starts in every arm; no resets; original horizons and terminal binary reward; pi0 reference.
Branch order: Latin rotation over seeds (`experiments/program2/make_batches.py`). 501,760 continuation actions per
branch; complete states saved at 251,904 and 501,760. Data r3-v1 = r2-v1 + new roles a3_select (diagnostics, 64),
a3_bank (64-state bank, 32/16/16), a3_final (128); disjoint from every earlier role by structure, seed and suffix
(`tools/data_gate.py --r3`); training data byte-identical. Evaluation at both endpoints only (no curve points):
a3_final 128 K=3 layouts x 4 attempts and a3_bank 64 x 4, eval seed 959000 (bank 959001), common layouts and
attempt schedules across arms and seeds; pi0 and post-probe diagnostics on a3_select.
Inference (`tools/analyze_a3.py`, synthetic tests `tests/test_analyze_a3.py`):
- Primary H1 at 251,904: d = P1(C) - P1(A) per seed; one two-sided paired t-test at alpha 0.05 (df 23) and its 95%
  interval; supported iff the interval lies above 0.
- Gatekeeping: only if H1 is supported, H2a C - D and H2b C - E at 251,904, two-sided paired t, Holm over the two.
  Otherwise both are descriptive. The hierarchy is fixed.
- Sensitivity (not decision): crossed seed x layout bootstrap (10,000, RNG 20261103), layouts-only bootstrap, exact
  sign-flip (2^24).
- Secondary (descriptive, 95% t-intervals): B-A, C-A, D-A, E-A, D-C, C-D, C-E, interaction D-B-C+A at both
  endpoints; 501,760 is the prespecified persistence assessment; the primary endpoint never moves. Exact
  access/completion decomposition per arm vs A (arithmetic, not mediation; undefined cases kept missing). Stage
  measures: q, r, C4, R4, c and entry/retrieval/carrying, change from pi0 and the probe on the same bank states,
  arrival timing and inventory; training anchor KL by stage, applied penalty, update size, approx-KL, entropy,
  visitation and reward exposure.
- Blinding: no contrast, arm mean or per-seed outcome before all 24 seeds are complete. Execution health only.
- Exclusion: a seed missing a branch or failing lineage/state checks is reported as excluded, never replaced.
Precision (`tools/power_a3.py`, `reports/a3/power.md`; the 3-seed SD 0.008 is not used): 95% half-width 0.013 /
0.021 / 0.030 / 0.034 for seed SD 0.03 / 0.05 / 0.07 / 0.08; P(H1 supported) at a true +0.03: 0.996 / 0.80 / 0.52 /
0.42. R2's seed SD of the mixed effect at 251,904 was 0.028. Expected discrimination: a suffix-only effect of the E2
size (+0.055) would be detected at any planning SD; +0.03 is detected unless the SD exceeds ~0.05; a null H1 with a
narrow interval constrains suffix-only benefits to below ~0.02-0.03.
Interpretation limits: E matches C's total scalar coefficient (0.0075), not its gradient strength. C > D without
C > A does not establish a useful suffix-only method. C > E supports a role for allocation beyond this uniform
reduction, not matched gradient strength. Shared parameters: a prefix constraint can change suffix behaviour.
Canary: planned seed 43, run as its own batch; `tools/a3_canary_check.py` (engineering only; no outcome).

**D. Initialization calibration (development).**
Question: does the initialization procedure provide high boundary-entry competence with low stage access, as the
manuscript's regimes require? Seeds 67-69; BC with prefix-sampling probability rho in {0.2, 0.5, 0.8} within each K
(K-balanced batches; prefix count Binomial(128, rho) per K; uniform within K x stage pool; batch, optimiser,
architecture fixed; `experiments/cal/bc-cal-p*.json`); checkpoints 4,000 and 8,000 on one path. Each checkpoint is
evaluated by the BC job on bc_val (50 layouts per K x 4) and dev_bank (64 per K x 4), eval seed 525000; raw attempts
saved. This changes supervised training, representations and behaviour; it is not a pure manipulation of competence.
Targets on three-seed means (`tools/analyze_cal.py`, `tests/test_analyze_cal.py`): K=1 q >= 0.75; K=3 0.05 <= q <=
0.40; entry competence >= 0.55 for K=1 and K=3; normal-start P1 <= 0.60 for both K (room for learning). Selection
among qualifying variants: fewer updates, then rho closest to 0.5, then smaller rho. All seeds kept. If nothing
qualifies: no pilot; report the shortfalls and what prevents the regime. No intervention outcome is used. Reference
point: the unmodified sampler draws prefix transitions with probability 0.341 (K=1) and 0.632 (K=3), the stage
shares of the bc_train pools.
Cost ~1.8M conservative.

**E. Calibrated-regime pilot (exploratory; conditional on D).**
Only if D selects a variant and the conservative cost fits the 15M development ceiling with the reserve held. Selected
sampler/checkpoint, K=1 and K=3, seeds 67-69, one ordinary-PPO probe per (seed, K) on the pilot config, four branches:
00, 10 (demonstration-state starts alpha 0.25, original reset states and remaining times), 01s (suffix-only, base 0.01
-> effective 0.0075), 11s (both); 251,904 continuation actions; complete state copied at the fork; same PPO settings.
Evaluation at 251,904: pl_final 64 layouts per K x 4 and pl_bank 64 per K x 4 (eval seed 989000); diagnostics on
pl_select. No retuning of alpha or lambda. Measures as listed in the instruction (P1, q, entry and later-progress
bank scores, change from pi0 and probe, r, arrival timing and inventory, normal vs assisted visitation and success,
intervention activity, compute); assisted training access is never pooled with normal-start access. The pilot
analysis script is committed before the pilot batches run. Exploratory: 3 seeds x 2 conditions establish no rule.

**F. Synthesis.** After A3 and the development phases: RQ1 distinctions and the RQ2 assessment (reproducible variation,
hindsight headroom over the best fixed method, a condition-identity rule, plausible value of q / entry competence /
delta-c, measurement and trial costs). No selector is trained unless the data justify it.

**G. Interruption and failures.** One job at a time; deterministic watcher; an interrupted or failed job is rerun from
its latest complete input checkpoint under a new batch ID after diagnosis (deterministic failure: fix + new ID; verified
transient failure: one documented retry). Partial outputs are kept. No design change after outcomes.

### Amendment 6 — 2026-11-01c (in force): A4 calibrated-initialization long-budget study; battery rule 31%

Owner instruction 2026-11-01c (verbatim in `mac-agentic-engineering/project.md`, harness `d8155d4`). This amendment
was frozen before any A4 run. Completed-study verdicts are preserved, and Amendment 5's battery rule (below 20%) is
superseded. Earlier replications are not reopened, and the five-arm allocation study is not repeated.

**A. Question.** In the calibrated K=3 initialization (BC rho 0.2, 8,000 updates), does suffix preservation improve
normal-start success after 1,001,472 continuation actions, and does its benefit grow relative to 251,904?

**B. Design.**
- Seeds 70-89 (n = 20), every seed kept. Seeds are never filtered by the calibration targets.
- **BC.** `experiments/a4/bc-a4.json` uses the unchanged joint conf-v1 K=1/K=3 dataset and the calibration sampler
  with rho 0.2. It saves one checkpoint at 8,000 updates. It is evaluated on bc_val and dev_bank with eval seed
  525000, as in calibration.
- **Probe.** The unchanged critic preparation and probe (`experiments/a4/a4-v1.json`; PPO settings identical to A3
  and the pilot). It runs on K=3 only, and its diagnostics use a4_select (64 × 2) plus both banks (× 2).
- **Arms, from the same post-probe state.**
  - A = 00, ordinary PPO.
  - C = 01s, suffix-only preservation: the existing estimator, base 0.01 on suffix rows with the full-batch
    denominator, effective (0, 0.0075).
  - pi0 is the BC checkpoint.
  - Both arms use alpha 0, normal starts and the same action allowance and optimization settings.
  - Branch order alternates by seed: 00 first for even seeds.
- **Allowance and endpoints.** 1,001,472 continuation actions (489 rollouts of 2,048; exact). States are saved and
  evaluated at 251,904, 501,760 and 1,001,472 (primary). A recovery state is saved every 100,352 actions; only the
  latest is kept, and it is removed at completion.

**C. Data and banks.**
- `r4-v1` (`experiments/a4/data-r4-v1.json`) copies every r3-v1 file and role unchanged and adds four roles:
  - a4_select (64);
  - a4_bank (128 planner boundary-entry states, K=3, original remaining time, labelled "entry", separate from every
    historical mixed bank);
  - a4_final (256 K=3 layouts);
  - a4_donor (512).
- Gate: `tools/data_gate_r4.py`. Training files are byte-identical, and every new role shares no structure, seed or
  suffix with any earlier role.
- **Normal-start evaluation.** a4_final, 256 × 2 attempts, eval seed 969000, the same layouts and attempt streams
  for every policy.
- **Entry bank.** 128 × 2 (seed 969001).
- **Actual-arrival bank** (`experiments/a4/arrival-v1.json`), frozen before any A4 run:
  - Sources: the calibration BC policies rho 0.2 / 8k, seeds 67-69.
  - Donor i goes to source i mod 3, with one sampled attempt per donor on a4_donor K=3, collect seed 979500.
  - The complete snapshot is taken at the first crossing.
  - Kept: crossings with at least 1 remaining step, the first 96 in donor order.
  - All 512 donors run. A shortfall is reported, and nothing is re-collected.
  - Evaluated × 2 with seed 969002.
- P1 is primary. C4 and R4 are not computed from two attempts.

**D. Statistics** (`tools/analyze_a4.py`, frozen; synthetic test `tests/test_analyze_a4.py`).
- **H1.** d_i = P1(C, 1,001,472) − P1(A, 1,001,472). Two-sided paired t at alpha 0.05 with a 95% interval, n = 20.
  The decision is "supported" if the interval excludes 0.
- **H2, gated.** Only if H1 is supported: g_i = d_i(1,001,472) − d_i(251,904), two-sided paired t at alpha 0.05. An
  increasing benefit is called supported only if H1 is positive and H2 is supported and positive. Otherwise the
  change across time is descriptive.
- **Sensitivity** (not decision rules):
  - crossed seed × layout bootstrap: 10,000 replicates, RNG 20261104, layouts resampled jointly for all seeds and
    arms;
  - layouts-only bootstrap;
  - exact sign-flip over 2^20 patterns.
- The 95% interval is reported against 0, ±0.03 and ±0.05. The analysis uses A4 data only, with no pooling.
- **Secondary and descriptive measures, at each endpoint:**
  - p, q and r (missing when there is no arrival);
  - entry-bank and arrival-bank competence, and their changes from pi0 and the probe on the same states;
  - arrival timing and inventory;
  - the per-seed decomposition (not mediation; bank competence is never used for r);
  - training anchor KL, applied penalty, update size, suffix visitation and successful-return exposure, by interval;
  - descriptive pattern labels from section 8. No single pattern is taken as an explanation.
- **Cohort profile.** BC-evaluation targets per seed, and pi0/probe q, entry and arrival competence. If the cohort
  does not reproduce the profile, the study is described as testing the fixed rho 0.2 / 8k procedure.
- Treatment outcomes stay blinded until 20/20. There is no interim stopping, extension, endpoint substitution or
  seed selection.
- Planning scenarios are in `reports/a4/power.md`: for seed SDs of 0.03-0.10, the 95% half-width is 0.014-0.047.

**E. Budget.**
- 70,000,000 actions from ledger 255,665,568. Earlier allowances are not carried over.
- Driver `tools/run_program4.py`. Before each batch, the worst-case conservative cost of this batch, plus every other
  incomplete required batch, plus 0.3M audit, must fit in 70M.
- Conservative costs are hard bounds: every evaluation attempt runs to its time limit.
- Planned worst case: about 61.8M with the real role limits (64.4M with every limit at 157). Expected: about 59.5M.
  The remaining protection is about 8M worst case and about 10.5M expected.
- Failures and retries consume the protection. If the fixed study no longer fits, the driver stops and the problem
  is reported. Seeds are never dropped.

**F. Battery and recovery.**
- **Rule.** Execution stops at 31% or lower, also on AC.
- **Guard** (`tools/battery_guard.py`).
  - Polls `pmset` every 15 s.
  - A failed reading sets an admission hold; after 8 consecutive failures it triggers a pause.
  - It pauses early when the discharge rate over the last 15 minutes predicts 31% or lower within 300 s.
  - At a pause it writes the persistent `.mae/monitor/BATTERY_PAUSE.json` and writes STOP into a running batch with
    verified identity.
- **Stop sequence.** The runner sends SIGTERM to the job. The branch saves `recovery.pt`, writes `paused.json` and
  exits 75 at the next update boundary. After a 10 s grace the runner kills anything left.
- **Admission.** The driver and every job check admission at start. The driver also requires a live guard with a
  fresh "ok" status.
- **Restart.** The flag is never cleared by code. Work resumes only on the owner's explicit instruction: the agent
  removes the flag, then `tools/make_resume_a4.py` writes resume batches.
- **Resume.** Exact resume from the latest valid state, verified by the smoke test. BC and probe jobs rerun from
  their complete inputs under a new batch. Interrupted records are kept and counted.
- **Completion** requires the full allowance and all endpoint artifacts across the lineage, never an exit code alone.

**G. Reporting.**
- `tools/verify_a4.py` gives an independent recomputation.
- Required content: all 20 paired seeds, inference and layout sensitivity, the gated time comparison, cohort
  stability, planner-entry versus arrival-bank competence, decomposition limits, costs, interruptions and one
  decisive recommendation.
- No automatic extension or added seeds.

### Amendment 7 — 2026-11-02 (in force): access-focused programme (RQ1): failure diagnostics, reset-placement pilot, conditional confirmation

Owner instruction 2026-11-02, recorded verbatim in `mac-agentic-engineering/project.md` (harness `936e761`). This is an
RQ1 study. No RQ2 selector. A4 is not extended. No preservation-only experiments. All earlier verdicts stand (F10-F25,
read with F23 and F26).

**A. Question.** Can the placement and ordering of demonstration-state starts improve learning of the prerequisite
sequence and normal-start success at a fixed budget, while keeping useful later-stage competence?

**B. Phase 1: failure diagnostics** (`bc2rl.diag5`, `experiments/p5/diag-v1.json`). No training.
- **Policies.** Fixed rule, not performance: A4 seeds 70-73, arm 00, at the post-probe fork and at 1,001,472 (hashes
  checked).
- **Layouts.** d5_trace, 64 K=3 layouts. This role is separate from every A4 role and every role of this programme.
- **Normal starts.** 2 attempts per layout, eval seed 979600. Each attempt is traced (`bc2rl.trace`): module entry
  times, door openings, key pickups, wrong-key pickups, toggles on locked doors, door closes, no-op actions, pose
  repeats, maximum cell visits, end stage and deadline.
- **Reference 2.** Every actual arrival is certified (`bc2rl.suffix_cert`). The planner then attempts the suffix from
  the actual arrival state with the remaining time:
  - feasible: the abstraction plan is replayed in the real environment and succeeds within the remaining time; the
    replay actions are counted;
  - impossible: the relaxed lower bound exceeds the remaining time;
  - unresolved: neither holds.
  A failed search is never counted as impossible. "Verified finishable access" is the share of attempts whose arrival
  is certified feasible. Unresolved arrivals are reported separately. Manuscript q is unchanged.
- **Reference 1.** The planner executes the prefix once per layout; those actions are counted once. Each frozen policy
  then executes the suffix from that state with the original clock: 2 attempts, eval seed 979601.
- **Status of the references.** Both are diagnostic conditions, not normal-start performance. Reference 1 changes the
  arrival state and timing and is not an upper bound.
- **Existing A4 records.** These give arrival timing, remaining time and deadline failures for all 20 seeds.
- **Opportunity rule (fixed before the diagnostics run).** The pilot runs only if both of the following hold, as
  means over the four final checkpoints:
  - (i) failures before the boundary are at least 25% of normal-start attempts (1 - q >= 0.25);
  - (ii) reference-1 success minus normal-start P1 is at least 0.05.

  If either fails, the result is reported and the pilot budget is not spent. Any correctness defect is resolved and
  its scope stated before training. The rule shows headroom only. It does not show that an access intervention will
  recover these failures.

**C. Phase 2: development pilot** (`experiments/p5/p5-v1.json`, `tools/run_program5.py`).
- **Initialization.** As A4: joint BC dataset, rho 0.2, BC checkpoint 8,000, K=3 online training, unchanged critic
  preparation and probe, architecture, reward, horizon and PPO settings. No preservation penalty in any arm.
- **Seeds.** 90-95, all kept, none filtered. Seed 90 is the engineering canary and is included in the analysis.
- **Arms.** All four are forked from one post-probe state. Branch order is rotated by (seed - 90) mod 4.

  | Arm | Starts |
  |---|---|
  | A (00) | Ordinary PPO |
  | B (B5) | Post-boundary demonstration resets with the original 50/25/25 entry/retrieval/carrying mixture of reset_donor planner states |
  | C (C5) | Uniform over three prerequisite-module-entry banks |
  | D (D5) | Backward curriculum: module 3 entry, then module 2, then module 1, in successive quarters |
- **Shared withdrawal schedule** (new specification; B is not a reproduction of the earlier constant-reset arm).
  - Assisted starts have probability 0.25 for starts drawn while executed continuation actions are below 376,320
    (75% of 501,760); there are none after that.
  - Normal starts remain available throughout. Episodes in progress always finish; nothing is cut at a boundary.
  - D's phases change at 125,440, 250,880 and 376,320 executed actions.
  - The schedules depend only on executed actions, never on outcomes.
- **Module-entry banks** (`ResetBank.module_rows`).
  - Each bank holds one state per reset_donor K=3 planner trajectory: the first recorded state with the agent inside
    module j's room, before that module's key is held.
  - Each state is rebuilt from the recorded observation: full grid and objects, inventory, doors, pose, original
    elapsed time and remaining time. Dynamics do not use the environment RNG.
  - Module 1 entry is the donor's initial state, so those starts do not bypass any prefix.
  - Tests: exact restoration, doors earlier/later, key not held, and the remaining planner plan still succeeds.
  - Donors are the reset_donor role, separate from evaluation and competence-bank roles.
- **Evaluation** at 251,904 and 501,760 (the fixed final pilot endpoint).
  - Normal starts: p5_eval, 64 K=3 layouts x 4 attempts, common random numbers (eval seed 989000), traced; arrivals
    certified.
  - Entry bank: p5_bank, 128 planner boundary-entry states x 2, original clocks.
  - pi0 and post-probe diagnostics: p5_select 64 x 2 and p5_bank x 2.
- **Reported.**
  - P1, q, verified finishable access (unresolved separate), arrival-conditioned completion, entry-bank competence,
    arrival timing and inventory, per-module progress and completion;
  - normal versus assisted training episodes and successes, assisted-step fractions and stage visitation (from
    training counters);
  - interaction and compute costs.

  Assisted-start results are never pooled with normal starts. Every paired seed contrast is shown with uncertainty.
  No per-arm checkpoint selection. Six seeds are development evidence, not confirmation.

**D. Confirmation gate** (fixed before any pilot outcome; `tools/analyze_p5.py` writes `reports/p5/gate.json`).
- A method m in {B, C, D} qualifies only if, at 501,760 on p5_eval, all of the following hold:
  - (1) mean over the 6 seeds of [P1(m) - P1(A)] >= 0.05;
  - (2) P1(m) - P1(A) > 0 in at least 4 of 6 seeds;
  - (3) execution and evaluation checks pass for all 6 seeds of m and A;
  - (4) the complete confirmation (conservative cost) fits in the remaining 70M budget.
- Among qualifying methods, select the one with the highest mean final P1. If another qualifying method is within
  0.02 of it, prefer the simpler one in the order B, C, D.
- Access and competence measures explain the result; they are not filters.
- If no method qualifies: no added doses, schedules or seeds. Finish the diagnostic synthesis and propose the next
  discriminating question without launching it.

**E. Phase 3: conditional confirmation** (`experiments/p5/c5-v1.json`; batches written by `tools/make_confirm_p5.py`
only after the gate).
- **Seeds.** 96-115 (n = 20, fixed): the same initialization, K=3, A (00) against the selected method with the exact
  pilot schedule and bank construction.
- **Primary endpoint.** 501,760, evaluated on c5_final (256 K=3 layouts x 2, eval seed 999000) and c5_bank (128 x 2).
  The descriptive checkpoint at 251,904 uses the same panel.
- **Certification.** Arrivals are certified at the primary endpoint only (budget; hard bounds).
- **Primary estimand.** The mean paired difference P1(m) - P1(A) at 501,760 over 20 seeds. One two-sided paired
  t-test at alpha 0.05, with its 95% interval.
- **Sensitivity.** Crossed seed x layout bootstrap (10,000; layouts common to arms) and exact sign-flip, with their
  assumptions.
- **Discipline.** Pilot data are not pooled. Blinded until 20/20. No interim stopping, seed replacement, schedule
  change or endpoint selection. No C4/R4.
- **Interpretation.** A benefit means learning efficiency at a fixed budget, not better converged performance.

**F. Budget.**
- 70,000,000 actions from ledger 311,392,581. Unused earlier allowances are not carried over.
- **Admission rule** (`tools/run_program5.py`): spent + conservative(batch) + conservative(other incomplete required
  batches) + the conservative confirmation reserve (held until the gate is recorded) + 0.3M audit <= 70M.
- **Hard bounds.** Each evaluation attempt runs to its time limit. Each certified arrival adds a replay bounded by the
  time limit.
- **Pre-data bounds** (all limits at 157):

  | Item | Bound |
  |---|---|
  | Preparation (data, tests, diagnostics) | about 1.4M |
  | Pilot | 19.8M |
  | Confirmation | 38.8M |
  | Audit | 0.3M |
  | Worst-case total | about 60.4M |

  That leaves about 9.6M protected.
- Local development checks before freezing: 17,940 measured outside the runner, plus 60,000 estimated (in
  `research/ledger_adjustments.json`).

**G. Execution and recovery.** These are as Amendment 6:
- 31% battery rule, guard and persistent flag; checkpoint-and-pause and exact resume;
- completion only with the full allowance and endpoint artifacts;
- canary seed 90 (engineering checks only, never retuning);
- two-hour reviews;
- the failure policy.

**H. Accounting fix.** Real jobs that tests start as subprocesses with a temporary MAE_RUN_DIR now mirror their step
record to the parent's ledger location (`BC2RL_STEPS_MIRROR`). The same gap affected A4's `a4-smoke` job. Its
subprocess actions are re-measured by this programme's smoke job and added as an A4 adjustment.
