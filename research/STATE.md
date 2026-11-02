# State

**Current milestone (2026-11-02):** the owner programme 2026-11-01c (A4, PROTOCOL_FREEZE Amendment 6) is complete.
No work is authorised. The owner decides on the next step (REPORT section S6).

**Established (closed):**
- A4 (F24): suffix-only preservation against ordinary PPO at 1,001,472 actions, K=3, rho 0.2 / 8k, n = 20 (seeds
  70-89). d = +0.0047 [-0.0152, +0.0246], p 0.63: not supported. H2 was gated out. Descriptive: +0.020 at 251,904,
  +0.012 at 501,760, then catch-up. Independent verification agrees.
- A4 cohort and costs (F25): 3/20 seeds met all calibration targets (tests the fixed procedure). Spend 55,727,013 of
  70M. Ledger 311,392,581. No pauses or retries.
- A3 (F19), calibration (F20), pilot (F21), synthesis (F22), corrections (F23): unchanged.

**Recommendation (F25, REPORT S6):** do not adopt suffix preservation for final success; no extension; no RQ2
selector. If further work is funded, target access (q).

**Owner limits (still in force):** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid or remote compute.
Battery: stop at 31% or lower, also on AC; the persistent flag `.mae/monitor/BATTERY_PAUSE.json` blocks all work;
never restart automatically. The guard must be started before any new heavy work.

**Monitors:** none running. Battery guard 31137 and review cron 5bcaa9b8 were stopped at completion on 2026-11-02.
The driver and watchers exited normally.

**Next action:** none. Wait for an owner instruction.
