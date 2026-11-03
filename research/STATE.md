# State

**Current milestone (2026-11-02c, complete):** corrective prefix imitation study (owner instruction 2026-11-02c,
verbatim in `mac-agentic-engineering/project.md`, harness `1efcb5f`; PROTOCOL_FREEZE Amendment 9). Stopped at the
frozen development gate. No arm qualified, so no confirmation was run.

**Question.** Do new expert corrections on learner-visited prefix states (C) improve unassisted normal-start success
over ordinary PPO (A), and do they add value beyond matched demonstration replay (R)?

**Result (development, 6 seeds; F32-F33, REPORT V).** P1 at 501,760: A 0.191, R 0.195, C 0.080.
C − A −0.111 [−0.136, −0.086], 0/6 positive. R − A +0.004 [−0.067, +0.075], 3/6. C − R −0.115.
Independent recomputation agrees; evaluation replay 36/36 matched.

**Next.** None authorized. Proposals (not launched) are in F33 and REPORT V6. They need an owner instruction.

**Established (earlier, unchanged).** Closed verdicts F10-F30, read with F23, F26 and the F31 corrections.
Seeds 116-121 are used (development). Seeds 122-141 and role r7_conf were reserved and not used.

**Owner limits.** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid or remote compute.
- **Battery:** stop at 31% or lower, also on AC. The persistent flag `.mae/monitor/BATTERY_PAUSE.json` blocks
  everything. Never restart automatically.
- Two-hour reviews during active work.

**Budget.** Ceiling 80M from ledger 329,624,666. Spent 12,571,482 (scientific 12,492,768; reserve 78,714).

**Monitors owned.** None. Battery guard and review cron `14175706` stopped at completion.
