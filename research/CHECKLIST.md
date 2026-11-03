# Checklist

Dependency-ordered. `[x]` done and verified, `[~]` in progress, `[ ]` planned.

## Setup
- [x] Repository layout, `mae init`, local Git exclusions
- [x] Manuscript read (Sections 1-3); SHA-256, RQs, mapping, conflicts in DECISIONS.md
- [x] Native Python 3.12 venv, pinned lock, MPS availability
- [x] `mae profile` on the actual Mac
- [x] Harness tests 14/14 (after macOS EPERM fix)
- [x] Owner resource limits -> `mae configure` (4 cores, 6 GiB, 1 job, 8 h safeguard), DECISIONS.md
- [x] Commit scaffolding (outer repo); pushed to origin/main

## M0: host and correctness
- [x] Resource canaries via runner: CPU throttle, low memory stop (small allocation), wall timeout,
      owner stop, missing/stale MPS telemetry, CPU child cleanup; restore owner limits
- [x] Telemetry module with background heartbeat thread (MPS thread read verified in benchmark)
- [x] Environment: K-module prefix, fixed canvas, gateway, suffix (obstacle, key disposal, pickup, delivery)
- [x] Reward contract (1 on full success only), deadline termination, observation encoding with time
- [x] State-aware planner; invariants (no alternate routes, drop pockets, solvability within H_x)
- [x] Snapshot/restore with exact replay (planner and random continuations), no time refresh
- [x] Boundary tests: success => access, first crossing only, turn-back, drop/reacquire, pickup not terminal
- [x] Split registry with seed namespaces and canonical layout/state hashes; overlap checks

## M1: throughput and BC
- [x] CPU vs MPS benchmark (MPS 4.3x faster); [~] sustained 10-15 min check folded into M2 continuation
- [x] 1,000 planner demonstrations (dev-v2), balanced over K=1/3, manifest and hashes
- [x] Competence, reset and anchor banks (disjoint donors), per-bin counts; cross-K match asserted
- [x] BC curves (2 seeds); early 4k / extended 16k
- [x] Gate passed: measurable q and c, headroom

## M2: PPO canary
- [x] Critic pre-check (early stopping), 50k probe, fork hashes, GAE/time tests
- [x] PPO stability screen (S4 selected)
- [x] Four-arm 250k continuation canary; learning check for arm 00

## M3: development comparison
- [x] K=1/3 x two checkpoints x two seeds; alpha and KL screen; extrapolated cost (F6, F7)
- [x] PROTOCOL_FREEZE.md committed and hashed
- [x] Owner review of freeze (owner requested a bounded development campaign, 2026-10-31)

## Pre-M4 development campaign (owner amendment 2026-10-31)
- [x] Owner amendment recorded verbatim in project.md (harness `366786a`)
- [x] Development allowance computed (8.0M; 5.0M after ledger correction)
- [x] Audit: manifest, raw recomputation, selection timing, ledger, contract (F8)
- [x] Information map and regimes (`reports/m3_info_map.csv`, F9)
- [x] Intervention activity (E3c), evaluation repeatability (E3a)
- [x] E1: four arms to 501,760, K=3 extended BC, seeds 0-1 (fresh runs; F9)
- [~] E2: seed-2 replicate deferred for budget (0 actions spent)
- [x] E3b: arrival-state banks + labelled clock-extended condition
- [x] No targeted family (section 7) and no 750k gate: not justified (Review 3)
- [x] Proposed Amendment 1 to PROTOCOL_FREEZE.md; costed M4 options in REPORT
- [x] Owner decision 2026-10-31: option A at both 251,904 and 501,760; cap not binding (harness `ea3d7ad`)
- [x] Amendment 1 approved; Amendment 2 (two endpoints, Holm over 6, budget) written before confirmation data
- [x] conf-v1 data generated (conf_select, conf_bank, conf_final 64); gate `tools/data_gate.py` passes

