# State

**Current milestone (2026-11-02c, running):** corrective prefix imitation study (owner instruction 2026-11-02c,
verbatim in `mac-agentic-engineering/project.md`, harness `1efcb5f`; PROTOCOL_FREEZE Amendment 9).

**Question.** Do new expert corrections on learner-visited prefix states (C) improve unassisted normal-start success
over ordinary PPO (A), and do they add value beyond matched demonstration replay (R)?

**Done.**
- Section 1 record audit (F31): direct key-vs-mask contrasts with layout-conditional and crossed intervals; key
  drops reclassified by door state; marked corrections in F29, F30, REPORT U.
- Design, label planner, sources, tests and analysis frozen (Amendment 9).

**Next.** Data r7-v1 → recovery bank → tests and smoke batch → panel addendum commit → development seeds 116-121
(seed 116 canary) → frozen gate (+ independent recomputation) → confirmation 122-141 only if selected → reserve
verification → reports.

**Established (earlier, unchanged).** Closed verdicts F10-F30, read with F23, F26 and the F31 corrections.

**Owner limits.** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid or remote compute.
- **Battery:** stop at 31% or lower, also on AC. The persistent flag `.mae/monitor/BATTERY_PAUSE.json` blocks
  everything. Never restart automatically.
- Two-hour reviews during active work (cron `14175706`).

**Budget.** Ceiling 80M from ledger 329,624,666; scientific cap 72M; 8M reserve. Spent so far about 0.56M
(audit and local checks). Conservative plan: development 13.76M, preparation 0.78M, confirmation 55.51M (C) or
39.05M (R).

**Monitors owned.** Battery guard (background task; pid in `.mae/monitor/battery_guard.pid`); review cron `14175706`.
