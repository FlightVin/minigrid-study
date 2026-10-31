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