## M4: core confirmation (Amendments 1 and 2)
- [x] Configs and batch files (`experiments/m4/`); schedule supports diag layouts and a second endpoint
- [x] Full test suite with smoke tests once before launch (255 passed; 0.35M actions in the ledger)
- [x] Seed batches s10, s11, s12, s13, s14 (BC, 4 probes, 16 branches each), budget check before each
- [x] Analysis at E250 and E500 (Holm over 6, TOST, bootstrap); audit (section 12); report (F10)

## M5: conditional RQ2
- [x] RQ2 deferred: selection headroom small (hindsight ~0.01, out-of-sample ~0) and no held-out conditions (F11 section 7);
  not because heterogeneity is absent

## Post-M4 audit (owner instruction 2026-10-31)
- [x] Instruction recorded verbatim in project.md (harness `b37997a`); battery watch (20%, 5 min); 2-hourly self-review job
- [x] Final protocol and provenance (REPORT C1); budget status; harness/local-only commits recorded
- [x] Measured vs estimated ledger; step-boundary accounting fix + tests
- [x] Primary aggregate reproduced independently; TOST statistics; IUT joint statement; matched-K bootstrap
- [x] Condition-level contrasts (24), multiplicity (Holm-24/48, BH, sign-flip), K=3/early subgroup audit
- [x] Checkpoint x intervention and E500-E250 (post hoc / descriptive)
- [x] Progress-matched bank decomposition (M4 and dev E3b)
- [x] p = q r decomposition with unsupported cells
- [x] C4/R4, curves, optimization diagnostics; superseded claims marked
- [x] Hindsight selection reference and leave-one-seed-out condition rule (not RQ2)
- [x] Execution verification (lineage, 160 state hashes, role separation pairwise, banks, metrics)
- [x] Effect figure from saved tables; report revised; manuscript-ready wording
- [x] Self-review 2026-10-31 19:05: three-way interaction, arrival inventory, curve table, diagnostic costs added; STATE fixed
- [x] Owner decision on follow-up R1: approved with refinements (2026-10-31; harness `4d4fc31`)

## R1: focused replication (Amendment 3)
- [x] Instruction recorded verbatim; starting ledger 93,199,203; budget 28.4M hard, admission rule (`tools/run_r1.py`)
- [x] New roles r1_select/r1_bank/r1_final (namespaces 112-114); base-dataset copy; gate extended (`--r1`)
- [x] Managed step records (`env_steps/`) for counter cross-checks and runner test jobs; tests find data via MAE_PROJECT
- [x] Power script with variance and layout scenarios (`reports/r1/power.*`); analysis + synthetic tests frozen
- [x] Protocol freeze Amendment 3 (C1-C9), committed before data
- [x] Data r1-v1 (32,184 planner actions) and gate (`reports/r1/data_gate.json`, pass)
- [x] Test suite as a runner job (265 passed, 3 skipped; 59,274 actions)
- [x] Canary (s15: BC, probe early, branch 01 early) and canary check (`reports/r1/canary_check.json`, pass; no outcomes read)
- [x] seed-s15-rest (2,157,855 actions; 4/4 exit 0)
- [x] Seed 16 (3,171,975 actions; 7/7 exit 0)
- [x] Seed 17 first attempt failed (telemetry race; batch 20261101T005849-94851 kept); fix + test committed
- [x] Seeds 17-22 (rerun from seed 17; 6/6 batches exit 0; 3.13-3.18M each)
- [x] Analysis (`tools/analyze_r1.py --check-states`), final runner tests (266 pass), report, F12, Review 7
- [x] Stop scientific execution and report (R1 total 25,471,099 actions)

