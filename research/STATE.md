# State

**Current milestone (2026-11-01b): programme complete.** Owner programme under PROTOCOL_FREEZE Amendment 5
(instruction verbatim in `mac-agentic-engineering/project.md`, harness `7ed7285`). All phases done: audit (F18),
A3 (F19), calibration (F20), pilot (F21), synthesis and costs (F22), consolidated report (`reports/REPORT.md`
section Q), independent verification (`reports/program2/verification.json`). No experiment is running or pending.

**Results:** A3 H1 supported (C-A +0.0106 [+0.0019, +0.0193] at 251,904; crossed bootstrap includes 0); gate C-D and
C-E not supported; +0.016 at 501,760. Calibration selected rho 0.2 / 8k. Pilot: no detectable normal-start effect
(3 seeds); K3 boundary-entry competence higher with preservation/resets. RQ2 selector not justified.

**Recommendation (REPORT Q7):** stop new training on this question; write up A3 with its scope. Optional future study
(owner decision): long-budget, pre-registered test in the calibrated regime (>= 16 seeds).

**Established (closed studies; verdicts unchanged)**
- M4 (F10): aggregate equivalence. F11: post hoc K=3/early-BC mixed preservation +0.045 (5 seeds).
- R1 (F12): +0.040, Holm-2 not met. R2 (F14): +0.0097 [-0.0035, +0.0229], not supported; the interval constrains
  effects of the motivating size (F18 wording).
- E1 (F15, corrected F18): cohort/panel contrasts with intervals; panel effects of ~0.02-0.04 not excluded.
- E2 (F16): suffix-only +0.055 in 3/3 seeds at 251,904 (exploratory) -> motivates A3.
- Component-code audit (F18, Amendment 5 B): no defect.

**Uncertain:** dose/allocation beyond the tested range; prefix preservation at an effective strength;
whether the initialization gives high entry competence with low access; reset/preservation value in such a regime.

**Owner limits:** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid/remote compute. Battery watch:
stop below 20%. Two-hour research reviews.

**Budget:** 130M from 158,314,282 (`tools/run_program2.py --status`). Required conservative ~97.3M; pilot ~9.1M;
12M reserve held for calibration/pilot admission.

**Monitoring state:** all owned monitors stopped at programme completion (battery watch 69759, review cron
d308a314; driver watchers exited with their drivers). Final ledger 97,351,286 of 130M (`tools/run_program2.py --status`).

**Recovery:** `tools/run_program2.py --status` lists incomplete batches; rerun them in plan order (complete jobs
count by summary or exit 0; an incomplete batch is rerun in full from its input checkpoints under a new batch ID).
Pilot batch files are placeholders until `make_batches.py --pilot RHO UPDATE --cal-batches B67 B68 B69`.

**Next action:** none authorised; awaiting owner direction on the REPORT Q7 recommendation.
