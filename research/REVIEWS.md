# Research reviews

Two-hourly reviews (owner amendment 2026-10-30). Newest last.

## Review 1 — 2026-10-30 ~17:25 EDT (after ~1.5 h of active work)

**Status.** M0 verified. M1 gate passed (F1). M2: canary probe collapsed (F2); stability screen chose
S4 (F3); four-arm continuation (250k/arm, K=3 extended, seed 0) running as batch 20261030T211303-98764.

**Does the work still answer RQ1/RQ2?** Yes, conditionally. The task separates access from competence
as intended: at extended BC, K=3 has q ~0.45 versus ~0.98 for K=1, with the same suffix competence
(~0.66) on a K-matched bank (F1). RQ1 now depends on one thing not yet shown: that ordinary PPO can
improve at all in this regime. With actor lr 3e-5 the probe holds performance but does not improve it
within 50k actions. If all arms stay flat over 250k-500k, RQ1 would compare interventions on a
non-learning baseline. That would be a weak answer to "improve subsequent PPO learning".

**Are the comparisons valid?** Mechanically yes: forks are hash-verified and exactly reproducible on CPU;
branches share the normal-layout stream; evaluation uses common random numbers; confirmation data do
not exist yet. Two qualifications:
- "Ordinary PPO" is now conservative PPO (lr 3e-5, no entropy bonus), chosen because larger steps
  destroyed the BC policy. This is a legitimate, prespecified development choice, but the report must
  say that the tested PPO is step-size-limited and that results may not transfer to other settings.
  [Superseded by F11 section 6: "step-size-limited" is a hypothesis; clipping activity alone does not diagnose it.]
- The critic is barely better than a constant (F3). Advantages are therefore mostly a noisy baseline.
  Any later decline in c could reflect value-estimation noise as much as missing stage practice. The
  analysis must keep this competing explanation explicit.

**Evidence vs claims.** No scientific claim has been made. Probe Delta-c values (e.g. -0.27 in F2) are
labelled optimization artifacts. S4 K=3 Delta-c of -0.09 is within noise (64 items x 2 attempts).

**Leakage.** Selection steps used only bc_val, dev_eval and dev_bank. Confirmation layouts and banks are
not generated. The screen selected on ordinary-PPO p only; Delta-c and intervention arms were not used.

**Failures and waste.** dev-v1 regenerated (bank mismatch, 3 min); one launch refused (dirty tree); one
probe failed on a seed-type bug (4 s); the first canary used a poorly fit critic. All cheap. The RL smoke
test now catches integration bugs before runner time.

**Resources.** 0.67 h batch wall; ~2.5M environment actions of the 80M cap (probe/branch summaries
1.52M; BC-curve evaluation ~0.6M; benchmarks ~0.3M; continuation ~1.2M running). Peak memory < 1 GiB,
no swap growth. MPS ~1,400 actions/s ordinary, ~950/s with the KL arm.

**Unresolved risks.** (1) PPO may not learn within budget (main risk). (2) 512-action batches hold ~4
episodes, so per-update signal is tiny; a larger rollout batch is the obvious next lever and on MPS it is
nearly free per action. (3) Estimates from 128 normal-start attempts have SE ~0.04, too coarse for a
5-point effect threshold in development screens.

**Next most informative experiment.** Read the four-arm curves. If arm 00 does not improve, run a
prespecified development check of rollout size (e.g. 16 envs x 128) at lr 3e-5 and 1e-4, selecting on
ordinary-PPO p after a fixed action budget, then start M3. Do not tune on intervention arms.

## Review 2 — 2026-10-30 ~19:25 EDT (after the M3 screen; no submissions during review)

**RQ fit.** The main risk from Review 1 is resolved: with R2, ordinary PPO improves in 7/8 forks (mean
P1 0.26 -> 0.37). RQ1 now compares interventions against a learning baseline. The K x checkpoint grid
spans P1 from 0.05 to 0.70 and access q from 0.25 to 1.0, so the conditions "where" each intervention
helps can be tested. The K=3 early forks sit near the floor; they contribute little signal.

