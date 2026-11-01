# MiniGrid study: demonstration-state starts and BC preservation after BC

Status 2026-11-01 (programme complete): M0-M4, the R1 focused replication (Amendment 3) and the owner's
2026-11-01 programme (PROTOCOL_FREEZE Amendment 4: R1 audit, R2 20-seed replication, E1 cross-panel, E2 anchor
components) are complete. The consolidated programme report is section P below. Earlier sections are kept; R1
interpretations corrected on 2026-11-01 are marked in place. M4 and R1 frozen verdicts are unchanged.

## Headline

**Programme 2026-11-01 (section P):** the R2 20-seed replication gave +0.0097 [-0.0035, +0.0229], p 0.142:
not supported; the K=3/early-BC preservation effect did not replicate at the M4 or R1 size. The paragraphs below
are the M4 and R1 headlines as written then.

At the tested strengths (alpha 0.25, lambda 0.01) and budgets (251,904 and 501,760 continuation actions), the
equal-weight average effects of demonstration-state starts, BC preservation and their combination were
practically equivalent to ordinary PPO within an absolute ±0.05 P1 margin. The average hides condition-level
effects. With early BC at K=3, preservation raised P1 at 501,760 by +0.045 (95% t-interval +0.035 to +0.055;
5/5 paired seeds positive; baseline 0.062, so +73% relative). This was found after M4 outcomes were seen (post
hoc), so it needs replication. With early BC at K=1, preservation cost -0.048 at 251,904, and the cost had closed
by 501,760. A large part of the earlier "bank vs arrival" competence gap was the progress mix of the saved-state
bank, not a different arrival state.

**R1 (prespecified replication, 8 fresh seeds, new panel):** the K=3/early-BC preservation effect was +0.040
(95% t +0.004 to +0.076), close to M4. It did not pass the prespecified Holm-2 test (adjusted p 0.067), and the
checkpoint interaction was not supported (adjusted p 0.096). The result did not meet its frozen criterion and is
inconclusive, not negative. The estimates are compatible with a positive effect similar to M4's (corrected
2026-11-01). The seed SD of the effect (0.043) was larger than in the M4 subgroup (0.008); the reasons are not
resolved (R1.10).

## P. Programme 2026-11-01 (Amendment 4): consolidated report

### P1. What completed and what remains
Completed, all under the frozen design: targeted R1 audit (R1.10, F13); R2 with all 20 planned seeds (23-42, no
exclusions, no failures); E1 cross-panel (26 policies x 2 panels); E2 anchor components (3 forks x 4 arms); final
runner tests (274 passed, 3 skipped); independent verification from raw records (`tools/verify_program.py`, no
problems). Nothing authorised remains. R2 is not extended (owner rule: no repeated testing).

### P2. R2 primary result (prespecified, R2 data only; F14)
K=3, early BC (4k), lambda 0.01 vs 0, normal-start P1 at 501,760 actions on r2_final (128 x 4), training seed
the unit, n = 20 paired seeds:

**d = +0.0097, 95% t-interval [-0.0035, +0.0229], t = 1.53, df 19, p = 0.142** (12/20 seeds positive;
baseline P1 0.093; seed SD 0.028).

Frozen decision: **not supported.** The interval excludes the 0.03 planning effect and the M4 estimate (0.045):
an effect of the size that motivated R2 is ruled out under this protocol; a small effect below about 0.023 is
not. The observed SD was below all planning SDs, so this is not a power failure. Relative to reference values
(descriptive one-sided p for "effect > value"): 0: 0.071; 0.03: 0.998; 0.05: >0.999.
251,904 (descriptive): +0.0099 [-0.0033, +0.0230]. Figures: `reports/r2/paired_effects.svg`, `endpoints.svg`.

### P3. Sensitivity checks (not the decision rule)
Exact sign-flip test over 2^20 patterns p = 0.146; crossed seed x layout bootstrap (10,000, RNG 20261102) 95%
[-0.0071, +0.0260]. Both agree with the t-test. The layouts-only bootstrap [0.0019, 0.0177] holds the 20 trained
policies fixed and ignores training variation, so it is not an interval for the estimand. Descriptive R1+R2
precision-weighted mean +0.014 (approx. 95% [0.003, 0.026]); no p-value; R1 and R2 exist because M4's post hoc
subgroup looked positive (adaptive study selection), so this mean is biased upward if anything.

### P4. Cross-panel (E1; exploratory; F15)
Saved 501,760 actors re-evaluated on both final panels, 4 attempts, new attempt seed. Paired d = 01 - 00:

| cohort / panel | P1 00 | P1 01 | d [95% t] | seed SD | n pos |
|---|---|---|---|---|---|
| M4 (5) / conf_final | 0.064 | 0.105 | +0.041 [+0.017, +0.065] | 0.019 | 5/5 |
| M4 (5) / r1_final | 0.066 | 0.123 | +0.058 [+0.025, +0.091] | 0.026 | 5/5 |
| R1 (8) / conf_final | 0.108 | 0.133 | +0.025 [-0.006, +0.056] | 0.037 | 5/8 |
| R1 (8) / r1_final | 0.128 | 0.148 | +0.020 [-0.008, +0.048] | 0.033 | 6/8 |

The effect follows the trained policies, not the panel: the M4 policies keep a clear gain on R1's panel, and the
R1 policies show a smaller gain on M4's panel. The panel does not explain the larger R1 seed SD. With new attempt
seeds, R1's own-panel d is +0.020 (originally +0.040): part of R1's estimate was attempt-level evaluation noise.
Together with R2, the M4 subgroup effect is best read as a favourable set of five training seeds, not a property of
the method. Figure: `reports/crosspanel/cells.svg`.

### P5. Anchor components (E2; exploratory, 3 seeds, 251,904, development panel; F16)
P1 contrasts (mean [95% t, df 2]): prefix-only -0.010 [-0.059, +0.038]; suffix-only **+0.055 [+0.035, +0.074]**
(3/3 seeds, +0.047 to +0.063); both -0.010 [-0.079, +0.058]; interaction -0.055 [-0.139, +0.030]. The suffix term
lowered suffix-state anchor KL (0.082 vs 0.138); the prefix term (weight 0.0025) hardly changed prefix KL. The
suffix-only result is not consistent with the null "both" arm, which contains the same suffix term; with 3 seeds,
128 attempts per branch and four unadjusted contrasts, it is hypothesis-generating only. No component claim is
made. Figure: `reports/comp/contrasts.svg`.

### P6. Corrected access / completion interpretation
Exact per-seed decomposition dp = dq (r1+r0)/2 + dr (q1+q0)/2, r = P(success | actual arrival) (arithmetic, not
mediation; undefined cases reported, never imputed):

