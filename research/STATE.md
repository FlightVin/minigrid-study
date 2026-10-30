# State

**Current milestone:** M1 (throughput, demonstrations, banks, BC). M0 verified.

**Established**
- Manuscript SHA-256 `38326ef0...f92b4` recorded; no substantive conflict with project.md.
- Host: Apple M5, 10 cores (4P+6E), 24 GiB; MPS available. Only 6.4 GiB was free at profiling.
- Environment: CPython 3.12.14 arm64; torch 2.15.0, minigrid 3.2.0, gymnasium 1.4.0 (`requirements.lock`).
- Harness: 14/14 tests pass after a macOS `killpg` EPERM fix (harness `b53f29a`).
- M0: 7/7 resource canaries pass; task/planner/restore/split tests 236/236 pass.
- Planner suffix length 13-37 actions (mean ~24) for every K; tau ~12 (K=1), ~41 (K=3).

**Uncertain**
- Sustained throughput and CPU vs MPS speed: not yet measured.
- Whether the full M4 matrix fits the campaign budget: unknown until M1/M3 profiling.

**Owner limits:** 4 cores, 6 GiB, 1 job (raise after benchmarking), no hour cap, 80M-action cap.
Pause after PROTOCOL_FREEZE.md.

**Blockers**
- None.

**Next action**
- Actor/critic model; data generation job (registry, demos, banks); CPU vs MPS benchmark; BC curves.
- First research review due ~18:00 EDT.