## Programme 2026-11-01 (Amendment 4): R2, E1, E2
Dependencies: each line needs the lines above it unless marked (parallel-safe: documentation).
- [x] Instruction recorded verbatim (harness `000fd83`); superseded limits noted
- [x] Monitors checked by process identity (none running); battery watch and 2-h review restarted
- [x] Targeted R1 audit (`tools/audit_r1.py`): inventory 64 records, lineage, roles, stats, actions, failure
- [x] Ledger correction (+128, failed-job step records); start total 118,670,430
- [x] Exact R1 and M4 decomposition; report corrections in place (R1.10); F13
- [x] Implementation: r2 roles + gate, component penalty + tests, crosspanel mode, eval_layouts_n
- [x] Frozen analyses: analyze_r2 (+ synthetic tests), analyze_crosspanel, analyze_comp; power_r2 (executable)
- [x] Budget driver run_program.py + plan.json; batch files; canary check script
- [x] PROTOCOL_FREEZE Amendment 4; DECISIONS; IMPLEMENTATION; STATE
- [x] Freeze commit + push (code frozen from here; only correctness fixes)
- [x] Data r2-v1 (runner) -> gate `--r1 data/r1-v1 --r2 data/r2-v1` (stop on failure)
- [x] Tests batch: full suite + RL smoke (exact CPU resume, heartbeat race, atomic writes)
- [x] Interruption drill: sleep canary stopped by `mae stop`; status stopped; children gone
- [x] Canary s23 (BC, probe, branch 01) -> `tools/r2_canary_check.py` (no outcomes) -> seed-s23-rest written + committed
- [x] R2 seeds 23-42 complete (20/20; watcher armed; no interim outcome reads)
- [x] R2 analysis `--check-states` (unblinded only at 20/20); figures
- [x] E1 cross-panel (26 policies x 2 panels x 4 attempts) -> analysis
- [x] E2 components (3 forks x 4 arms, 251,904) -> analysis `--check-states`
- [x] Final runner test job (prog-tests); ledger and cost reconciliation (measured vs conservative)
- [x] Independent verification of R2/E1/E2 numbers from raw records (separate script or fresh-agent review)
- [x] Consolidated report (sections 1-8 of the instruction), FINDINGS, review; commit + push
- [x] Stop owned monitors (battery watch, cron, watchers) by verified identity; stop scientific execution

## Programme 2026-11-01b (Amendment 5): A3, calibration, pilot, synthesis
Dependencies: each line needs the lines above it unless marked (parallel-safe: documentation).
- [x] Instruction recorded verbatim (harness `7ed7285`); superseded stop rules noted; closed verdicts preserved
- [x] Focused component-code audit (labels, sampling, coefficients, teacher, KL, actor/critic, RNG, fork state, no
      hidden change); value + gradient tests on fixed states; B + C = D, E = 0.75 D; no defect
- [x] Interpretation corrections (REPORT P2/P4/P5/P8; F18); literature positioning note
- [x] Implementation: arms 01w/11s, effective coefficients recorded, update-size diagnostics, BC prefix_prob,
      raw BC attempts, roles a3_*/pl_*, data config r3-v1, gate --r3
- [x] Frozen analyses: analyze_a3 (+ gate tests), power_a3, a3_canary_check, analyze_cal (+ rule tests)
- [x] Driver run_program2.py + plan; batch files (A3, calibration; pilot placeholders)
- [x] PROTOCOL_FREEZE Amendment 5; DECISIONS; IMPLEMENTATION; STATE
- [ ] Freeze commit + push; monitors (battery watch, review cron) started and recorded
- [x] Data r3-v1 (runner) -> data gate --r3 (stop on failure)
- [x] Tests batch (full suite + RL smoke incl. exact resume)
- [x] A3 canary s43 -> a3_canary_check (no outcomes)
- [x] A3 seeds 44-66 (24/24; watcher armed; no interim outcome reads)
- [x] A3 analysis `--check-states` (unblinded at 24/24); figures (paired arm effects at both endpoints, component
      contrasts, penalty/update-size diagnostics) — F19; H1 supported, gate not supported
- [x] Calibration batches s67-69 -> analyze_cal -> selection (rho 0.2 / 8000; DECISIONS)
- [x] (if selected) pilot batch files written; pilot runs; analysis; figures (analysis script and figure code
      `plot_program.py --which pilot` committed before any pilot run)
- [x] Figure: initial access vs boundary-entry competence (`reports/cal/access_entry.svg`)
- [x] Final runner tests (p2-tests); ledger and cost reconciliation
- [x] Independent verification from raw attempts (A3 inventory, coefficients, lineage, roles, formulas, actions;
      calibration; pilot) — `tools/verify_program2.py` committed; `--engineering` passes on 43-51
