# Implementation

Engineering changes, defects, fixes and test evidence. Scientific results go in FINDINGS.md.

## 2026-10-30 — Setup on the destination Mac

**Host (measured by `mae profile`, `.mae/profile.json`):** Apple M5, arm64, macOS 26.6.2,
10 cores (sysctl: 4 performance + 6 efficiency), 24.0 GiB unified memory, 678 GiB free disk.
At profiling time: 6.4 GiB available, 1.33 GiB swap in use (browser, Slack, editors and agent clients running).

**Python environment.** Rebuilt `.venv` with uv on CPython 3.12.14 arm64; the previous venv was
CPython 3.14.6 with no packages. Lock: `requirements.lock`.

**Harness defect: `killpg` EPERM on macOS.**
- Symptom: 5 of 14 harness tests failed (`test_failure_stops_siblings_and_no_retry`,
  `test_memory_stop_with_small_allocation`, `test_mps_telemetry_guard_without_gpu`, `test_owner_stop`,
  `test_wall_limit`) with `PermissionError` from `os.killpg` in `shutdown`.
- Cause: on macOS, `killpg` returns EPERM (not ESRCH) when all group members are unreaped zombies.
  Verified directly: live group -> success; zombie-only group -> EPERM; reaped group -> ESRCH.
  The same result occurs outside the agent sandbox.
- Fix (harness commit `b53f29a`, branch `mac-host-fixes`): in `group_signal`, ignore EPERM only
  when the job leader has exited; re-raise otherwise.
- Evidence: 14/14 harness tests pass. No test worker remained afterwards (checked process list;
  two unrelated `sleep` processes with live non-harness parents predate the run).

## 2026-10-30 — M0 resource canaries (runner, destination Mac)

Driver `tools/m0_canaries.py`; record `.mae/canaries/20261030T201408.json`; 7/7 passed.

| Canary | Batch | Response | Notes |
|---|---|---|---|
| cpu-throttle (6 busy children, 4-core budget) | 20261030T201107-59036 | completed | mean 4.39 cores over 18 samples: duty cycling works but overshoots ~10% (soft) |
| owner-stop (`mae stop` at 10 s) | 20261030T201153-59515 | owner_stop | 3/3 children gone |
| wall-limit (0.006 h) | 20261030T201205-59677 | wall_limit at 22.8 s | 2/2 children gone |
| memory-stop (1 GiB limit, 1.5 GiB in 64 MiB steps) | 20261030T201229-59913 | memory_pressure at 1.019 GiB | |
| mps-no-telemetry | 20261030T201237-60014 | stale-telemetry stop at 30.9 s | |
| mps-stale-telemetry (one beat) | 20261030T201309-60308 | stale-telemetry stop at 32.9 s | |
| mps-telemetry-ok | 20261030T201343-60766 | completed | driver memory 0.008 GiB reported |

Owner limits were restored afterwards (4 cores, 6 GiB, 1 job, 8 h). Still open: background-thread
reads of the MPS driver counter during live MPS training (checked in the M1 benchmark).

## 2026-10-30 — Task, planner and splits (M0)

- `src/bc2rl/task.py`: fixed 21x9 canvas for K=1..3; gateway door (12,4) always yellow; suffix with an
  inner wall (x=16) and one gap, purple target ball, green distractor ball, purple delivery floor.
  The suffix uses its own RNG stream, so one layout seed gives the same suffix for every K.
  Reward 1 only on success; the deadline is terminal (time is observed); MiniGrid's step dynamics
  are reused unchanged. Observation: 4-channel categorical grid (type, color, state, agent dir marker),
  aux (dir, carried type, carried color), remaining time / 200 (common for all K).
- `src/bc2rl/planner.py`: segment-exact BFS (exact within each segment; segments end in forced poses).
  Not proven globally optimal: it excludes plans that pick the distractor, drop the target, close
  doors, or move keys dropped in earlier segments. Every plan is verified by replay. ~15-35 ms/layout.
  Smoke sample (30 layouts per K, slack 24, suffix allowance 80): tau 8-18 (K=1), 19-33 (K=2),
  30-51 (K=3); suffix length 13-37, mean ~24 for every K.
