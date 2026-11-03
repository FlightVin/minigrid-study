# MiniGrid study: final write-up

Consolidated under the owner instruction of 2026-11-02d. This document summarises the whole MiniGrid programme
(M0 to Amendment 9). It adds no new experiment. The detailed record stays in `reports/REPORT.md` (sections C to V),
`research/FINDINGS.md` (F1-F33) and `research/PROTOCOL_FREEZE.md` (Amendments 1-9). Where those records carry a
marked correction, this document uses the corrected wording.

## 1. Question and task

**Research questions (manuscript).**
- **RQ1.** When do demonstration-state starts, behaviour preservation, or their combination improve PPO after
  behaviour cloning (BC)?
- **RQ2.** Can early measurements predict which option helps on held-out task conditions, better than simpler
  selection methods after their cost?

**Task.** A custom MiniGrid environment, fully observed and symbolic. A **prefix** of K locked-door modules
(K = 1 or 3; each needs the matching key) leads through one gateway to a common **suffix**: an obstacle route,
disposal of the final key, target pickup and delivery. Reward is 1 on delivery only. Each layout has a fixed action
limit (prefix length + 24 + 80).

**Pipeline.** BC on planner demonstrations → a shared 50k-action PPO probe → matched PPO continuation branches from
one hashed fork per seed. Separate feed-forward actor and critic (three 3×3 convolutions, one 128-unit layer).

**Measures.** All are on unassisted normal starts unless stated otherwise.
- **P1:** success rate (mean over layouts of the per-layout success fraction).
- **q (access):** the fraction of attempts that cross the boundary into the suffix.
- **r (completion):** successes divided by arrivals (S_A/A).
- **c (bank competence):** success from saved boundary or suffix states.

The decomposition of a P1 difference into an access term and a completion term is arithmetic, not mediation.

## 2. Hypotheses and conclusions (confirmatory and gated tests)

Each row gives the strongest evidence for the hypothesis. "95% t" is over training seeds and conditional on the
evaluated layout panel. "Crossed" is the seed × layout bootstrap. Effects are P1 differences against ordinary PPO
(A or arm 00).

| # | Hypothesis | Strongest evidence | Uncertainty | Conclusion |
|---|---|---|---|---|
| H1 | Demonstration-state starts (α 0.25) improve P1 (RQ1; equal-weight average over K × BC checkpoint) | M4, 5 seeds, prespecified: +0.004 at 501,760 (95% t [−0.016, +0.023]); −0.011 at 251,904 | TOST at ±0.05 passed at both budgets; crossed agrees | **Practically equivalent** to ordinary PPO within ±0.05 (F10, F11) |
| H2 | BC preservation (forward KL to π0, λ 0.01) improves P1 (RQ1, average) | M4: +0.003 [−0.015, +0.021] at 501,760 | TOST passed | **Practically equivalent** within ±0.05 |
| H3 | The combination improves P1 (RQ1, average) | M4: +0.004 [−0.028, +0.035] at 501,760 | TOST passed | **Practically equivalent** within ±0.05 |
| H4 | Low access with substantial competence predicts a benefit from demonstration starts (manuscript) | M4 K=3/extended BC: reset −0.004 (descriptive); calibrated pilot K=3 +0.001 [−0.078, +0.080] (3 seeds); reset-placement pilot best +0.028 [+0.004, +0.052] (6 seeds, gate not met) | No confirmatory test of this condition; development estimates only | **Not supported.** Effects below about 0.03 are not excluded |
| H5 | Preservation helps where BC competence would decline: K=3, early BC (post hoc from M4) | R2, 20 fresh seeds, prespecified: +0.0097 [−0.0035, +0.0229], p 0.142 | Crossed [−0.0071, +0.0260]; R1 +0.040 [+0.004, +0.076], Holm p 0.067 | **Did not replicate at the M4 size** (+0.045). Effects ≥ 0.03 are excluded; a small effect is not |
| H6 | Suffix-only preservation (effective 0.0075) improves P1 at 251,904 (A3) | A3, 24 seeds, prespecified: +0.0106 [+0.0019, +0.0193], p 0.019 | **Crossed [−0.0014, +0.0235] includes 0** | **Supported for this panel; about one point.** Not resolved for new layout panels |
| H6b | Restricting preservation to suffix states beats the full or 0.75× mixed penalty (A3 gate) | C − D +0.0007 [−0.0079, +0.0093]; C − E −0.0003 [−0.0101, +0.0094] | Differences larger than about ±0.01 excluded | **Not supported.** No allocation advantage at the tested strengths |
| H7 | Suffix-only preservation improves P1 at 1,001,472 actions in the calibrated regime (A4) | A4, 20 seeds, prespecified: +0.0047 [−0.0152, +0.0246], p 0.63 | Crossed [−0.020, +0.029]; ≥ 0.03 excluded | **Not supported.** Early +0.020 at 251,904 (descriptive) faded as ordinary PPO caught up |
| H8 | An access-targeted reset placement (post-boundary, module entry, backward curriculum) improves P1 by ≥ 0.05 (Amendment 7 gate) | Development, 6 seeds: +0.008, +0.012, +0.028 [+0.004, +0.052] | Development only; no multiplicity control | **Gate not met.** No confirmation run |
| H9 | Planner corrections on learner-visited prefix states (C) improve P1, and beat matched demonstration replay (R) (Amendment 9 gate) | Development, 6 seeds: C − A −0.111 [−0.136, −0.086], 0/6 positive; R − A +0.004 [−0.067, +0.075]; C − R −0.115 | Development only; C − A direction consistent in every seed | **Gate not met. C lowered P1** in this fixed procedure; R showed no material change |
| RQ2 | Early measurements select a per-condition intervention better than simple rules, after cost | M4 hindsight headroom +0.010 (in-sample); leave-one-seed-out condition rule +0.0006; calibrated pilot headroom +0.0065 | No held-out conditions were built; no selector was trained | **Not tested.** Demonstrated headroom is too small to repay diagnostic cost (37k-73k actions per condition) |