- [x] Synthesis: RQ1 distinctions; RQ2 assessment; literature positioning; one decisive recommendation
- [x] Consolidated report (closed / A3 confirmatory / secondary / calibration / pilot / remaining hypotheses);
      FINDINGS; review; commit + push
- [x] Stop owned monitors by verified identity only when the programme is complete

## Programme 2026-11-01c (A4; PROTOCOL_FREEZE Amendment 6; 70M from 255,665,568)

- [x] Instruction recorded verbatim (harness `d8155d4`); active battery rule set to 31% or lower (STATE, project.md
      note; tools/battery_watch.py and every "below 20%" record are historical)
- [x] Interpretation corrections (F23; REPORT marked "corrected 2026-11-01c")
- [x] Battery guard, job/driver admission, checkpoint-and-pause, recovery states, resume tool; tests on simulated
      readings (32/31/30%, AC, missing) and pause/resume smoke (local)
- [x] Data r4-v1 config, entry bank, arrival-bank job, A4 configs, batches, driver, frozen analysis, verifier,
      planning scenarios; DECISIONS, Amendment 6, STATE
- [x] Commit; verify no duplicate monitors; start battery guard; review cron
- [x] Data r4-v1 (runner) -> `tools/data_gate_r4.py` (stop on failure)
- [x] Arrival bank (runner); record counts / shortfall; freeze its hash; recompute conservative costs (driver)
- [x] Tests batch (full suite + RL smoke + pause smoke)
- [x] Canary seed 70 -> `tools/a4_canary_check.py` (no outcomes)
- [x] Seeds 71-89 (driver 37930; no pauses, no retries; battery 82-85% AC)
- [x] Cohort profile (pi0/probe/BC targets) reported (F25, REPORT S4: 3/20 meet all targets; tests the fixed procedure)
- [x] Analysis `tools/analyze_a4.py --check-states` at 20/20; `tools/verify_a4.py` (agrees); figures
- [x] Final tests (p4-tests, 306 passed); cost reconciliation (55,727,013); FINDINGS F24-F25; REPORT section S; recommendation; commit + push
- [x] Stop owned monitors at completion (battery guard 31137, review cron 5bcaa9b8)

## Programme 2026-11-02 (access-focused RQ1; PROTOCOL_FREEZE Amendment 7; 70M from 311,392,581)

- [x] Instruction recorded verbatim (harness `936e761`); starting ledger recorded
- [x] Section 2 corrections: `tools/a4_longitudinal.py` -> `reports/a4/longitudinal.md`; F26
- [x] Code: suffix certification, trace, diag5, module-entry banks, withdrawal schedule, allocation counters, certify/trace
      evaluation options, accounting mirror; unit tests + opt-in smoke (local)
- [x] Roles d5_trace, p5_*, c5_* (registry dry-run passes); configs data-r5-v1, diag-v1, p5-v1, c5-v1; batches; driver
- [x] Amendment 7 (design, opportunity rule, gate, confirmation, budget); DECISIONS; STATE
- [x] Commit; start battery guard (verify inclusive 31% decisions) and review cron; no duplicate monitors
- [x] Data r5-v1 (runner) -> gate check (roles, banks, disjointness)
- [x] Tests batch (full suite + smoke incl. p5 smoke) -> measure A4 smoke gap -> ledger adjustment
- [x] Analysis tools frozen before outcomes: `tools/analyze_diag5.py`, `tools/analyze_p5.py` (gate), canary check
- [x] Diagnostics batch -> failure taxonomy, references, certification -> opportunity rule (met; one deterministic
      failure fixed, rerun)
- [x] Pilot canary s90 -> engineering check (hashes, restoration, schedules, counters, numerics)
- [x] Pilot seeds 91-95 (no pauses, no retries; battery 87-90% AC)
- [x] Pilot analysis + gate.json: **no method qualified** (B +0.008, C +0.012, D +0.028; threshold 0.05);
      `tools/verify_p5.py` agrees; confirmation tools committed before the gate but unused