**Validity.** Forks are hash-matched across arms; arms share streams; no confirmation data exist. The
screen chose alpha and lambda only from dev_eval P1 by a rule written before the batch. Applied
literally, the 0.02 tie rule picks alpha = 0.25 although alpha = 0.5 scored higher. I keep the rule:
changing it after seeing the data would be selection on the outcome.

**Evidence vs claims.** Screen differences (+0.017 to -0.047) are smaller than the fork-to-fork SD of
paired differences (0.04-0.06). Part of that SD is MPS nondeterminism (F5). I do not know how much.
This matters for M4: if the noise of a paired contrast is dominated by run-to-run nondeterminism, more
forks are the only remedy; if it is dominated by fork heterogeneity, stratified analysis helps.

**Alternative explanations.** (1) Preservation lowers P1 monotonically in lambda. This can be the
expected cost of holding the policy near a weaker pi0, not a failure of the mechanism. (2) Reset raises
bank P1 more than normal P1: suffix practice may help competence, while the binding limit for P1 at K=3
is access (q). This supports measuring q and c separately in M4.

**Leakage, resources.** No leakage found. Batch wall 1.56 h. Actions: 23.8M of 80M (29.7%). Peak
memory per job < 1 GiB. M3 used ~15.7M (estimate 17M).

**Waste.** None significant. The 3-value lambda grid was informative (monotone pattern).

**Plan update.**
- Run arm 11 (alpha 0.25, lambda 0.01) on the 8 forks, as prespecified.
- Add one replicate of arm 00 per fork in the same batch (identical config; differs only by MPS
  nondeterminism). This measures the null spread of a paired contrast and sizes M4. Cost ~2.5M.
- Endpoint: 250k is favoured. A 4-arm fork at 250k costs ~1.36M actions versus ~2.36M at 500k. Within
  the remaining budget less a 20% reserve, that is ~26 versus ~15 forks; with paired SD ~0.05 the
  forks, not the length, decide power. Final choice at the freeze.

## Review 3 — 2026-10-31 ~01:35 EDT (end of the pre-M4 development campaign; no submissions running)

**RQ fit.** RQ1 asks whether the interventions change P1 after BC. On development data, no arm separates from
ordinary PPO at 250k (8 forks) or at 500k (K=3, extended BC, 2 seeds). The design still answers RQ1. The
realistic M4 outcome is "small or no effect, bounded by precision". M4 should be sized to bound effects, not
to find a large one.

**Validity.** The audit found no correctness defect (F8). The comparisons are paired on hashed forks with
common random numbers. Two of my own earlier claims were wrong and are corrected:
- improvement in 7/8 forks (actually 8/8);
- the cause of repeat variation and the precision/power statement (withdrawn).

The selection rule was recorded before its outcomes.

**Evidence vs claims.** The most interesting development pattern, the K=3 combined benefit, did not survive a
rerun of the same forks (F9). This is the main lesson: single-path development contrasts are dominated by
training-path variation (SD about 0.05). Development rankings must not guide M4 hypotheses.

**Alternative explanations.** The planner bank overstates competence on actual arrival states (F9 E3b).
Time pressure explains about 0.03 of that gap. The rest is untested (prefix configuration or layout
selection). Planner-bank c is therefore a valid but different estimand from arrival competence. The report
must keep "p = q x c" out.

**Leakage.** None. No confirmation data exist. Seeds 10-14 were not touched. All diagnostics used dev roles.

**Resources and waste.**
- Campaign 5.03M actions, 0.49 h of batch wall time.
- Ledger gap of about 2.75M from tests (now counted conservatively as 3.1M). This cost E2, the third seed.
- Waste: the full-suite runs with RL smoke tests (~0.22M each) were avoidable. They are now opt-in.

**Next most informative experiment.** None within the development allowance. More seeds would help most, and
they belong in M4. A 750k gate is not justified: no emerging separation, slow learning (+0.04 to +0.07 per
250k), and path noise dominates.

**Plan update.** Stop development. Recommend M4 option A with Amendment 1. Wait for owner approval.

## Review 4 — 2026-10-31 16:20 EDT (after M4)

