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

None.
