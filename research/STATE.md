# State

**Current milestone (2026-11-01c):** owner programme A4 under PROTOCOL_FREEZE Amendment 6 (instruction verbatim in
`mac-agentic-engineering/project.md`, harness `d8155d4`). Earlier programmes are closed; their verdicts are preserved
(F10-F22, read with the F23 wording corrections).

**Active objective:** A4. In the calibrated K=3 initialization (BC rho 0.2, 8k), does suffix-only preservation
(01s, effective 0.0075) improve normal-start P1 over ordinary PPO (00) at 1,001,472 actions (H1, n = 20, seeds
70-89)? If H1 is supported: does the benefit grow from 251,904 (H2)? Treatment outcomes stay blinded until 20/20.

**Established (closed):**
- A3 (F19): C-A +0.0106 at 251,904, supported conditional on the panel; the crossed bootstrap includes 0.
- Calibration (F20): rho 0.2 / 8k qualified on means; fragile.
- Pilot (F21): K3 bank competence rose; no resolved normal-start effect.

**Uncertain:**
- whether the A4 cohort reproduces the calibrated profile;
- whether bank-competence gains transfer to normal-start success with more training;
- whether the benefit grows, persists or is caught up.

**Owner limits:** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid or remote compute.
- **Battery: stop at 31% or lower, also on AC.** The guard polls every 15 s. The persistent flag
  `.mae/monitor/BATTERY_PAUSE.json` blocks all work. Never restart automatically; resume only on the owner's
  explicit instruction.
- Two-hour reviews: execution and validity only.

**Budget:** 70M from ledger 255,665,568 (`tools/run_program4.py --status`). Worst case about 61.8M; expected about
59.5M; protection about 8M.

**Monitors:** battery guard PID 31137 (task b826abobo; log `.mae/monitor/battery_guard.log`; status
`.mae/monitor/battery_status.json`); review cron 5bcaa9b8 (every 2 h at :43; checks the pause flag first;
session-only). Canary driver PID 31664 (create 1793580296.22; batch 20261102T004500-31671; log
`.mae/monitor/a4_canary.log`); watcher task bgf5l423o. Done: data (gate pass), arrival bank (96, frozen), tests
306 + smoke 6.

**Recovery after a battery pause** (owner instruction only):
1. Verify that nothing runs.
2. Delete the flag on the owner's instruction.
3. Run `tools/make_resume_a4.py <seeds>` and commit.
4. Start the guard, then `tools/run_program4.py <resume batch> <remaining seed batches>`.

Interrupted records are kept. `paused.json` in each paused branch gives the resume point.

**Next action:** commit the frozen protocol, then: guard, data batch, gate, arrival batch, tests batch, canary s70,
canary check, seeds 71-89, analysis, verification, report.