| data | access part | completion part | sum |
|---|---|---|---|
| M4 subgroup E500 (4 defined seeds) | +0.033 | +0.015 | +0.048 |
| R1 E500 (8) | +0.0115 | +0.0288 | +0.040 |
| R2 E500 (20; primary data) | +0.0036 (SD 0.013) | +0.0061 (SD 0.026) | +0.0097 |
| E1 M4 / conf, r1 panels | +0.034, +0.023 | +0.005, +0.026 | |
| E1 R1 / conf, r1 panels | +0.012, +0.008 | +0.012, +0.013 | |

The split is not stable across studies, panels or seeds. **"The preservation gain is mainly access" is withdrawn**
(R1 and R2 do not support it; it holds only in M4's subgroup on its own panel). In R2 neither part differs clearly
from 0. Stage measures (bank bins, KL, timing, visitation) are in `reports/r2/r2_summary.json` (secondary block);
they are descriptive and are not read as p = q x c.

### P7. Measured versus estimated cost, failures and deviations (F17)
Spend 39,643,852 of 50M (total ledger 158,314,282); reserve unused. R2 33.40M (plan 35.13M conservative; ceiling
38M), E1 2.81M (2.90M; 4M), E2 3.36M (3.40M; 4M), final tests 0.06M, development test before freeze 6,032. Each
batch 0.925-0.976 of its conservative estimate. No job failed. Deviations: lost r2-smoke step record (fixed;
conservative 250,000 entered); run_program completion detection (fixed, no job effect); one runner refusal at the
start of xp-r1 because I left an uncommitted file (0 actions; rerun unchanged; DECISIONS). Engineering: heartbeat
fix, atomic writes, interruption drill and exact CPU resume passed (canary and test batches); no interruption
occurred, so no resume was needed.

### P8. Recommendation
**Close the RQ1 line: report preservation at K=3 with early BC as not replicated.** M4's aggregate result
(practically equivalent within +-0.05) stands; R2, the largest and prespecified test, excludes the M4-size subgroup
effect, and E1 is consistent with the earlier estimates coming from a favourable set of trained policies (M4) and
attempt-level evaluation noise (R1).
Do not spend further budget on this effect. The E2 suffix-only signal is the only new lead; it should be pursued
only under a new owner decision with a prespecified design, not as a continuation of this programme.

Manuscript-ready wording (not inserted): "In a prespecified 20-seed replication, preservation at K=3 with early
BC changed normal-start success by +0.010 (95% CI -0.004 to +0.023; p = 0.14), excluding the +0.045 effect seen
in the post hoc M4 subgroup. Re-evaluating the M4 and R1 policies on both test panels showed that the earlier gain
belonged to the trained policies, not the panel."

## R1. Focused replication of the K=3/early-BC preservation effect (Amendment 3; complete)

**Result in one paragraph.** At K=3 with early BC, preservation (lambda 0.01) raised normal-start P1 at 501,760
post-probe actions by **+0.040** (95% t-interval +0.004 to +0.076; unadjusted p 0.033; **Holm-2 p 0.067**).
The frozen decision rule needs Holm-adjusted p < 0.05, so **H1 is not supported**. The checkpoint interaction
(early minus extended) was +0.039 (95% t -0.009 to +0.087; Holm p 0.096), so **H2 is not supported**. By the
frozen interpretation rule the result is **inconclusive**: the interval does not exclude the M4 estimate
(+0.045). It is not a failure to replicate. The estimates are compatible with a positive effect similar to M4's;
interval overlap is not evidence of replication. The seed SD of the effect (0.043) was larger than in the M4
subgroup (0.008). With 8 seeds, power at this SD for an effect of this size was limited (about 0.62 for H1 alone,
lower under Holm-2), not zero. (Corrected 2026-11-01; R1.10.)

### R1.1 Frozen protocol and provenance
- Protocol: `research/PROTOCOL_FREEZE.md` Amendment 3 (C1-C9), frozen in `01beef9` before any R1 data. Owner
  instruction verbatim in `mac-agentic-engineering/project.md` (harness `4d4fc31`).
- Analysis `tools/analyze_r1.py` and statistics `tools/r1_stats.py`, with synthetic tests
  (`tests/test_analyze_r1.py`) committed at the freeze. Power: `tools/power_r1.py` -> `reports/r1/power.md`.
  No analysis code changed after the freeze.
- Design: K=3; BC 4k (early) and 16k (extended) updates from one BC run per seed, on the unchanged joint
  conf-v1 dataset and sampler (`experiments/m4/bc-v1.json`); fresh seeds 15-22; arms 00 (lambda 0) and 01
  (lambda 0.01), both alpha 0, forked from one hash-verified post-probe state; reference = the seed's own BC
  checkpoint.
- Evaluation: new roles r1_select / r1_bank / r1_final (namespaces 112-114, appended; no earlier role changed).
  Final panel 128 layouts x 4 attempts (512 attempts) per policy; bank 64 x 4. The same panel and attempt seeds
  for every seed, arm and checkpoint.
- Data gate (`reports/r1/data_gate.json`): pass. The training files are byte-identical, all conf-v1 roles are
  identical, there is zero overlap with every earlier role, and the bank bins are 32/16/16.
- Reproduction: project commits `01beef9` (freeze) through `dd597ea` (telemetry fix); harness branch
  `mac-host-fixes`, HEAD `4d4fc31`, runner fix `b53f29a` (local only; remote reproducibility is not claimed).
  Package versions: `reports/r1/pip_freeze.txt`. Each batch manifest records both SHAs.
- Verification (corrected 2026-11-01): all **64 endpoint records** (8 seeds x 2 checkpoints x 2 arms x 2
  endpoints; 32 branches) recompute exactly from raw attempt files. The earlier "48 branch summaries" counted the
  16 probe and 32 branch summaries; it was a documentation error (`tools/audit_r1.py`, `reports/r1/audit.json`).
  All fork hashes match. All saved state hashes check (`--check-states`). All completed-job step records equal the
  summary action counts.

### R1.2 Per-seed paired results (P1, 512 attempts per cell)

| Seed | 00 early | 01 early | d_early | 00 ext | 01 ext | d_ext | interaction |
|---|---|---|---|---|---|---|---|
| 15 | 0.148 | 0.150 | +0.002 | 0.490 | 0.457 | -0.033 | +0.035 |
| 16 | 0.074 | 0.100 | +0.025 | 0.477 | 0.492 | +0.016 | +0.010 |
| 17 | 0.061 | 0.162 | +0.102 | 0.445 | 0.436 | -0.010 | +0.111 |
| 18 | 0.160 | 0.246 | +0.086 | 0.469 | 0.480 | +0.012 | +0.074 |
| 19 | 0.156 | 0.191 | +0.035 | 0.525 | 0.563 | +0.037 | -0.002 |
| 20 | 0.049 | 0.043 | -0.006 | 0.449 | 0.480 | +0.031 | -0.037 |
| 21 | 0.148 | 0.229 | +0.080 | 0.559 | 0.518 | -0.041 | +0.121 |
| 22 | 0.150 | 0.148 | -0.002 | 0.494 | 0.492 | -0.002 | 0.000 |
| **Mean** | 0.118 | 0.159 | **+0.040** | 0.489 | 0.490 | **+0.001** | **+0.039** |

d_early is positive in 6 of 8 seeds. The two negative values are small (-0.006, -0.002). Three seeds gain
+0.08 to +0.10.

### R1.3 Primary estimates (501,760 actions; Holm over H1, H2)

| Estimand | Estimate | Seed SD | 95% t (df 7) | p | Holm p | Sign-flip p | Crossed bootstrap 95% | Layouts-only 95% |
|---|---|---|---|---|---|---|---|---|
| H1: d_early | +0.0403 | 0.043 | [+0.004, +0.076] | 0.033 | **0.067** | 0.055 | [+0.006, +0.075] | [+0.027, +0.054] |
| H2: interaction | +0.0391 | 0.057 | [-0.009, +0.087] | 0.096 | **0.096** | 0.125 | [-0.013, +0.093] | [+0.013, +0.065] |
| d_extended (secondary) | +0.0012 | 0.028 | [-0.022, +0.025] | 0.91 | - | 0.91 | [-0.035, +0.039] | [-0.022, +0.024] |

- Decision: neither hypothesis is supported (both Holm p >= 0.05). The frozen interpretation cell is
  "inconclusive", because the H1 upper bound (0.076) is above the M4 estimate (0.045).
- Magnitude: the d_early interval includes 0.05, so the effect is "not distinguishable from the 0.05 practical
  threshold". Relative to ordinary PPO with early BC (0.118), +0.040 is +34%.
- Layout sensitivity: the crossed seed x layout bootstrap also excludes 0 for H1 and includes 0 for H2.
  Layout sampling alone gives narrow intervals for both, so the seed spread is the dominant uncertainty, not the
  panel. These are sensitivity checks. They do not replace the Holm decision.
- The interaction's sign pattern comes from the early checkpoint: the extended-BC effect is close to zero at
  501,760.

### R1.4 Descriptive checkpoint (251,904 actions; unadjusted, no claims)

| Estimand | Estimate | 95% t | Seeds positive |
|---|---|---|---|
| d_early | +0.030 | [+0.016, +0.043] | 8/8 |
| d_extended | +0.042 | [+0.014, +0.070] | 7/8 |
| interaction | -0.012 | [-0.030, +0.006] | - |

At 251,904, preservation is ahead with both checkpoints. With extended BC, ordinary PPO then catches up
(P1 0.389 -> 0.489 against 0.431 -> 0.490), so the extended-BC effect disappears by 501,760. With early BC,
the effect is still present at 501,760. So the 501,760 interaction mostly shows that the extended-BC
advantage closes earlier. This is a descriptive pattern and is not tested.

### R1.5 Secondary stages (501,760; difference 01 - 00, 95% t over seeds; descriptive)

| Measure | Early BC | Extended BC |
|---|---|---|
| P1 | +0.040 [+0.004, +0.076] | +0.001 [-0.022, +0.025] |
| q (stage access) | +0.038 [+0.012, +0.065] | -0.022 [-0.038, -0.007] |
| P(success given arrival), seeds with both defined | +0.061 [-0.009, +0.132] | +0.023 [-0.004, +0.051] |
| C4 (any of 4) | +0.076 [+0.006, +0.146] | +0.018 [-0.014, +0.049] |
| R4 (all 4) | +0.009 [-0.003, +0.020] | -0.040 [-0.072, -0.008] |
| Fixed-bank c | +0.029 [-0.041, +0.098] | +0.019 [-0.020, +0.057] |
| Bank entry / retrieval / carrying | +0.031 / +0.035 / +0.018 (all CIs include 0) | -0.001 / -0.004 / +0.080 (all include 0) |

- (Corrected 2026-11-01.) The earlier reading "the gain is mainly access" is withdrawn. It compared a significant
  q difference with a non-significant bank difference, and q and fixed-bank c are on different scales. The exact
  per-seed decomposition of dp into access and arrival-conditioned completion (R1.10) gives, with early BC at
  501,760: access part +0.0115 and completion part +0.0288 (71% of +0.040). Fixed-bank c is not r and is not
  used in it.
- With extended BC, preservation slightly lowers access and all-4 reliability. Its P1 is unchanged.
- Anchor KL to pi0 (mean over training) is 0.093 vs 0.162 (early) and 0.088 vs 0.159 (extended): the anchor
  does what it is meant to do. Arrival time (~80 steps early, ~54 extended) and inventory are the same in both arms.
  No branch has zero arrivals.
- Starting points (mean over seeds, r1_select): early pi0 p 0.056 -> probe 0.076; extended pi0 0.358 -> probe
  0.387. Ordinary PPO with early BC reached 0.118 at 501,760, against 0.062 in the M4 subgroup. The panel,
  layouts and seeds are different, so these baselines are not directly comparable.

### R1.6 Comparison with the M4 post hoc estimate (separate; not pooled)

| | M4 post hoc subgroup (F11) | R1 (prespecified) |
|---|---|---|
| Seeds / panel | 10-14 (5) / conf_final 64 x 8 | 15-22 (8) / r1_final 128 x 4 |
| d_early at 501,760 | +0.045 [+0.035, +0.055] | +0.040 [+0.004, +0.076] |
| Seed SD of d_early | 0.008 | 0.043 |
| Seeds positive | 5/5 | 6/8 |
| Interaction at 501,760 | +0.073 [+0.038, +0.108] | +0.039 [-0.009, +0.087] |

- The point estimates are close. The estimates are compatible with a positive effect similar to M4's; interval
  overlap is not proof of replication.
- (Corrected 2026-11-01.) The M4 subgroup's seed SD (0.008) was the smallest of the 8 M4 cells, and R1's (0.043)
  lies between the M4 median (0.028) and maximum (0.057). Possible reasons, not separated: post hoc selection of
  the subgroup; small-sample variance estimation (an SD from 5 values is very imprecise); panel differences
  (conf_final 64 x 8 vs r1_final 128 x 4, different layouts); and training-path variability. The cross-panel
  study (Amendment 4, E1) tests the panel part. At SD 0.043 and a true effect of 0.040, the chance that 8 seeds
  pass H1 alone is about 0.62. It is lower under Holm-2.
- The M4 interaction was smaller in R1 and is not confirmed.

### R1.7 Costs, failures and exclusions
- **Spend (corrected 2026-11-01):** R1 used **25,471,227** environment actions (ledger 93,199,203 -> 118,670,430;
  first reported as 25,471,099 before the 128-action failed-job correction, R1.10), which is 89.7% of the
  28.4M authorization. 2.93M was not used. The conservative plan was 26.97M and the expected cost 25.54M. Every
  batch exited 0 and cost less than its conservative estimate. Completion was secure at every admission.
- **Batches:** data `20261101T001930-86871` (32,184); tests `20261101T001959-87087` (59,274); canary
  `20261101T002041-87256` (1,002,393); seed 15 rest `20261101T002815-88091`; seed 16 `20261101T003945-89279`;
  failed seed 17 `20261101T005849-94851` (86,223 by step record, kept); seeds 17-22 `20261101T010311-99104`, `T012123-1751`,
  `T013935-7336`, `T015804-10217`, `T021657-15496`, `T023515-17380` (3.13M to 3.18M each); final tests `20261101T025500-19209` (266 passed, 3 skipped).
- **One failure:** the first seed 17 BC job stopped on a heartbeat-file race in `src/bc2rl/telemetry.py`. Two
  threads shared one temporary file name. This was classified as a deterministic code defect. It was fixed
  with per-process and per-thread names, plus a test that fails on the old code (`dd597ea`). The seed was rerun
  under a new batch ID with the same seed. The failed run and its 86,223 actions stay in the record and the
  ledger. No new canary was run, because only the heartbeat write changed (DECISIONS).
- **Exclusions:** none. All 8 seeds and 32 branches are complete. No seed was replaced. No design element
  changed after the freeze, and the canary's outcome was not read before all seeds finished.

### R1.8 Interpretation
- **What R1 shows.** The preservation effect at K=3 with early BC is positive in direction and similar in size
  to M4 (+0.040 vs +0.045). The unadjusted test and the crossed bootstrap both exclude zero. But the prespecified
  confirmatory test (Holm over 2) does not reach 0.05. So **R1 does not confirm the benefit, and it does not
  refute it.** R1 did not meet its frozen Holm-2 criterion. Its estimates are compatible with a positive effect
  similar to M4's (corrected 2026-11-01).
- **Checkpoint dependence is not established.** At 501,760 the extended-BC effect is zero and the interaction is
  positive but not significant. At 251,904 both checkpoints benefit to a similar degree. The best-supported
  description is that preservation speeds up early learning with both checkpoints, and the advantage lasts
  longer with early BC. This is descriptive only.
- **Seed variance matters for planning.** The seed SD in R1 was larger than in the M4 subgroup. The reasons are
  not separated (R1.6). Claims that rest on five seeds and a selected subgroup are fragile here.
- **Unchanged:** the M4 aggregate equivalence result (C2) stands as it was. R1 does not modify or pool with it.

### R1.9 One next research question (proposal; superseded 2026-11-01 by the owner's R2 design, Amendment 4)
**Does preservation improve K=3/early-BC P1 at 501,760 when tested as a single prespecified hypothesis with
enough seeds for the observed spread?** Test only the early checkpoint (BC, early probe, arms 00/01; about
1.81M actions per seed, conservative). Plan with R1's seed SD of 0.043. A single two-sided test at 0.05 needs
about 12 fresh seeds for 80% power at +0.040, or about 20 for +0.030 (simulation, planning only). That is about
22M to 36M actions. Pooling with R1 would need to be fixed in advance and is not assumed here. This waits for an
owner decision. R1 has stopped scientific execution, and nothing further was started.

### R1 manuscript-ready wording (not inserted into the manuscript)

> In a prespecified replication with eight fresh training seeds and a new 128-layout evaluation panel,
> preservation (lambda = 0.01) at K = 3 with early BC improved normal-start success after 501,760 continuation
> actions by 0.040 (95% CI 0.004-0.076; 6 of 8 seeds positive; baseline 0.118), close to the post hoc estimate
> from the main study (0.045). The effect did not survive the prespecified Holm correction over two hypotheses
> (adjusted p = 0.067), and the checkpoint interaction was not supported (0.039, 95% CI -0.009 to 0.087;
> adjusted p = 0.096). The replication is therefore inconclusive rather than negative; its estimates are
> compatible with a positive effect similar to the original. In an exact decomposition of the success difference,
> about 29% came from more frequent arrival at the final stage and about 71% from higher completion after arrival.
> At 251,904 actions preservation was ahead with both BC checkpoints. *(Corrected 2026-11-01.)*

### R1.10 Targeted audit (2026-11-01, before R2; `tools/audit_r1.py`, `reports/r1/audit.json`)

Independent of `tools/analyze_r1.py`: raw attempt files, summaries, configs, step records and the registry.
- **Inventory (exact):** 13 batches; 8 complete BC jobs + 1 failed (seed 17, batch `20261101T005849-94851`, no
  summary, partial checkpoint kept); 16 probes; 32 branches; **64 endpoint records**, each 512 normal attempts
  (128 x 4) and 256 bank attempts (64 x 4); 2 runner test jobs; 1 data job. No record is missing or duplicated.
- **Roles and panel:** every branch config names r1-v1, r1_final, r1_bank, r1_select. The per-item time limits of
  all 64 records equal the r1_final K=3 registry in order, and all 64 records share one identical panel.
- **Lineage:** every branch carries its probe's fork hash. Every probe references its own seed's BC job (seed 15's
  extended probe references the canary batch, by design).
- **Statistics:** P1, d_early, d_extended, the interaction, the t-tests (own t CDF by numerical integration) and
  Holm-2 reproduce the frozen values exactly (H1 p 0.0335, Holm 0.0670; H2 p 0.0957, Holm 0.0957).
- **Actions:** step records of all R1 jobs total **25,471,227**, against the ledger's 25,471,099. The 128-action
  gap is the failed seed 17 BC job: it ran 128 evaluation actions after its last metrics row. `tools/ledger.py` now
  takes the step record when it is larger for a job without a summary (role `partial_unrecorded`). R1's corrected
  spend is 25,471,227; the ledger total is 118,670,430.
- **Failure record:** the runner ledger records the failed batch as stopped (job_failed). Its files are kept.

**Exact decomposition** (per seed, `reports/r1/decomposition.csv`): dp = dq (r1 + r0)/2 + dr (q1 + q0)/2, with r
= P(success | actual arrival) on the normal-start panel. This is arithmetic, not causal mediation: each policy
reaches a different arrival-state distribution. All 8 seeds have r defined in both arms.

| R1 cell | dp mean (SD) | access part mean (SD) [95% t] | completion part mean (SD) [95% t] | access share |
|---|---|---|---|---|
| E500 early | +0.040 (0.043) | +0.0115 (0.010) [+0.003, +0.020], 7/8 > 0 | +0.0288 (0.038) [-0.003, +0.061], 6/8 > 0 | 29% |
| E500 extended | +0.001 (0.028) | -0.0152 (0.013) [-0.026, -0.004], 1/8 > 0 | +0.0165 (0.023) [-0.003, +0.036], 6/8 > 0 | - |
| E250 early | +0.030 (0.016) | +0.0080 (0.008) [+0.001, +0.015] | +0.0218 (0.011) [+0.013, +0.031], 8/8 > 0 | 27% |
| E250 extended | +0.042 (0.033) | +0.0215 (0.031) [-0.005, +0.048] | +0.0205 (0.011) [+0.011, +0.030], 8/8 > 0 | 51% |

The same decomposition of the M4 subgroup (K=3, early BC, E500; `reports/r1/m4_decomposition.json`): seed 13's
ordinary arm never arrived (q 0), so its split is undefined and not imputed. Over the other 4 seeds: dp +0.047,
access part +0.033 (SD 0.014), completion part +0.015 (SD 0.020).

**Corrected interpretations.**
1. R1 did not meet its frozen Holm-2 criterion. This stands.
2. R1's estimates are compatible with a positive effect similar to M4's. Interval overlap is not proof of
   replication.
3. Eight seeds had limited power at the R1 SD (about 0.62 for H1 alone at +0.040), not zero power.
4. The larger SD is not attributed only to subgroup selection: small-sample variance estimation, panel differences
   and training variability are also possible (E1 tests the panel part).
5. "Mainly access" is withdrawn for R1. With early BC at E500 the completion part is the larger share (about 71%).
   In the M4 subgroup the access part was larger (about 69% over 4 defined seeds). So the split was not stable
   across the two studies, and neither study supports a general "mainly access" statement. The M4 manuscript
   wording ("mainly through retained stage access", section "Manuscript-ready wording") is qualified accordingly:
   it describes the M4 subgroup only.

## C1. Final protocol and provenance

| Event | Commit / batch | Time (EDT, 2026-10-31 unless noted) |
|---|---|---|
| Original freeze (250k endpoint, conf_final 32 x 16) | `7f94f18`; freeze SHA-256 `2b5c5252...` | 2026-10-30 19:57:01 |
| Amendment 1 first written (64 layouts x 8 attempts; diagnostics on conf_select) | `d928291` | 01:37:00 |
| Owner decision ("option A for both 250K and 500K"; cap not binding) | harness `ea3d7ad` (verbatim) | before 10:41 |
| Amendment 1 approved; **Amendment 2 adds E500 as a second confirmatory endpoint** | `39c7901`; freeze SHA-256 `2037aa14...` | 10:41:34 |
| conf-v1 data generated (first confirmation data) | batch `20261031T144204-65491` | 10:42:04-10:43:57 |
| Seed batch s10 starts | batch `...144443-65814` at `ccfe8c6` | 10:44:43 |
| M4 analysis code committed | `c53b63f` | 10:47:03 |
| First conf_final outcome written | `m4-K3-u4000-s10-00/attempts_final_251904.jsonl` | 10:52:55 |

- The 64 x 8 design was first written at 01:37 and fixed by approval at 10:41. Both endpoints became
  confirmatory at 10:41:34. Both came before any confirmation data existed. The analysis code was committed
  about 6 minutes before the first conf_final outcome.
- Prespecified in the freeze text before data: the estimand, the three primary contrasts (family of 6 with
  both endpoints, Holm), TOST at ±0.05, the verdict rules, and the t-interval and crossed bootstrap.
- Implementation choices made in code, not in the protocol text:
  - Resampling K=1 and K=3 layouts independently. The freeze did not address cross-K matching; a matched
    version agrees within 0.0014 (C2).
  - The verdict labels for secondary rows.
- Committing the code before outcomes does not by itself prove that every analysis choice was prespecified.
- Hypotheses:
  - Primary: reset, preservation and combined vs ordinary PPO, equal-weight over the 4 strata, at E250 and E500.
  - Secondary (pointwise, descriptive): interaction, 11-10 and 11-01; the same contrasts in q, c, C4, R4 and
    P(success | arrival); per-stratum contrasts.
  - Descriptive: curves, E500 - E250 changes, moderation D, diagnostics.
  - Everything in C3-C7 beyond those lists is post hoc.
- Budget:
  - The project's 80M cap stopped being binding by owner decision. The owner set no new numeric hard budget.
  - Amendment 2's 109M was a submission stop line that I set. It was not reached.
  - Amendment 1's protected reserve (>= 10.23M) was part of the A8 budget rules, which Amendment 2 replaced
    without restating a reserve. No reserve was in force during M4.
- Reproduction:
  - Every batch directory archives the exact project source (`code/`) and a manifest with the project SHA,
    harness SHA and interpreter.
  - Seed 10 ran project `ccfe8c6`; seeds 11-14 ran `c53b63f`. These differ only in tools, tests and state
    text, not in `src/` or `experiments/`. Data ran at `39c7901`.
  - The harness at execution was `ea3d7ad` on local branch `mac-host-fixes`. Its runner code is `b53f29a`,
    which carries a macOS process-group fix that is not on the harness `main`.
  - The harness has no remote, so these harness commits are **local only**. The project repository is pushed
    to `origin`. Remote reproduction of the runner fix, and of the run artifacts in `.mae/` and `data/`
    (git-ignored), is therefore not available.

## C2. Aggregate result (prespecified; F11 section 1)

| Endpoint | Contrast | Estimate | 95% t (df 4) | TOST p (t_L / t_U) | Holm-6 p |
|---|---|---|---|---|---|
| 251,904 | reset | -0.011 | [-0.031, +0.009] | 0.0027 (5.49 / -8.49) | 1.00 |
| 251,904 | preservation | -0.006 | [-0.029, +0.016] | 0.0028 (5.45 / -6.98) | 1.00 |
| 251,904 | combined | -0.020 | [-0.047, +0.008] | 0.0191 (3.05 / -7.08) | 0.68 |
| 501,760 | reset | +0.004 | [-0.016, +0.023] | 0.0015 (7.49 / -6.48) | 1.00 |
| 501,760 | preservation | +0.003 | [-0.015, +0.021] | 0.0009 (8.32 / -7.34) | 1.00 |
| 501,760 | combined | +0.004 | [-0.028, +0.035] | 0.0077 (4.68 / -4.05) | 1.00 |

- **Reproduction.** Recomputed independently from raw attempts. Verified:
  - 5 seed blocks.
  - One BC path per seed supplying both checkpoints.
  - Equal stratum weights.
  - Arms paired within a fork; endpoints paired within a branch.
  - Episodes, checkpoints and endpoints never treated as replicates.
- **Directional and equivalence tests.**
  - Directional claims use Holm over 6 tests; none is made.
  - Equivalence uses TOST per contrast (p_TOST = max of the two one-sided p-values).
  - The joint statement "all six within ±0.05" is an intersection-union test: every p_TOST < 0.05, so it holds
    at level 0.05. Holm over the six TOST p-values gives the same result.
- **Uncertainty scope.**
  - The t-interval is conditional on the fixed 64-layout panel per K. That panel is shared by every seed.
  - The crossed seed x layout bootstrap also samples layouts. It agrees with the t-interval, but it is a
    sensitivity check, not replication.
  - conf_final layouts are matched across K. A matched-index bootstrap changes no interval endpoint by more
    than 0.0014 (`reports/postm4/primary.csv`).
- **What this does not establish.** Equivalence in every condition, no change of any kind, equal learning
  curves, the absence of any useful intervention in this task family, or the outcome beyond 501,760.

## C3. Condition-level effects (paired seed differences; F11 sections 2-3)

Mean paired difference, pointwise 95% t-interval (df 4) and seeds positive. Bold: pointwise p < 0.05.
Per-stratum contrasts are secondary or descriptive under the freeze. Figure: `reports/postm4/effects.svg`.

| Endpoint | Condition | Arm-00 P1 | Reset 10-00 | Preservation 01-00 | Combined 11-00 |
|---|---|---|---|---|---|
| E250 | K=1, early BC | 0.508 | -0.042 [-0.089, +0.005] 1/5 | **-0.048 [-0.077, -0.019] 0/5** | -0.057 [-0.122, +0.008] 0/5 |
| E250 | K=1, extended BC | 0.729 | +0.001 [-0.036, +0.039] 3/5 | -0.004 [-0.044, +0.036] 2/5 | -0.008 [-0.051, +0.036] 2/5 |
| E250 | K=3, early BC | 0.046 | +0.021 [-0.008, +0.050] 4/5 | +0.023 [-0.028, +0.075] 4/5 | +0.024 [-0.002, +0.050] 4/5 |
| E250 | K=3, extended BC | 0.355 | -0.023 [-0.078, +0.032] 2/5 | +0.004 [-0.067, +0.075] 3/5 | -0.039 [-0.084, +0.007] 1/5 |
| E500 | K=1, early BC | 0.551 | +0.000 [-0.059, +0.060] 3/5 | -0.001 [-0.031, +0.029] 3/5 | -0.018 [-0.067, +0.031] 2/5 |
| E500 | K=1, extended BC | 0.766 | -0.013 [-0.027, +0.002] 1/5 | -0.005 [-0.046, +0.037] 3/5 | +0.011 [-0.043, +0.064] 3/5 |
| E500 | K=3, early BC | 0.062 | +0.031 [-0.010, +0.072] 4/5 | **+0.045 [+0.035, +0.055] 5/5** | +0.043 [-0.001, +0.086] 4/5 |
| E500 | K=3, extended BC | 0.406 | -0.004 [-0.070, +0.062] 3/5 | -0.027 [-0.057, +0.003] 1/5 | -0.021 [-0.072, +0.030] 2/5 |

- **Preservation, K=3/early BC, 501,760: +0.045, from baseline 0.062 (+73% relative).**
  - Pointwise statistics: t = 12.5, p = 0.00023. After Holm over the 24 arm-vs-00 contrasts, p = 0.0056; over
    the 48 contrasts examined in F10, p = 0.011.
  - Exact sign-flip p is 0.0625, the smallest possible with 5 seeds. The t-based p rests on near-normal seed
    differences and a seed SD (0.008) estimated from 5 values.
  - Robustness checks:
    - Crossed seed x layout bootstrap: [+0.022, +0.074].
    - Leave-one-seed-out: 0.042-0.047.
    - Leave-one-layout-group-out: 0.040-0.052, every interval above 0.
  - The gain is broad but uneven across layouts: 36 positive, 12 negative and 16 zero of 64; the top 10 carry
    66% of the net gain.
  - Seed 13's ordinary-PPO branch has zero arrivals. It is kept as valid data.
- **What accompanies it** (descriptive): higher access in every seed (+0.10 to +0.19 q).
  - Arrival timing is similar, and arrival-conditioned completion is similar (0.27 vs 0.28 pooled).
  - On the same fixed bank states, ordinary PPO stays near pi0 (entry c 0.26 vs 0.28 at pi0; retrieval falls
    0.48 -> 0.39). Preservation keeps retrieval and carrying near or above pi0 and raises entry c beyond pi0
    (0.37).
  - Ordinary PPO drifts furthest from pi0 in this condition (anchor KL 0.36 vs 0.16-0.20 elsewhere).
  - This is consistent with preservation protecting fragile BC behavior when access is low. It is not a causal
    demonstration.
- **Checkpoint dependence (post hoc).** At K=3 and 501,760, the preservation effect at early minus at extended
  BC is +0.073 [+0.038, +0.108]. At K=1 and 251,904 it is -0.044 [-0.070, -0.018]. Averaging checkpoints hides
  these.
- **Three-way intervention x K x checkpoint (post hoc, 6 tests).** Preservation at 501,760: +0.069 [+0.005,
  +0.132], p 0.040. Reset at 251,904: +0.088, p 0.027. Neither survives Holm over 6.
- **Arrival inventory.** Every K=3/early-BC arrival carries the yellow key in both arms, and timing is similar.
  The access gain is not a change in what the agent carries on arrival.
- **Status.** This is a post hoc subgroup. It is not promoted to a primary result and needs independent
  replication (C9).

## C4. Competence bank, progress-matched (F11 section 4)

- The planner bank mixes progress levels: 32 entry, 16 retrieval and 16 carrying states, equal weight per
  state. Mixed c = 0.5 entry + 0.25 retrieval + 0.25 carrying. Boundary arrivals correspond to the entry bin.
- **Example verified** (M3 K=3/16k seed 0, ordinary PPO):
  - Planner bank: mixed c 0.594, entry 0.391, retrieval 0.750, carrying 0.844.
  - Own arrival bank: 0.385.
  - The gap of 0.209 shrinks to 0.006 after progress matching, so composition explains 97%.
- **Development arrival banks** (6 own-bank cases): composition explains about 78% of the mixed-bank gap on
  average.
  - Entry-minus-arrival gaps range from -0.07 to +0.14.
  - Arrival competence exceeds planner entry competence in 2 cases.
  - There is no uniform mismatch.
- **M4** (entry c on conf_bank vs own-arrival r on conf_final):
  - Mean r - entry: -0.004 at K=1 and -0.056 at K=3. The K=3 arrivals have less remaining time (median 57-94
    vs 104) and come from different layouts.
  - Mixed - entry: +0.079 (K=1) and +0.102 (K=3).
- **Estimands.** The mixed bank is a valid declared nu, and its score is a distribution-specific measure. It is
  not completion from boundary entry. The existing data cannot separate time from layout at K=3.
- No causal link between bank-score changes and the small average P1 effects is established.

## C5. Access vs arrival-conditioned completion (F11 section 5)

- **Identity.** Per branch, p = q x r exactly (r = completion given actual arrival, not mixed-bank c; checked on
  all 160 records).
- **Weighting.** The quoted 501,760 aggregates (ordinary p 0.4463, q 0.7057, r 0.6324; preservation 0.4494,
  0.7459, 0.6025) are verified. Here r = total successes / total arrivals, which weights K=1 most heavily.
- **Decomposition.** Within seed x stratum, preservation's +0.003 at 501,760 splits into:
  - access +0.008,
  - arrival-conditioned completion -0.007,
  - unsupported +0.002 (one cell with q = 0, where r is undefined and not imputed).
  At 251,904: -0.006 = +0.005 access, -0.013 completion, +0.002 unsupported.
- **Interpretation.** Access gains partly cancel lower r. Because r averages over policy-dependent arrival
  states, a lower r does not show a fixed skill deteriorating.

## C6. Secondary outcomes, curves and optimization (F11 section 6)

- **Coverage and reliability** (secondary, pointwise, unadjusted; 24 pooled secondary-metric contrasts).
  Preservation at 501,760: C4 +0.033 [+0.010, +0.056], R4 -0.019 [-0.037, -0.001].
  - This means more layouts with at least one success and fewer with all successes: success is redistributed
    across layouts at similar mean P1.
  - It is not evidence of generalization, policy-support expansion or broad retention.
- **Curves.**
  - Endpoint equivalence is not curve equivalence.
  - Some early deficits close later: reset +0.014 and combined +0.024 between endpoints; preservation +0.047 at
    K=1/early BC.
  - Descriptive curves are tabulated below (means over 5 seeds; `reports/postm4/extras.json`). There is no
    area-under-curve test and no per-arm best checkpoint.
  - "sel" columns are conf_select normal starts: 64 x 2 attempts at pi0 and the probe, 64 x 1 at the curve
    points. "final" columns are conf_final, 64 x 8.
  - These are different layout sets. Compare only within a set, never across sets.

| Condition | Arm | sel pi0 | sel probe | sel 126,976 | sel 376,832 | final 251,904 | final 501,760 |
|---|---|---|---|---|---|---|---|
| K=1, early | 00 | 0.266 | 0.361 | 0.444 | 0.566 | 0.508 | 0.551 |
| K=1, early | 10 | 0.266 | 0.361 | 0.463 | 0.547 | 0.466 | 0.552 |
| K=1, early | 01 | 0.266 | 0.361 | 0.466 | 0.547 | 0.460 | 0.550 |
| K=1, early | 11 | 0.266 | 0.361 | 0.431 | 0.569 | 0.451 | 0.533 |
| K=1, extended | 00 | 0.633 | 0.684 | 0.766 | 0.828 | 0.729 | 0.766 |
| K=1, extended | 10 | 0.633 | 0.684 | 0.719 | 0.787 | 0.730 | 0.753 |
| K=1, extended | 01 | 0.633 | 0.684 | 0.713 | 0.784 | 0.725 | 0.761 |
| K=1, extended | 11 | 0.633 | 0.684 | 0.722 | 0.797 | 0.721 | 0.776 |
| K=3, early | 00 | 0.052 | 0.039 | 0.047 | 0.053 | 0.046 | 0.062 |
| K=3, early | 10 | 0.052 | 0.039 | 0.056 | 0.119 | 0.067 | 0.093 |
| K=3, early | 01 | 0.052 | 0.039 | 0.072 | 0.097 | 0.069 | 0.107 |
| K=3, early | 11 | 0.052 | 0.039 | 0.053 | 0.116 | 0.070 | 0.105 |
| K=3, extended | 00 | 0.275 | 0.302 | 0.306 | 0.425 | 0.355 | 0.406 |
| K=3, extended | 10 | 0.275 | 0.302 | 0.375 | 0.416 | 0.332 | 0.402 |
| K=3, extended | 01 | 0.275 | 0.302 | 0.353 | 0.397 | 0.359 | 0.379 |
| K=3, extended | 11 | 0.275 | 0.302 | 0.347 | 0.391 | 0.316 | 0.386 |

- **Optimization.**
  - Actor lr 3e-5. Gradient-norm clipping at 0.5 is active in every update (median pre-clip norm about 2.4).
  - Per update: PPO clip fraction about 0.027, approx KL about 0.003. Anchor KL to pi0 grows 0.09 -> 0.22 in
    ordinary PPO.
  - P1 still rises between endpoints (+0.037).
  - Whether step size is the bottleneck is untested.

## C7. Execution and accounting

- **Execution.** 20 forks and 160 branch-endpoint records verified (F11 section 8):
  - lineage;
  - fork hashes and all 160 saved-state hashes;
  - per-item time limits proving that diagnostics and curves used conf_select while endpoints used conf_final;
  - pairwise zero overlap among conf_select, conf_bank, conf_final and every dev role;
  - 32/16/16 banks matched across K;
  - full metric recomputation;
  - missing conditional statistics kept as missing.
  - No failures and no retries.
- **Ledger** (`tools/ledger.py`, at this commit): 93.14M total, not an exact count.
  - Runner-measured: 89.57M. This includes 1.31M of data planner replay, derived from layout lengths.
  - Outside the runner, estimated: 3.45M (conservative; point estimate about 3.1M).
  - Outside the runner, measured: 0.12M (two test-suite runs under the new accounting).
  - M4 itself: 55.85M, all runner-measured.
- **Accounting fix.** `src/bc2rl/accounting.py` counts every `StageTask.step`.
  - Outside the runner, it records per-process totals in `.mae/unmanaged_actions/`, which the ledger adds as
    measured.
  - It stops a process after 1M unmanaged steps (`BC2RL_UNMANAGED_ACTION_LIMIT`).
  - Tests: `tests/test_accounting.py`.
  - It does not enforce CPU or memory limits outside the runner.
- **Environment.** The battery watch (5-minute checks; stop below 20%) ran throughout. No watcher or worker
  from M4 remained.

## C8. Research questions

- **RQ1 (when do the interventions help?).**
  - On average, none of the three changes P1 by more than ±0.05 at either budget.
  - Condition-level evidence suggests that preservation helps when early BC meets low access (K=3/early BC),
    where ordinary PPO drifts from pi0 and loses access in some seeds. Preservation transiently costs early
    performance when access is already full (K=1/early BC).
  - Hypotheses from the manuscript:
    - "Low access with substantial competence predicts a benefit from demonstration starts" (K=3/extended
      BC): not supported (reset -0.004 at 501,760).
    - "Declining competence predicts a benefit from preservation": descriptively consistent in K=3/early BC,
      not tested confirmatorily.
- **RQ2 (can early measurements select useful interventions on held-out conditions after cost?).**
  - It remains a proposal, but not because heterogeneity is absent. Demonstrated selection headroom is small:
    - the in-sample hindsight per-condition best minus best fixed arm is +0.010 at 501,760 and +0.007 at
      251,904;
    - a zero-cost condition-identity rule gains about 0 out of sample (leave-one-seed-out, same conditions:
      +0.0006 vs the fixed arm chosen the same way).
  - No held-out conditions exist. An early-measurement selector must beat the condition-identity rule after
    charging diagnostic and trial costs.
  - **Cost.** The pi0 and post-probe diagnostics cost 37k-73k actions per condition, 7-15% of a 501,760
    continuation. The shared probe is not charged. A short-trial selector costs several branches. Neither cost
    can be recovered from an out-of-sample gain of about 0.

## C9. Recommendation: one follow-up, R1 (approved 2026-10-31 and executed as Amendment 3; result in section R1)

**R1. Independent replication of the conditional preservation effect.**
- **Question.** Does preservation (lambda 0.01) improve normal-start P1 at K=3 with early BC, and does its effect
  depend on the BC checkpoint, on fresh training seeds and fresh evaluation layouts?
- **Design.**
  - K=3 only; BC 4k and 16k from one BC run per seed; arms 00 and 01 from a shared post-probe fork.
  - **8 fresh seeds (15-22).**
  - Frozen endpoint 501,760, evaluated at 64 x 8 normal starts and a 64 x 4 bank. 251,904 is evaluated as a
    descriptive point.
  - New registry roles appended after conf_final (rep_select, rep_bank, rep_final), so no existing role changes.
    The training-role byte gate applies as before.
  - PPO, probe, alpha and lambda unchanged. The protocol and analysis are frozen before data.
- **Primary tests (Holm, family of 2).** H1: the preservation effect at K=3/early BC at 501,760 (two-sided paired
  t, df 7). H2: the checkpoint x preservation interaction at K=3 (effect at 4k minus at 16k).
- **Secondary.** The effect at K=3/extended BC; the q/r decomposition; fixed-bank entry, retrieval and carrying
  c; the 251,904 point.
- **Precision** (80% power, first Holm step).
  - Minimal detectable effect: 0.011 / 0.032 / 0.040 / 0.066 at paired seed SD 0.008 / 0.024 / 0.03 / 0.05.
  - The observed effect (0.045) is detectable if the SD is at most 0.034. Observed SDs: 0.008 at K=3/early BC
    and 0.024 at K=3/extended BC; the interaction SD was 0.028.
- **Cost** (conservative, from measured M4 maxima). Per seed:
  - BC evaluation 0.151M;
  - 2 probes 0.288M;
  - 4 branches 2.705M (501,760 training each plus evaluation at both points);
  - total 3.144M per seed.
  Eight seeds: 25.2M. Data about 0.5M and tests about 0.1M bring the total to **about 25.8M** (continuation
  alone 16.1M). Five seeds would cost 15.7M but could detect 0.045 only if the SD is at most 0.023. Wall time
  about 3 h. Proposed stop line: 1.10 x 25.8M = 28.4M.
- **What it can support:** confirmatory replication of a condition-specific preservation benefit, and of its
  checkpoint dependence, at this lambda, task and budget.
- **What it cannot support:** K=1 claims, causal mechanism, other doses, tasks or budgets, or RQ2 selection
  value.
- **Why not the measurement-validity study (B).** Existing artifacts resolve most of the bank question (C4).
  The remaining K=3 difference (about 0.056) mixes time and layouts and does not change the RQ1 interpretation.
  It can wait. Any later prefix-state test must hold success-relevant variables fixed. A clock extension changes
  both time and the policy's time input, so it is not a pure test of time. Arrival-aligned resets or anchors
  would be a new intervention and would be named as one.

## Manuscript-ready wording (not inserted into the manuscript)

> Across five paired training seeds and four conditions (prerequisite length K in {1, 3} x early or extended BC),
> demonstration-state starts (alpha = 0.25), forward-KL preservation toward the BC policy (lambda = 0.01) and their
> combination were practically equivalent to standard PPO in equal-weight average normal-start success after
> 251,904 and 501,760 continuation actions (all six TOST p < 0.02 for a ±0.05 margin; largest absolute estimate
> 0.020). Averages concealed condition-dependent effects. In a post hoc analysis, preservation improved success
> with early BC and the longer prerequisite (K = 3) by 0.045 (95% CI 0.035-0.055; 5 of 5 seeds; baseline 0.062),
> in that subgroup mostly through more frequent arrival at the final stage *(qualified 2026-11-01: the split was
> not reproduced in R1)*, while it transiently reduced success with early BC at K = 1 (-0.048 at
> 251,904; 0.00 at 501,760). Later-stage competence measured on a fixed saved-state bank depended strongly on the
> bank's progress composition: when compared at the stage boundary, planner-state competence was close to
> competence on the policy's own arrival states (mean difference -0.004 at K = 1, -0.056 at K = 3).

**Does the proposed conclusion survive?** "Small average effects coexist with possible condition-dependent
preservation benefits, and the interpretation of competence depends strongly on the saved-state distribution."
It survives with two refinements:
1. The condition dependence includes a transient preservation cost at K=1/early BC, not only a benefit.
2. "Saved-state distribution" mainly means its progress composition. After progress matching, entry-state
   competence approximates arrival competence at K=1 and is modestly higher at K=3.

## Superseded statements (kept in their original places, marked)
- F10 / earlier report: "Per-stratum arm differences are all within the seed-to-seed spread" and "No stratum
  shows an arm difference outside the seed-to-seed spread". These are withdrawn; they used an unpaired
  criterion (C3).
- "The interventions neither accelerate nor stall it [learning]". Withdrawn (C6).
- "Every effect larger than 0.05 P1 in either direction is excluded". This holds for the aggregate estimand only
  (C2).
- Review 4: "this is evidence of no useful effect, not a lack of evidence". This holds only for the average
  effect (C2, C3).
- "PPO is step-size-limited". Downgraded to a hypothesis (C6).
- F9 / report section 4: "competence on actual arrival states is below planner-bank c for every policy". Mostly
  progress composition, and not uniform (C4).
- "RQ2's condition (useful heterogeneous effects) is not met". Replaced by C8.
- "Ledger 93.02M" as one figure. It is now split into measured and estimated parts (C7).

# Part II — Development record (written before M4; historical)

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
  planner-bank c (0.59-0.73) for every policy. **[Superseded by C3: mostly progress composition of the mixed
  bank; entry-state c is close to own-arrival competence.]**
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

## Resources (development, before M4)
- Total: 36.82M of 80M environment actions (46.0%), including 3.10M estimated outside the runner.
- Batch wall time: 3.74 h.
- Campaign: 5.03M actions, 0.49 h batch wall time; active work 00:48-01:40 EDT.
- Ledger: `tools/ledger.py` with `research/ledger_adjustments.json`.

## Known limitations
- PPO is step-size-limited (lr 3e-5, clipped gradients on every minibatch). **[Superseded by C5: clipping activity
  alone does not diagnose the bottleneck; step-size limitation is a hypothesis.]**
- MPS training is not bitwise reproducible, so inference relies on independent seeds.
- The 250k endpoint is a fixed budget, not convergence (arm 00 still improves at 500k).
- The planner bank measures a different state distribution from actual arrivals. **[Refined by C3: mainly a
  different progress composition.]**

