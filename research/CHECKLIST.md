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
- [ ] conf-v1 data generated (conf_select, conf_bank, conf_final 64); gate `tools/data_gate.py` passes

## M4: core confirmation (Amendments 1 and 2)
- [x] Configs and batch files (`experiments/m4/`); schedule supports diag layouts and a second endpoint
- [x] Full test suite with smoke tests once before launch (255 passed; 0.35M actions in the ledger)
- [ ] Seed batches s10, s11, s12, s13, s14 (BC, 4 probes, 16 branches each), budget check before each
- [ ] Analysis at E250 and E500 (Holm over 6, TOST, bootstrap); audit (section 12); report

## M5: conditional RQ2
- [ ] Only if M4 shows useful heterogeneous effects and budget permits; else costed proposal