**Result.** Confirmatory and clear: all three interventions are practically equivalent to ordinary PPO at both
251,904 and 501,760 (F10). Intervals are tight (half-widths 0.018-0.032), so this is evidence of no useful
effect, not a lack of evidence. [Superseded by F11: true for the equal-weight average only; condition-level
effects exist (preservation at K=3/early BC, +0.045 at E500, post hoc).]

**Consistency with development.** Development contrasts were within about 0.02 of 0 (F7) and the M3 K=3
"benefit" did not reproduce (F9). M4 agrees with that pattern. The precision planning was accurate (observed
half-widths near the rho = 0 scenario).

**Alternative explanations.** (i) Dose: alpha 0.25 and lambda 0.01 were active (F8 E3c) but small; larger doses
were worse or not better in the screen (F6). (ii) The step-size-limited PPO configuration (lr 3e-5) [hypothesis; F11 section 6] may leave
little room for any learning-dynamics intervention. (iii) Mechanism signals (q from preservation, c from all
arms) do not reach P1, consistent with the planner bank differing from arrival states (F9). [Superseded by F11 section 4: mostly the
bank's progress composition; coexistence, not a causal explanation.]

**Leakage / integrity.** Analysis committed before outcomes; no confirmation data used for any development
decision; no retries; audit exact.

**Waste.** None in M4. The data-batch launch error cost 0 actions.

**Plan.** Stop experiments. Report to the owner.

## Review 5 — 2026-10-31 19:05 EDT (two-hour self-review; post-M4 audit)

**Checked.** Re-read `project.md` (post-M4 audit instruction, sections 1-10) and `agent.md`. Running tasks: only the
battery watch (PID 66192, 5-minute checks; 92% on AC at 19:00); no runner batch, no bc2rl worker. No training was
started. Completed: F11 audit, revised REPORT (C1-C9), accounting fix, data-gate pairwise check, effect figure,
commit `c6359c3` pushed.

**Against the instruction, item by item.**
- Sections 1, 2 and 8 are met. One nuance is recorded: analysis-code timing alone does not prove that every choice
  was prespecified, and the code-level cross-K resampling choice is listed in C1.
- Section 3 had a gap: the intervention x K x checkpoint analysis was only within K. Added the three-way
  (post hoc; nothing survives Holm-6).
- Section 5 had a gap: arrival states for K=3/early BC. Added inventory: identical in both arms.
- Section 6 had a gap: curves were only referenced. Added a curve table that keeps the layout sets separate.
- Section 7 had a gap: diagnostic costs were not quantified. Added them (37k-73k actions per condition).
- Sections 4, 9 and 10: no change needed. R1 is proposed and not run.

**Claims beyond evidence (checked).**
- The headline limits equivalence to the aggregate.
- The K=3/early BC effect is labelled post hoc, with sign-flip limits stated.
- No causal claim about the banks.
- "Step-size-limited" is a hypothesis.
- The ledger is split into measured and estimated parts.

**Corrections to state.** STATE still said "7/8 forks" (corrected in F8), quoted the pre-amendment freeze (250k,
32 x 16), carried the superseded F9 arrival claim and an old test count. All fixed. CHECKLIST is current.

**Leakage / integrity.** No confirmation data were used for any development decision. R1 would use fresh
seeds and fresh layout roles.

**Next.** Wait for the owner's decision on R1. Keep the battery watch and the two-hourly reviews.

## Review 6 — 2026-10-31 20:57 EDT (two-hour self-review; R1 running)

**Checked.** Re-read `project.md` (R1 approval, sections 1-7; post-M4 audit instruction) and `agent.md`. Running:
R1 driver (`tools/run_r1.py`, PID 88084), seed 16 batch 20261101T003945-89279 (6/7 jobs exited 0 at the review),
battery watch (100% on AC, 5-minute checks). Completed since Review 5: instruction recorded (`4d4fc31`); freeze
Amendment 3 with frozen analysis, power script and tests (`01beef9`), before any R1 data; data and gate; runner
test job; canary with engineering check; seed 15. R1 spent 3.25M of 28.4M at the end of seed 15.

**Against the owner's direction.**
- Scope matches section 1 (K=3, 4k/16k, seeds 15-22, arms 00/01 at alpha 0, 501,760 primary). No added arm,
  dose or endpoint.
- Section 2: 128 x 4 panel; separate bank 32/16/16; new roles disjoint from every earlier role (gate).
- Section 3: hypotheses, Holm-2, bootstrap and power fixed before data. Power table shows no 80% promise.
- Section 4: one canary first; its outcome was not read; tests ran through the runner.
- No outcome of any R1 branch has been read. Nothing in STATE or REPORT claims an R1 result.

**Gaps and corrections.**
- agent.md asks for a deterministic watcher per experiment family. It was armed only now. Fixed (DECISIONS).
- agent.md asks for `pip freeze` before a run. Recorded now; packages unchanged since 2026-10-30.
- Amendment 3 per-seed conservative cost had an arithmetic slip (3,333,150 -> 3,334,150). No effect on admission.
- IMPLEMENTATION.md lacked the R1 engineering changes. Added.

**Next.** Seeds 16-22 (about 2.5 h). Then the frozen analysis with state-hash checks, a final runner test job,
REPORT/FINDINGS, and a stop. Documentation commits are made in one command so the tree is never dirty at a batch
boundary.

## Review 7 — 2026-11-01 03:00 (R1 complete)

**State.** No experiment is running. Completed: seeds 17-22 (rerun after the telemetry fix), frozen analysis with
state checks, and a final runner test job (266 passed, 3 skipped). R1 spent 25,471,099 of 28.4M.

**Against the owner's direction.**
- Section 1 scope held: 8 seeds, both checkpoints, arms 00/01, alpha 0, 501,760 primary. No seed replaced, no
  dose or endpoint added.
- Section 3: the decision used the frozen Holm-2 rule only. The unadjusted p (0.033) is close to 0.05 after
  adjustment (0.067). The report states "not supported" and "inconclusive" plainly, and does not round it up to
  a replication.
- Section 6: the interpretation cell follows the frozen rule. The M4 aggregate result is unchanged.
- Section 7: the report has the protocol and provenance, all 8 paired seeds, both estimates with t and bootstrap
  intervals, Holm, layout sensitivity, secondary stages, a separate M4 comparison, costs, the failure and no
  exclusions, an interpretation, one next question and manuscript wording. Harness hashes are recorded.
  The manuscript is not changed.

**Risks in the reading.**
- "Positive but unconfirmed" depends on the unadjusted interval and the bootstrap. Both are labelled as
  sensitivity checks.
- The 251,904 pattern ("preservation speeds early learning with both checkpoints") is descriptive and is not
  turned into a claim.

**Next.** Stop scientific execution. Stop the remaining watchers by verified identity. Report to the owner.

## Review 8 — 2026-11-01 ~05:05 local (R2 running; programme under Amendment 4)

**State.** Done since Review 7: owner instruction recorded (`000fd83`); targeted R1 audit and corrections (F13,
REPORT R1.10); freeze `c372ef7`; data r2-v1 + gate (pass); test batch (273 passed, smoke 3/3 incl. exact resume);
interruption drill (pass); canary s23 (pass, no outcome read); seed 23 rest and seeds 24-27 complete; seed 28
running. Every batch exited 0 and cost below its conservative estimate (per seed 1.64-1.68M vs 1.73M). Programme
spend 9.37M of 50M; projected conservative total 42.04M (+ audit) — completion is secure.

**Research questions and validity.** R2 still tests the single RQ1 question fixed in Amendment 4; E1 and E2 are
queued behind it. No R2 outcome, paired difference or arm mean has been read; the analysis is blinded until 20/20.
Seeds, lambda, panels and endpoints are unchanged. The frozen design remains executable.

**Resources and tracking.**
- Monitors verified by PID and create time: battery watch 35448 (100%, AC), seeds driver 42665, watcher loop
  (watch_batch child active). Review cron 19ac8cf7 active.
- The review prompt (written before the R1 audit) names the start as 118,670,302; the frozen start is the
  corrected 118,670,430 (Amendment 4 A). `run_program.py` uses the corrected value.
- **Defect found and fixed (tooling, no scientific effect):** `tools/run_program.py` judged a batch complete only
  by `summary.json`. Pytest jobs and the drill never write one, so the test batch counted as incomplete for ever:
  committed cost was overstated by ~0.4M, and E1/E2 would have been refused after R2. Now: a job is complete with a
  summary or exit code 0 in its batch's execution record; the drill is marked not required in `plan.json`. The
  running driver (old code) only over-holds 0.4M for R2 admissions, which is harmless.
- Ledger accounting: the r2-smoke loss (~0.22M) is fixed in code and added as a 0.25M estimate (IMPLEMENTATION).

**Next.** Let seeds 28-42 finish (~2.7 h). Then E1 cross-panel, E2 components, final tests, R2 analysis with
`--check-states`, independent verification, report.

## Review 9 — 2026-11-01 ~07:45 local (programme complete; final)

**State.** R2 seeds 23-42 finished (20/20, every batch exit 0, 0.925-0.973 of conservative). The frozen analysis
ran once at 20/20: +0.0097 [-0.0035, +0.0229], p 0.142, not supported, interval excludes 0.03 (F14). E1 (F15),
E2 (F16) and final tests (274 passed) completed inside their ceilings. Spend 39.64M of 50M; reserve unused (F17).

**Validity.** No design change after any outcome. No interim read of R2 outcomes. R2 data only for the decision;
the R1+R2 synthesis is descriptive with adaptive selection disclosed. Independent verifier
(`tools/verify_program.py`) reproduces R2, E1 and E2 from raw attempts. M4 and R1 verdicts unchanged.

**Deviation.** One runner refusal at the start of xp-r1 because I left an uncommitted file in the tree (0 actions;
rerun unchanged; DECISIONS). Rule kept since: write and commit new files in one command.

**Interpretation risks checked.** E2's suffix-only result is not promoted to a claim (3 seeds, development panel,
inconsistent with the "both" arm). E1 does not count as replication. The decomposition is arithmetic, not mediation.