- `src/bc2rl/splits.py`: 10 roles with fixed SeedSequence namespaces; disjoint full-layout structure
  hashes; evaluation/bank roles suffix-disjoint from training roles and from each other.
  With the initial counts, 15 candidates were rejected by this rule (all evaluation roles).
- Tests (`tests/`): 236 pass. They cover reward contract under random play, success => access,
  first crossing only (turn back and re-enter), pickup not terminal, wrong objects on delivery,
  drop/reacquire, deadline terminal with last-step success, no alternate routes (door/gap removal),
  planner within limit (120 layouts), restore equality of observations/rewards/flags/time through
  completion for planner and random continuations (through JSON), no extra time for an
  almost-expired snapshot, registry overlap detection.
- Test defect fixed: one test teleported the agent into the suffix with locked doors; the boundary
  invariant correctly rejected it. The test now crosses legitimately first.

## 2026-10-30 — M1 data and backend benchmark

**Datasets** (`data/`, untracked; hashes in each `manifest.json`):
- `dev-v1` (batch 20261030T202518-64004): superseded. Its competence bank matched across K for
  61/64 items only. Cause: the suffix BFS could search the prefix rooms, which differ by K, so
  tie-break RNG use differed. Fix: suffix search confined to the gateway approach cell, gateway and
  suffix (no length lost on 300 test layouts). `data.py` now asserts the cross-K bank match.
- `dev-v2` (batch 20261030T203121-67141, job m1-data-dev-v2): 0 planner failures; 15 registry
  rejections (suffix rule). Transitions: bc_train 45,212; bc_val 5,114; reset_donor 25,918;
  anchor_donor 25,522; dev_bank 6,466. Layouts: rl_train 4,096; dev_eval 64. Bank bins 32/16/16 per K.
  Suffix plan length mean ~24 (range 11-40) for both K; tau mean 12.3 (K=1), 40.9 (K=3); H 110-163.

**Backend benchmark** (same batch; real model and env; 4 envs x 128 steps, 4 epochs x 4 minibatches
of 128 actor+critic updates + 128-state anchor forward; 150 s each, warmup cycles excluded):

| Backend | Actions/s (1st half -> 2nd half) | Update s/cycle | Rollout s/cycle | BC steps/s (b=256) | Peak RSS |
|---|---|---|---|---|---|
| MPS, 1 CPU thread | 1,404 (1,406 -> 1,401) | 0.149 | 0.216 | 96.9 | 0.50 GiB (+0.11 GiB MPS) |
| CPU 4 threads | 331 (320 -> 341) | 1.458 | 0.097 | 18.0 | 0.41 GiB |
| CPU 2 threads | 315 | 1.529 | 0.094 | 16.2 | 0.41 GiB |
| CPU 1 thread | 276 | 1.764 | 0.090 | 13.8 | 0.41 GiB |

Decision: MPS for all scientific runs, one job at a time. The background telemetry thread read the
MPS driver counter for 150 s while the main thread ran MPS work, with no fault. Batch peak conservative
memory 0.56 GiB; no swap growth. MPS rollouts are now inference-latency bound (~1.7 ms per step).
A dedicated 10-15 min sustained thermal check is folded into the M2 canary (continuous MPS work).

**PPO fork aliasing defect.** `Optimizer.load_state_dict` reuses same-dtype CPU tensors, so an
in-memory fork changed when a learner that loaded it trained. On-disk forks were never affected.
Fix: `PPO.state()`/`load()` deep-copy. Test: a fork reproduces collect+update exactly on CPU.

**Runner refusal.** One BC launch was refused because the tree had uncommitted edits (no job ran).
The watcher then reported the previous batch; it was restarted after the new batch was confirmed.
