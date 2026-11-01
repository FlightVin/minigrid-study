# State

**Current milestone (2026-11-01):** owner programme under PROTOCOL_FREEZE Amendment 4 (instruction recorded in
`mac-agentic-engineering/project.md`, harness `000fd83`). Priorities: (1) targeted R1 audit + freeze [audit done,
REPORT R1.10]; (2) R2 20-seed replication; (3) E1 cross-panel; (4) E2 anchor components; (5) audit and report.
Budget: 50M actions from corrected ledger 118,670,430 (`tools/run_program.py --status`). No wall-time limit.

**Active objective:** R2 — does preservation (lambda 0.01) improve normal-start P1 at K=3 with early BC after
501,760 actions? Seeds 23-42 (fixed), one two-sided paired t-test at 0.05, R2 data only. Analysis blinded until
20/20 (`tools/analyze_r2.py`).

**Established**
- M4 (F10): all 6 primary contrasts practically equivalent (equal-weight aggregate). Unchanged.
- F11 (post hoc): K=3/early-BC preservation +0.045 at E500 (5 seeds, SD 0.008).
- R1 (F12, F13): +0.040 [0.004, 0.076]; Holm-2 not met (p_holm 0.067); interaction not supported. Compatible
  with a positive effect similar to M4's; power at SD 0.043 was limited (~0.62), not zero.
- R1 audit (F13): 64 endpoint records exact; stats reproduce; ledger +128 (failed job). Exact decomposition:
  R1 early E500 access +0.0115, completion +0.0288; M4 subgroup access +0.033, completion +0.015 (4 defined
  seeds). "Mainly access" withdrawn for R1, qualified for M4.
- Earlier: M0-M3 engineering and development findings F1-F9 (see FINDINGS).

**Uncertain**
- Whether the K=3/early-BC effect is real (R2).
- Why the seed SD differs between M4 and R1 (selection, small-sample SD, panel, training variability; E1 tests panel).
- Which anchor component carries the effect (E2; exploratory, 251,904 only).

**Owner limits:** 4 cores, 6 GiB, one job, native MPS via the runner, no paid/remote compute. Battery watch:
stop below 20% (`tools/battery_watch.py`, log `.mae/monitor/battery_watch.log`). Two-hour research reviews.

**Monitoring state:** battery watch running (session task brnp52lai); review cron 19ac8cf7 (session-only, every
2 h at :53; recreate in a new session). R2 seeds driver `tools/run_program.py` (PID 42665, create 1793506742.71;
log `.mae/monitor/r2_seeds.log`) running seed-s23-rest then seeds 24-42; watcher bound to it.

**Resources used:** before the programme 118,670,430 (R1 25,471,227). Programme spend: `run_program.py --status`.

**Blockers:** none.

**Next action**
- Done: freeze `c372ef7`, data + gate, tests, drill, canary (pass). Running: seed-s23-rest, seeds 24-42.
  Then E1 -> E2 -> final tests -> audit -> report. Resume rule after any
  interruption: `tools/run_program.py --status` lists incomplete batches; rerun them (complete jobs are skipped
  only at batch level; an incomplete batch is rerun in full from its input checkpoints under a new batch ID).
