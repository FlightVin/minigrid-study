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
