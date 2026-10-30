# Checklist

Dependency-ordered. `[x]` done and verified, `[~]` in progress, `[ ]` planned.

## Setup
- [x] Repository layout, `mae init`, local Git exclusions
- [x] Manuscript read (Sections 1-3); SHA-256, RQs, mapping, conflicts in DECISIONS.md
- [x] Native Python 3.12 venv, pinned lock, MPS availability
- [x] `mae profile` on the actual Mac
- [x] Harness tests 14/14 (after macOS EPERM fix)
- [x] Owner resource limits -> `mae configure` (4 cores, 6 GiB, 1 job, 8 h safeguard), DECISIONS.md
- [ ] Commit scaffolding (outer repo)

## M0: host and correctness
- [ ] Resource canaries via runner: CPU throttle, low memory stop (small allocation), wall timeout,
      owner stop, missing/stale MPS telemetry, CPU child cleanup; restore owner limits
- [ ] Telemetry module (from template) with background heartbeat thread
- [ ] Environment: K-module prefix, fixed canvas, gateway, suffix (obstacle, key disposal, pickup, delivery)
- [ ] Reward contract (1 on full success only), deadline termination, observation encoding with time
- [ ] State-aware planner; invariants (no alternate routes, drop pockets, solvability within H_x)
- [ ] Snapshot/restore with exact replay (planner and random continuations), no time refresh
- [ ] Boundary tests: success => access, first crossing only, turn-back, drop/reacquire, pickup not terminal
- [ ] Split registry with seed namespaces and canonical layout/state hashes; overlap checks

## M1: throughput and BC
- [ ] CPU vs MPS benchmark (same config), sustained 10-15 min thermal check
- [ ] ~1,000 planner demonstrations, balanced over K=1/3, with manifest and hashes
- [ ] Competence, reset and anchor banks (disjoint donors), per-bin counts
- [ ] BC curves on development; choose early/extended update rules
- [ ] Gate: measurable q and c, headroom (0.3 <= c_pi0 <= 0.9 in some checkpoint)

## M2: PPO canary
- [ ] Critic pre-check; 50k probe; four-arm short continuation; exact fork hashes; GAE/time checks

## M3: development comparison
- [ ] K=1/3 x two checkpoints x two seeds; alpha and KL screen; extrapolated cost
- [ ] PROTOCOL_FREEZE.md committed and hashed

## M4: core confirmation
- [ ] 5 seeds x 4 conditions x 4 arms on untouched confirmation layouts; audit; report

## M5: conditional RQ2
- [ ] Only if M4 shows useful heterogeneous effects and budget permits; else costed proposal