**Next.** Stop owned monitors by verified identity; report to the owner; stop.

## Review 10 — 2026-11-01 ~09:20 local (Amendment 5; A3 running)

**State.** Done since the new instruction: instruction recorded (`7ed7285`); component-code audit (no defect) and
interpretation corrections (F18); Amendment 5 freeze `ee27b03`; data r3-v1 + gate (pass); tests 288 + smoke 3/3
(smoke step records now captured); canary s43 passes all engineering checks; pilot analysis script and test committed
before any pilot run; literature notes. Seeds 44 and 45 complete (each 0.923 of conservative); seed 46 running.

**Validity.** The A3 design is unchanged since the freeze. No A3 contrast, arm mean or per-seed outcome has been read;
the analysis stays blinded until 24/24. Calibration and pilot rules were fixed before their data exist. The research
questions in the instruction (allocation vs strength, persistence, regime) map one-to-one to A3 H1/gate/secondary,
the calibration targets and the pilot.

**Resources and tracking.** Spend 11.43M of 130M (A3 11.36M; ~0.07M local tests). Required conservative remainder
fits with the 12M reserve held. Monitors verified by process identity: battery watch 69759 (100%, AC), seeds driver
71896 (create time matches), one watcher loop; review cron d308a314. No duplicates.

**Next.** Seeds 46-66 (~4.5 h). Then `tools/analyze_a3.py --check-states`, figures, F19; then calibration batches
cal-s67..69 -> `tools/analyze_cal.py` -> pilot batch files via `make_batches.py --pilot` (if selected) -> pilot.

