# MiniGrid study: demonstration-state starts and BC preservation after BC

Status 2026-10-31 01:40 EDT: M0-M3 complete; pre-M4 development campaign complete. **No confirmatory result
exists.** Every number below comes from development layouts and is exploratory. The protocol freeze
(`research/PROTOCOL_FREEZE.md`, commit `7f94f18`) is unchanged. A proposed Amendment 1 waits for owner
approval. No confirmation data have been generated.

## Question
RQ1: when do demonstration-state starts (arm 10), forward-KL preservation toward the BC policy (arm 01),
or both (arm 11) improve PPO after BC, compared with ordinary PPO (arm 00)?
Task: MiniGrid prerequisite rooms (K = 1 or 3) before a common suffix. Measures: normal-start success P1,
access q, and competence c on a fixed planner-derived suffix bank.

## 1. Audit findings and corrected claims (F8)
- Metrics recompute exactly from raw attempts (64 branches; maximum difference 0.0). The selected contrasts
  reproduce using the original arm-00 runs.
- Analysis key: `reports/m3_manifest.csv`, 72 jobs = 8 probes + 32 selected + 24 screen + 8 repeats, with
  source commits and checkpoint hashes. Selection is by explicit key.
- The alpha/lambda selection rule was committed 11 s before the screen batch started, in the commit the batch
  ran from.
- Contract audit: no correctness defect. Checked: binary terminal reward, necessary crossing, original
  clocks, full restore, matched banks, disjoint roles, one BC path per seed, complete fork state, KL to the
  BC checkpoint, GAE/termination, and matched action budgets.
- Engineering limitation: M3 branch checkpoints hold weights only and cannot be resumed. New runs save
  complete hashed state; an exact resume test passes on CPU.
- **Corrections:**
  - C1: ordinary PPO improved in 8/8 forks, not 7/8.
  - C2: withdrawn: repeat variation attributed to "GPU nondeterminism alone" and the variance decomposition.
  - C3: withdrawn: the freeze's precision and power claim, which assumed independent strata within a seed.
  - C4: early diagnostics and final evaluation shared layouts in the freeze plan.
  - C5: about 2.75M environment actions ran outside the runner (tests and checks). They are now a
    conservative 3.1M ledger line.

## 2. New experiments, costs, deviations and failures
Pre-registered in `research/DECISIONS.md` (2026-10-31). Batch `20261031T050016-80407`, commit `424354c`.

| ID | What | Actions | Result |
|---|---|---|---|
| E3a | Evaluation repeatability on one saved policy | 77,331 | Same seed: 384/384 attempts identical. New seed: P1 moved -0.031 |
| E3b | Arrival-state banks, cross-policy evaluation, clock-extended condition (K=3, 16k, 2 seeds) | 225,816 | F9 |
| E3c | KL activity (8 forks) | 0 | lambda 0.01 lowers anchor KL in 8/8 forks; gradient share 1.5-3.5% |
| E1 | Four arms to 501,760, K=3, extended BC, seeds 0 and 1 | 4,730,779 | F9 |
| E2 | Seed-2 replicate | 0 (deferred) | Stopped before any action, for budget |

- **Deviation 1.** M3 branches were not resumable, so E1 is fresh runs from the hashed post-probe forks
  (501,760 actions each). This is declared as a separate pipeline segment and its full cost is counted.
- **Deviation 2.** The ledger correction lowered the development allowance from 8.0M to 5.0M, so E2 and the
  K=1 extension were not run. Campaign total: 5,033,926 actions. That is 0.03M above the conservative
  5.0M allowance and within the 5.35M allowance at the point estimate.
- **Failures.** None.

## 3. Learning curves and paired effects
Figure: `reports/dev2_curves.svg`. Tables: `reports/dev2_long_evals.csv`, `reports/dev2_long_contrasts.csv`.
- At 250k (M3, 8 forks): all contrasts average within 0.02 of 0; fork SD 0.04-0.06.
- At 500k (K=3, extended BC, 2 seeds), seed 0 / seed 1:

| Contrast | Seed 0 | Seed 1 |
|---|---|---|
| reset | -0.039 | +0.020 |
| preserve | -0.008 | +0.031 |
| combined | -0.008 | +0.062 |
| Y11 - Y10 | +0.031 | +0.043 |
| Y11 - Y01 | 0.000 | +0.031 |

  Every within-seed layout interval includes 0. **Inconclusive.**
- Ordinary PPO still learns: +0.004 and +0.078 from 250k to 500k; all arms +0.065 on average.
- No conclusion supports "accelerates learning", "improves the later endpoint", "preserves competence"
  or "helps only under particular conditions". The data remain inconclusive.