All six M4 primary contrasts (three interventions × two budgets) lay inside ±0.05 by TOST.

**Overall answer to RQ1.** At the tested strengths, budgets and task, none of demonstration-state starts,
preservation, their combination, reset placement or corrective imitation produced a resolved gain of the
planning size (0.03-0.05) in normal-start success. The only confirmatory positive result (H6) is about one point,
early in training, and is not resolved under layout uncertainty. A matching early advantage in A4 (+0.020) faded by
1M actions.

## 3. Exploratory diagnostics (kept separate; no confirmatory claim)

| Study | What it showed | Status |
|---|---|---|
| M4 condition-level effects (F11) | K=3/early BC preservation +0.045 (5/5 seeds); K=1/early BC −0.048 at 251,904, closed by 501,760; checkpoint dependence at K=3 | Post hoc; the K=3 effect did not replicate at its size (H5) |
| E1 cross-panel re-evaluation (F15, F18) | The M4 subgroup effect held on a second panel for the same policies (+0.041, +0.058). R1 policies gave +0.025 and +0.020 | Already-observed policies; panel effects of 0.02-0.04 not excluded |
| E2 anchor components (F16) | Suffix-only +0.055 in 3/3 seeds; full penalty null | 3 seeds; did not replicate in A3 (H6b) |
| Initialization calibration (F20) | BC with ρ 0.2 and 8,000 updates gave high entry competence (0.60) with low K=3 access (0.21) | Three-seed means; fragile (1/3 seeds met all targets alone) |
| Calibrated-regime pilot (F21) | Resets and suffix preservation raised fixed-bank boundary-entry competence (01s +0.133) without a normal-start change | 3 seeds; ±0.08 intervals |
| A4 longitudinal (F26) | Ordinary PPO: P1 0.186 → 0.390 from 251,904 to 1M; access term +0.162 of +0.204 | Descriptive decomposition |
| Failure diagnostics (F28) | At A4 finals: 3-6% of attempts arrived in a certified impossible state; 0.49-0.71 of failures were before the boundary; failed attempts repeated locked-door toggles and no-ops | Traced sample; behaviours, not causes |
| Controller diagnostics (F29-F31) | Privileged key help in every module +0.100 (A4 cohort) and +0.158 (pilot cohort); full prefix help +0.27 to +0.34; door-only help and action masking ≤ 0.05. The A4 key-only crossed intervals include zero | Frozen policies, privileged help; opportunities, not training results |
| Corrective-imitation secondaries (F32) | C doubled policy entropy; removed most locked toggles and no-ops; lowered q (0.29 vs 0.42) and r (0.28 vs 0.46) without labelling suffix states; policy mass on the held-out recovery bank's label sets rose only 0.647 → 0.675; auxiliary CE 0.87 nats above its tie-entropy floor (premise audit) | Development; post hoc mechanisms not separated |

## 4. Negative results, small effects and failed replications

**Negative or null results (prespecified).**
- M4: all three interventions practically equivalent to ordinary PPO on average (H1-H3).
- R2: the K=3/early-BC preservation effect not supported (H5).
- A3: no allocation advantage for suffix-only preservation (H6b).
- A4: no long-budget benefit of suffix preservation (H7).
- Amendment 7 and Amendment 9: no method passed the development gate (H8, H9). Corrective imitation was harmful in
  the frozen procedure.
- RQ2: no selection headroom worth its cost.

**Small effects.**
- A3 suffix preservation: +0.0106 at 251,904 (panel-conditional; crossed interval includes 0).
- A4 at 251,904: +0.020 (descriptive), +0.005 at 1M.
- R2 full penalty at 501,760: +0.0097; A3 full penalty +0.0087. These agree but are below any planning value.
- Backward reset curriculum: +0.028 (development).

