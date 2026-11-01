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

## 2026-10-30 — M2 canary probe: failed launch and fixes

- Batch `20261030T205100-80441` (m2-canary-probe-K1-u4000-s0) failed deterministically after the pi0
  evaluation: `StartSampler` nested a list seed inside `default_rng([...])` (NumPy TypeError). Unit
  tests had used integer seeds. Fix: flatten int-or-sequence seeds. The pi0 evaluation that ran
  (K=1, early BC, seed 0: p 0.25, q 1.00, c 0.27; 23,097 evaluation actions) is retained in that run
  directory and is consistent with the BC curve. Not reused: the canary is rerun under a new batch.
- Added `tests/test_rl_smoke.py`: real dev-v2 data and BC checkpoint, tiny budgets, CPU, probe then
  all four arms in one process (fork hash verified in each branch; assisted steps only in arms 1x).
  It exposed one more in-process-only issue (`set_num_interop_threads` called twice), now tolerated.

## 2026-10-31 — Pre-M4 development campaign: code changes

- `rl.py`:
  - Optional `eval_schedule` (evaluations at exact cumulative post-probe action counts) and `save_state_at`
    (complete hashed learner state: actor, critic, both Adam states, torch/numpy/sampler RNGs, in-flight
    environments, counters, pi0).
  - `resume` mode, which refuses changed frozen settings.
  - `diag_role` for separate pi0/probe diagnostic layouts.
  - `@/job` paths for `--bc-run`.
  - Bank evaluation skipped when bank_attempts = 0.
  - M3 configurations are unaffected: the keys are absent.
- `evaluate.py`: `capture=True` stores the full snapshot at first crossing.
- `diag.py`: `reeval`, `arrival` (first-crossing banks, cross-policy evaluation, labelled clock-extended
  condition) and `gradcheck`.
- Tools:
  - `audit_m3.py`: manifest and independent recomputation.
  - `info_map.py`.
  - `analyze_dev2.py`: within-seed layout-resampling intervals.
  - `plot_dev2.py`: dependency-free SVG.
  - `ledger.py`: reads `research/ledger_adjustments.json`.
- Tests:
  - Exact CPU resume (`test_scheduled_branch_resumes_exactly`).
  - Diagnostics smoke test.
  - Registry extension keeps earlier entries.
  - `diag_role` layout separation.
  - RL smoke tests are opt-in (`BC2RL_SMOKE=1`) because each run executes ~220k environment actions.

## R1 (Amendment 3), 2026-10-31
- `splits.py`: namespaces 112-114 (r1_select, r1_bank, r1_final) appended to ROLE_ORDER; earlier registry entries
  unchanged (checked by `data.py` against the base registry).
- `data.py`: optional `base_dataset` copies every base file and layout role unchanged and plans only the new roles.
  `tools/ledger.py` counts planner replay only for planned roles.
- `accounting.py`: inside a runner job each process records its step count in `$MAE_RUN_DIR/env_steps/`.
  The ledger uses these only for jobs without another source (test jobs). They cross-check summaries: data 32,184
  = planner replay; canary BC/probe/branch step records equal their summaries.
- Tests locate untracked data through `MAE_PROJECT`, so the suite runs as a runner job from the source snapshot.
- `tools/data_gate.py --r1`; `tools/r1_stats.py` (exact t CDF for any df, Holm, sign-flip);
  `tools/power_r1.py`; `tools/analyze_r1.py` + `tests/test_analyze_r1.py` (7 synthetic tests);
  `tools/run_r1.py` (admission rule); `tools/r1_canary_check.py`; `experiments/r1/make_batches.py`.
- **Defect (2026-11-01 01:02 UTC): telemetry rename race.** Batch 20261101T005849-94851 (seed 17) stopped:
  `r1-bc-s17` failed with FileNotFoundError in `telemetry.resource_heartbeat`. The heartbeat thread and the main
  thread wrote the same `telemetry.tmp`; one rename removed the other's file. Present since M0; it had not fired
  before (113 earlier jobs). Fix: a temporary name per process and thread. `tests/test_telemetry.py` (4 threads x
  300 writes) fails on the old code and passes on the fix. Telemetry only; no training, evaluation or data code
  changed. The failed job (86,095 BC-evaluation actions, counted in the ledger) is kept. Seed 17 reruns under a
  new batch ID with the same seed and batch file; seeds 15-16 ran the earlier code, which differs only here.

