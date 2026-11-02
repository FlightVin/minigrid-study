# State

**Current milestone (2026-11-02):** owner programme 2026-11-02, the access-focused RQ1 study (PROTOCOL_FREEZE
Amendment 7; instruction verbatim in `mac-agentic-engineering/project.md`, harness `936e761`). Earlier verdicts are
closed (F10-F25, read with F23 and F26).

**Active objective.** Can the placement and ordering of demonstration-state starts improve learning of the
prerequisite sequence and normal-start success at a fixed budget? Phases:
1. Failure diagnostics on frozen A4 checkpoints, followed by the opportunity rule.
2. Development pilot: seeds 90-95; arms 00, B5, C5, D5; 501,760 continuation actions.
3. Frozen gate.
4. Conditional confirmation: seeds 96-115, 00 against the selected method.

**Established.**
- A4 (F24-F26): the preservation benefit at 1M is +0.005 [-0.015, +0.025]. Within-panel learning in arm A was mostly
  in the access term (+0.162 of +0.204, E250 to E1M). K=3 targets were met in 17/20 seeds.

**Uncertain.**
- whether access headroom translates into success (reference 1);
- whether arrivals are finishable (certification);
- whether any reset placement improves normal-start success by 0.05 or more.

**Owner limits.** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid or remote compute.
- **Battery:** stop at 31% or lower, also on AC. The persistent flag `.mae/monitor/BATTERY_PAUSE.json` blocks
  everything. Never restart automatically.
- Two-hour reviews.

**Budget.** 70M from ledger 311,392,581 (`tools/run_program5.py --status`). Conservative bounds: preparation about
1.4M, pilot 19.8M, confirmation reserve 38.8M, audit 0.3M. Protection is about 9.6M worst case.

**Monitors.** The battery guard and review cron are to be started at execution (none running yet).

**Next action.**
1. Commit.
2. Start the guard and the review cron.
3. Run the data batch, then the tests batch.
4. Run diagnostics, then `tools/analyze_diag5.py` (opportunity rule).
5. Pilot canary s90, then canary check, then seeds 91-95.
6. Run `tools/analyze_p5.py` (gate).
7. Run the confirmation if the gate passes.
8. Verify and report.