- [-] Confirmation seeds 96-115: not run (gate selected none; section 7)
- [x] Final tests (308 passed, 10 skipped); cost reconciliation (16,835,872); FINDINGS F27-F28; REPORT section T;
      recommendation; commit + push
- [x] Stop owned monitors (battery guard 56292, review cron 2f62d80b)
- [ ] Next question (key choice vs door approach counterfactual) — proposal only; awaits owner instruction

## Programme 2026-11-02b (frozen-policy controller diagnostics; PROTOCOL_FREEZE Amendment 8; 2M from 328,228,453)

- [x] Instruction recorded verbatim (harness `03d20ea`); starting ledger recorded
- [x] Position checks: tree, ledger, workers, policy hashes (8/8)
- [x] Denominator audit (`reports/p6/audit_p5.md`); marked corrections in F27/F28/REPORT T
- [x] Battery guard restarted (PID 30539) and two-hour introspective review loop (cron eb95c0a1); no duplicates
- [x] Role d6_ctrl + data r6-v1 (runner; 6,343 actions) -> disjointness check (no failures)
- [x] Controller module (KA/DA helpers, physical mask, step-indexed CRN), tests (zero remaining time, final-step
      arrival, inventory changes, already-open door, unavailable assistance, budget interruption)
- [x] Conservative cost -> 64 layouts fit (1,375,488 for evaluation; total about 1.80M of 2M)
- [x] Frozen analysis + independent verifier + replay job; Amendment 8 (hashes, controller definitions, fallbacks, accounting,
      manifest); commit before outcome-producing runs
- [x] Tests batch (first failed: test design, 70,354 counted; rerun 321 passed); engineering canary on d5_trace (no problems)
- [x] Evaluation batches: 8 policies x 8 conditions (1,116,009 actions; no pauses)
- [x] Verification replay sample (128/128, 0 mismatches); analysis; independent verification (agrees)
- [x] Trajectory inspection (predetermined sample); interpretation; ranked recommendation + one proposal (REPORT U5; not launched)
- [x] Final tests (321 passed); cost reconciliation (1,396,213 of 2M); FINDINGS F29-F30; REPORT U; STATE; commit + push; stop owned monitors (guard 30539, cron eb95c0a1)
- [ ] Corrective-imitation study (REPORT U5) or close the line — awaits owner instruction

## 2026-11-02c — Corrective prefix imitation study (Amendment 9)

- [x] Record instruction verbatim (harness `1efcb5f`); restart battery guard and review cron (no duplicates)
- [x] Section 1 record audit (F31) and marked corrections
- [x] Label planner, sources, PPO/rl integration, trace drop classification, recovery bank, eval replay
- [x] Unit tests and local smoke pass; power table; conservative costs; analysis and verification scripts
- [x] Amendment 9 frozen and committed before outcome-producing runs
- [x] Data r7-v1 (registry disjointness) → panel and bank hashes addendum
- [x] Recovery bank (label check 1/480 tie-set gap through obstacle pickup; documented in the addendum)
- [x] Tests + smoke batch in the runner (334 passed, 11 skipped; smoke 4 passed)
- [x] Development seeds 116-121 (116 canary: health only; no tuning)
- [x] Frozen gate + independent gate recomputation (no arm selected; agrees)
- [x] Confirmation 122-141 — not run (gate selected none)
- [x] Reserve: eval replay (36/36), final tests (334 passed); independent verification (agrees)
- [x] FINDINGS F32-F33, REPORT V, STATE, DECISIONS, REVIEWS; commit and push; stop owned monitors
- [ ] Follow-up mechanism study (F33) or close the line — awaits owner instruction

## 2026-11-02d — Consolidation and write-up (no new training)

- [x] Record instruction verbatim (harness `d015799`)
- [x] Stop new training: confirmed no project processes; records already committed (`9149d77`)
- [x] Hypothesis → evidence → uncertainty → conclusion table; exploratory diagnostics separate (`reports/WRITEUP.md`)
- [x] Negative results, small effects, failed replications, measurement lessons, costs, limitations
- [x] Reassessment: unresolved premise, deciding observation, smallest test (proposal only)
- [ ] Offline supervised capacity check, or close the project — awaits owner instruction