**Failed replications.**
- M4 post hoc subgroup +0.045 (seed SD 0.008) → R1 +0.040, inconclusive (Holm p 0.067) → R2 +0.0097, not supported.
  The subgroup was selected after outcomes; the first estimate was inflated. The 5-seed SD understated the spread by
  about five times.
- E2 3-seed suffix-only +0.055 → A3 24-seed +0.0106. The "suffix positive, full penalty null" pattern did not
  replicate (D − A +0.0098).
- Fixed-bank competence gains (pilot, A4 entry bank +0.035 at 251,904) did not appear on actual-arrival states at
  1M (−0.006) or in normal-start success.

## 5. Measurement lessons

1. **An optimisation defect can look like forgetting.** The first probe collapsed (P1 0.25 → 0.00) because of
   large actor updates on critic noise plus an entropy bonus, not missing stage practice (F2). A stability screen
   came before any scientific comparison.
2. **Training on MPS is not bitwise repeatable.** The repeat SD (0.027) was not distinguishable from evaluation
   noise alone (SE 0.020 per policy at 32 × 8). Inference must rest on paired seeds, not repeat runs (F8).
3. **Strata within a seed are not independent.** Both BC checkpoints and both K values share one BC run, and every
   seed shares one panel. An early power statement that assumed independence was withdrawn (F8).
4. **Keep diagnostic and evaluation layouts apart.** π0 and probe diagnostics were moved off the final panel (F8).
5. **Count every action.** About 2.75M actions ran outside the runner before M4 and were added late. Test
   subprocesses later lost 74,997 actions of step records. Mirrored step records fixed it (F8, F28). Every
   programme now reconciles the ledger to batch records exactly (F33: 577,518 = audit + local runs).
6. **Use paired criteria.** An unpaired "within seed-to-seed spread" statement hid a paired effect (F10 → F11).
7. **Post hoc subgroups and 3-seed estimates are inflated.** M4 +0.045 → R2 +0.0097; E2 +0.055 → A3 +0.0106.
   Small-sample SDs are unreliable (0.008 vs later 0.028-0.043).
8. **Re-evaluation noise is large at 64 × 4.** Re-scoring the same R1 policies with new attempt seeds moved the
   cohort estimate from +0.040 to +0.020 (F15). Neither evaluation identifies a "noise share" (F18).
9. **Report panel-conditional and crossed intervals together.** A3 passed its prespecified t-test while the crossed
   bootstrap included 0 (F19, F23). The layouts-only bootstrap ignores seed variation and is not valid for the
   estimand (F14).
10. **A fixed planner bank is not the arrival distribution.** Much of an early "bank vs arrival" gap was the bank's
    progress mix (F11). In A4, entry-bank gains persisted while arrival-bank gains did not (F24).
11. **Assisted references are not bounds.** "Headroom" from a planner-assisted prefix was withdrawn: assistance
    changes trajectories, inventory and time together (F27, F28, F31).
12. **State denominators explicitly.** Mean-of-seed r differs from pooled S_A/A; eligible-episode denominators
    overstated premature key drops (243/502 → 177/501) (audit_p5, F31).
13. **The access/completion split is arithmetic, not mediation.** Comparing significance across measures on
    different scales ("mainly access") was withdrawn (F13, F23).
14. **Do not compare across panels or summary statistics.** A post-probe median on one panel against an endpoint
    mean on another was withdrawn as a learning gain (F26).
15. **Validate expert labels before freezing.** The label planner first left the frontier key's cell blocked after
    pickup (44 inconsistent labels); a consistency check found it before any outcome (Amendment 9). One residual
    tie-set gap (1/480) is documented.

## 6. Costs

Executed environment actions over the whole programme: **342,196,148** (ledger). By programme (approximate; small
residuals are ledger adjustments recorded in DECISIONS):

| Programme | Actions |
|---|---|
| M0-M4 (development, M4 confirmation) | about 93.0M |
| R1 replication | 25.5M |
| Amendment 4 (R2, E1, E2) | 39.6M |
| Amendment 5 (A3, calibration, pilot) | 97.4M |
| Amendment 6 (A4) | 55.7M |
| Amendment 7 (diagnostics, reset-placement pilot) | 16.8M |
| Amendment 8 (controller diagnostics) | 1.4M |
| Amendment 9 (record audit, corrective imitation development) | 12.6M |

No result was excluded, and no seed was replaced. Every deterministic failure was fixed with a new run ID, and every
failure stays in the record.

## 7. Limitations

- One task family, one network family, one PPO configuration. A small gridworld does not support claims about other
  domains or long horizons.