## Review 11 — 2026-11-01 ~11:15 local

- **State.** A3 seeds 43–51 finished (9/24) and seed 52 is running (batch `20261101T155802-1913`). The seeds log shows no failures, refusals or retries. Every branch exited with code 0.
- **Validity.** The design has not changed. I read no A3 aggregate outcomes; the analysis stays blinded until 24/24. Branch order follows the committed Latin rotation. Comparisons and interpretations from earlier reviews are unchanged.
- **Resources.** Spent 33,166,705 of 130M (A3 33,095,399). Remaining conservative cost of the required work is 65.17M. The projected conservative total is 98.6M, so the 12M reserve and the 15M development ceiling stay available. Per-seed cost is still about 3.65M, which is 0.92 of the conservative estimate.
- **Monitors.** Each monitor has exactly one process, verified by PID and create time: battery watch 69759 (90%, mains power), driver 71896 (create 1793540164.945303) and one watcher loop. The review cron is active. There are no duplicates.
- **Next step.** Let seeds 52–66 finish (about 15 × 21 min, roughly 5.3 h). Then run `tools/analyze_a3.py --check-states`, make the figures and write F19. Then run calibration batches cal-s67..69, `tools/analyze_cal.py`, and the pilot if a variant is selected.

## Review 12 — 2026-11-01 ~13:15 local