## 2026-11-01 — Programme under Amendment 4 (R2, E1, E2)
- `tools/ledger.py`: a job without a summary counts at least its managed step records (`partial_unrecorded`).
  Found by the R1 audit: the failed r1-bc-s17 ran 128 evaluation actions after its last metrics row. Ledger total
  118,670,302 -> 118,670,430.
- `tools/audit_r1.py`: targeted, independent R1 audit (inventory, lineage, panel fingerprint, statistics with its
  own t CDF, action counts, failure record, exact decomposition). Outputs `reports/r1/audit.json`,
  `decomposition.csv`.
- `src/bc2rl/ppo.py`: `anchor_penalty()` and arms `01p`/`01s` (`COMPONENT`). Arm 01 keeps the original expression.
  New per-update stats: `anchor_kl_prefix`, `anchor_kl_suffix`, `anchor_penalty` (no effect on any RNG).
  `src/bc2rl/rl.py`: anchors carry `is_prefix`; the component is passed to PPO, recorded in configs and summaries,
  and restored on resume; optional `eval_layouts_n` (first n layouts of the eval role).
  Tests (`tests/test_ppo.py`): "both" equals the original loss and gradients bitwise; prefix + suffix = both;
  all RNG streams identical across component arms after an update; "both" with labels equals the unlabelled path.
- `src/bc2rl/diag.py crosspanel`: evaluates a saved branch state (hash checked) on several panels with its own
  eval seed; new attempt files only.
- `src/bc2rl/splits.py`: namespaces r2_select 115, r2_bank 116, r2_final 117 appended. `tools/data_gate.py --r2`.
- New tools: `tools/analyze_r2.py` (blinded until 20/20), `tools/power_r2.py`, `tools/analyze_crosspanel.py`,
  `tools/analyze_comp.py`, `tools/run_program.py`, `tools/r2_canary_check.py`, `tools/battery_watch.py`;
  `experiments/program/make_batches.py` and `plan.json`.
- 2026-11-01, after the R2 test batch: **accounting defect.** The r2-smoke runner job ran ~0.22M environment actions
  that no step record kept: `src/bc2rl/accounting.py` chose the record directory at the first flush, after the
  smoke tests had pointed `MAE_RUN_DIR` at temporary directories. Fix: the directory is fixed at import (the job's
  own directory). Test: `test_record_dir_fixed_at_import_not_by_later_env_changes` (fails on the old code: the
  record lands in the changed directory). Affected: r2-smoke only (the ordinary suite's count, 59,274, matches the
  earlier measurement; R1's test jobs skipped the smoke tests). Ledger: +250,000 conservative estimate
  (`research/ledger_adjustments.json`). Training and evaluation code are unaffected; the R2 canary runs after it.

## 2026-11-01b — Amendment 5 implementation (before any A3/calibration/pilot run)
- `src/bc2rl/ppo.py`: arms `01w` (mixed penalty, base 0.75 x kl_coef) and `11s` (resets + suffix-only);
  `KL_SCALE`, `arm_kl_coef`, `effective_coefficients`; optional `update_diagnostics` (KL between successive
  policies on 256 + 256 fixed anchor rows by stage; actor parameter-change norm), no RNG and no gradient.
- `src/bc2rl/rl.py`: branch and resume use `arm_kl_coef`; branch metadata/summary record
  `kl_effective_prefix_suffix`.
- `src/bc2rl/bc.py`: `sample_batch` (original sampler unchanged, same RNG calls; optional `prefix_prob`);
  each checkpoint evaluation writes raw `attempts_u<update>.jsonl` (normal rows with K; bank rows with bank_K, bin).
- `src/bc2rl/splits.py`: roles a3_select 118, a3_bank 119, a3_final 120, pl_select 121, pl_bank 122, pl_final 123.
- `tools/data_gate.py --r3`; `experiments/a3/data-r3-v1.json` (base r2-v1).
- Analysis and tooling: `tools/analyze_a3.py` (+ tests), `tools/power_a3.py`, `tools/a3_canary_check.py`,
  `tools/analyze_cal.py` (+ tests), `tools/run_program2.py`, `experiments/program2/make_batches.py` and plan.
- Tests: `tests/test_ppo.py` (+4: coefficients, fixed-state value/gradient additivity and scaling, exact expected
  penalty, diagnostics leave training bitwise unchanged), `tests/test_bc_sampler.py` (2), `tests/test_analyze_a3.py`
  (6), `tests/test_analyze_cal.py` (2). Local full suite: 288 passed, 3 skipped (actions recorded by the ledger).