- Each intervention was tested at one or two strengths. Nulls apply to those strengths and budgets.
- Most estimates are conditional on one evaluation panel per study.
- RQ2 was never tested on held-out conditions.
- Mechanism statements (entropy, interference, access versus completion) are descriptive.

## 8. Reassessment before choosing another environment (owner instruction 2026-11-02d, item 4)

**What is settled.** Ordinary PPO improves steadily with budget, and most of its gain is access (A4: +0.162 of
+0.204). Failure sits mostly before the boundary. Privileged prefix help at evaluation raises success by 0.27-0.34.
Yet every training method that tried to deliver prefix knowledge captured at most about 0.03 or did harm. Those
methods were: starts from module entries, a backward curriculum, preservation of BC behaviour, demonstration replay
and planner corrections.

**The unresolved claim.** All the access interventions rest on one untested premise: *this policy class can
represent the prefix decisions, and only the training signal is missing.* The record has three hints against it:
- Under direct planner supervision of 387,948 learner-visited states, the policy mass on the label set of the
  held-out recovery bank rose only from 0.647 to 0.675 (F32).
  [Corrected 2026-11-03 (premise audit, `reports/p8/premise_audit.md`): raw cross-entropy is not fitting error.
  With uniform targets over tie sets the floor is the target entropy, 0.244 nats on average. The logged CE (1.115)
  was 0.87 nats above that floor (0.79 over the last 20 updates). Argmax-in-set agreement was 0.64 (0.68 over the
  last 20 updates). Those examples were fresh current-rollout states, so the excess mixes fitting and
  generalisation, under the joint PPO objective with coefficient 0.1.]
- BC validation loss bottomed at 0.28 near 8,000 updates and then rose. K=3 access after BC was 0.05-0.53
  across the BC variants tried (F1, F20).
- [Corrected 2026-11-03 (premise audit): the earlier text said the actor "sees the 21 × 9 grid through three
  3 × 3 convolutions, a 7 × 7 receptive field". That is wrong. The convolutions use stride 1 and padding 1, with no
  pooling. Each convolution feature has a 7 × 7 local receptive field. But the full 32 × 21 × 9 feature map is
  flattened (6,048 features, position kept) into one dense layer of 128 units, so the actor's dense layer sees
  the whole grid.] Relations between distant cells, such as "this key's colour matches that door" and "which
  door is the first locked one", must be formed by that single 128-unit layer (777k of the 797k parameters).

If the premise is false, the null and negative results above could reflect the network as well as the
interventions. A new environment with the same network could repeat that confound.
[Note 2026-11-03: the owner authorised a bounded version of the test below as a final capability audit
(PROTOCOL_FREEZE Amendment 10; results in section 9). The proposal text is kept as written.]

**The observation that would change belief.** Can the same actor, trained by supervision alone on planner labels
for learner-visited prefix states, reach high held-out agreement on fresh layouts, and does that policy then reach
the boundary unassisted?
- **High agreement and high access:** the representation is adequate. The failures concern how RL delivers or
  weighs the signal. Moving to a second environment then tests generality.
- **Low agreement despite more data:** the policy class is the binding limit. Fix the architecture first, then
  re-check one key prior result before any new environment.
- **High agreement but low access:** the labels or the abstraction are wrong. Re-examine the planner targets.

**The smallest experiment that tests it** (proposal; not launched; needs an owner instruction):
- **States.** Roll out frozen ordinary-PPO policies (development seeds 116-121, arm A) on fresh training-role layouts.
  Label prefix states with the frozen Amendment 9 planner. Use about 200k training states and a separate 50k
  held-out set from disjoint layouts. Score by argmax-in-label-set, so tie sets need no tie-breaking.
- **Fits.** Cross-entropy only, no RL:
  - the current actor from the BC initialisation and from scratch, at 25k, 100k and 200k states (a data curve
    separates data limits from capacity limits);
  - one larger-capacity comparison actor (for example, a global-context layer).
- **Measures.**
  - Held-out agreement overall and by stratum (on track, backtracked, key lost, wrong key).
  - The existing 480-state recovery bank.
  - Unassisted q with the fitted actor on 64 fresh layouts × 2 attempts, prefix only, planner-free.
- **Decision thresholds** (freeze before running). For example: ≥ 0.90 held-out agreement means adequate;
  ≤ 0.80 with a flat data curve means capacity-limited; anything between is unresolved.
- **Cost.** At most about 0.5M environment actions (collection plus one short rollout panel). About 1 hour of
  local compute. One Amendment 9 development seed cost 1.9M.

This test is useful whatever its outcome. It does not add a dose, seed or schedule to a failed method, and it is not
an attempt to obtain a positive ending.

**A second open question, for after this one.** Completion after arrival stayed near 0.46-0.64 under every
intervention. Learned suffix completion is a separate limit, and it should not be pooled with access in any new
study.