- **State.** A3 seeds 43–56 finished (14/24) and seed 57 is running. Every job exited with code 0. There are no refusals or retries, and the watcher has reported no stall. Since Review 11 I wrote and committed the post-outcome code before any outcome existed:
  - figures for A3, calibration and the pilot (`tools/plot_program.py`, tested on synthetic data only);
  - the independent verifier `tools/verify_program2.py`, whose `--engineering` mode passed on seeds 43–51 with no outcome computed.
- **Validity.** The design has not changed and I read no A3 aggregate outcomes. The research questions and the order of the objectives are unchanged. The engineering checks (lineage, effective coefficients, roles, one identical panel, step records = summaries) found no defect.
- **Resources.** Spent 54,872,167 of 130M (A3 54,800,861). The remaining conservative cost of the required work is 41.44M and the projected conservative total is 96.6M. The 12M reserve and the 15M development ceiling are still available. Per-seed cost is unchanged.
- **Power note.** The battery falls by about 5 percentage points per hour while the charger is connected (93% at 10:48, 80% at 13:13): under this load the charger does not keep up. At this rate the 20% stop arrives in about 12 h. The rest of the required work plus the pilot needs about 7–8 h, so the margin is adequate. The battery watch stays the hard guard. If the battery reaches 20% it stops the driver, and the failure policy applies (resume with a new run ID).
- **Monitors.** One process each, verified by PID and create time: battery watch 69759, driver 71896 (create 1793540164.945303) and one watch_batch loop. The review cron is active. There are no duplicates.
- **Next step.** Seeds 57–66 (about 3.5 h). Then the A3 analysis with `--check-states`, the full verifier, the figures and F19. Then calibration s67–69 → `analyze_cal` → the pilot if a variant is selected.

## Review 13 — 2026-11-01 ~15:15 local

- **State.** A3 seeds 43–62 finished (20/24) and seed 63 is running. All exit codes are 0. The seeds log has no refusal or error lines, and the watcher has reported no stall.
- **Validity.** The design has not changed and I read no A3 aggregate outcomes. The frozen analysis, verifier and figure code are unchanged since their commits.
- **Resources.** Spent 76,540,622 of 130M (A3 76,469,316). The remaining conservative cost of the required work is 17.72M and the projected conservative total is 94.56M. Projected A3 spend at 24/24 is about 91M, under the 103M A3 ceiling. The 12M reserve and the 15M development ceiling are still available.
- **Power.** The battery is at 68% with the charger connected and falls about 6 points per hour. The 20% stop is about 8 h away. The work left needs about 6–7 h: A3 about 1.4 h, calibration about 0.5 h and the pilot about 4 h. The margin is narrower than at Review 12, but the battery watch remains the hard guard. If the margin becomes too small before the pilot, I will check the battery before launching it rather than start a batch that is likely to be cut.
- **Monitors.** One process each, verified by PID and create time: battery watch 69759, driver 71896 (create 1793540164.945303) and one watch_batch loop. The cron is active. There are no duplicates.
- **Next step.** Seeds 63–66. Then `analyze_a3.py --check-states`, `verify_program2.py`, `plot_program.py --which a3` and F19. Then calibration s67–69.