- The M3 K=3 combined benefit (+0.043, +0.039) became -0.047 and -0.008 when the same forks were retrained.
  The moderation D = (Y11 - Y00)[K=3] - (Y11 - Y00)[K=1] is not robust: extended-BC D at 250k is +0.055 / +0.086
  with the M3 K=3 paths and -0.035 / +0.039 with the new K=3 paths. D cannot be computed at 500k.

## 4. Access, competence, arrival states, time pressure, intervention activity
- **Access vs competence by condition** (F9 regimes):
  - K=1 has full access (q about 1) and is limited by suffix completion.
  - K=3 has low access (q 0.45 at pi0) with useful bank competence (0.64 at 16k).
  - K=3 at 4k is near the floor, with late arrivals.
- **Arrival mismatch.** Arrival states share pose and inventory with the bank's entry states but have less
  time and different prefix-room configurations. Competence on actual arrival states (0.38-0.63) is below
  planner-bank c (0.59-0.73) for every policy.
- **Time pressure.** Restoring 104 remaining steps (a separate, labelled condition) recovers only about +0.03.
  Planner-bank c and arrival competence are different estimands.
- **Do not read p = q x c.**
- **Intervention activity.**
  - Realized assisted-episode fraction is 0.244-0.258 for alpha 0.25 (10-19% of steps).
  - lambda 0.01 lowers anchor KL by a median ratio of 0.59.
  - Both interventions are active, so "too weak to act" does not explain the null contrasts. Whether a
    larger dose would change P1 is untested (screen: alpha 0.5 +0.017; lambda 0.1/1.0 lower).

## 5. Replication and remaining uncertainty
- Only 2 development seeds. The planned third seed was deferred.
- Training-path variation is substantial (same-fork repeat SD 0.048; evaluation-only SD about 0.029).
- Layout heterogeneity is large (per-layout SD of P1 0.36). The dominant uncertainties are therefore
  training path and layouts, not attempts per layout.

## 6. Is more development justified?
No, within this budget. Arguments against more:
- No emerging separation at 500k.
- Slow learning.
- Path noise.

The only high-value additions are more independent seeds, which belong in M4, and a test of the
arrival-competence gap (prefix configuration). The latter is a mechanism question for RQ1's
interpretation, not for the M4 design. A 750k/1M extension would cost about 4M more for the same
2 seeds at K=3 and is not justified.

## 7. M4 options (conservative per-job maxima; available for M4 = 80 - 36.82 - 10.26 reserve = 32.92M)

| Option | Design | Cost | Fits? | Can establish | Cannot establish |
|---|---|---|---|---|---|
| **A (recommended)** | Freeze + Amendment 1: K {1,3} x BC {4k,16k} x 5 seeds x 4 arms, 251,904 actions, conf_final 64 x 8 | 32.95M (about 31.5M at means) | Yes; reserve >= 10.23M | The frozen equal-weight estimand across all four access/competence regimes; effects of about 0.05-0.07 detectable; equivalence at ±0.05 only if true effects are near 0 | Effects of longer training; small (< 0.04) effects |
| B | Same full matrix at 501,760 | about 56-59M | No: needs about +23-26M (cap about 103-106M) | As A at a longer budget | — within the current cap |
| C | 500k, extended BC only: K {1,3} x 5 seeds x 4 arms | about 29.0M | Yes | Longer-budget effects for high-competence BC | BC-checkpoint dependence; the low-competence regime; the frozen 4-stratum estimand (changed). Larger seed-level SD (2 strata) |

**Recommendation: option A.** The development evidence says precision is limited by independent training
paths and layouts, not by training length. A keeps all four regimes, which is what "when" in RQ1
needs. It fits the cap and protects the reserve. It also saves complete states at 251,904, so a later,
separately funded extension can continue the same trajectories.

## Resources
- Total: 36.82M of 80M environment actions (46.0%), including 3.10M estimated outside the runner.
- Batch wall time: 3.74 h.
- Campaign: 5.03M actions, 0.49 h batch wall time; active work 00:48-01:40 EDT.
- Ledger: `tools/ledger.py` with `research/ledger_adjustments.json`.

## Known limitations
- PPO is step-size-limited (lr 3e-5, clipped gradients on every minibatch).
- MPS training is not bitwise reproducible, so inference relies on independent seeds.
- The 250k endpoint is a fixed budget, not convergence (arm 00 still improves at 500k).
- The planner bank measures a different state distribution from actual arrivals.

## Readiness
Ready for M4 on approval of option A and Amendment 1. On approval, in order:
1. Generate conf-v1 with conf_final 64 per K.
2. Check that the training roles are byte-identical to dev-v2.
3. Run the BC for seeds 10-14.
4. Run M4 one seed-batch at a time, with a budget check before each batch.

RQ2 stays a costed follow-up proposal.
