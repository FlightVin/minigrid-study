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
