# State

**Current milestone (2026-11-01b):** owner programme under PROTOCOL_FREEZE Amendment 5 (instruction verbatim in
`mac-agentic-engineering/project.md`, harness `7ed7285`). Phases: (1) audit + freeze [done]; (2) A3 anchor
allocation, seeds 43-66 (confirmatory); (3) initialization calibration, seeds 67-69; (4) calibrated-regime pilot
(conditional); (5) synthesis, verification, report. No wall-time limit. Do not stop at "nothing authorised" while a
later phase is feasible.

**Active objective:** calibration (seeds 67-69, rho 0.2/0.5/0.8, checkpoints 4k/8k) -> frozen selection
(`tools/analyze_cal.py`) -> pilot if a variant qualifies.

**A3 done (F19):** H1 C-A at 251,904 supported, +0.0106 [+0.0019, +0.0193], p 0.019 (crossed bootstrap
[-0.0014, +0.0235] includes 0). Gate C-D +0.0007, C-E -0.0003: not supported. C-A at 501,760 +0.0160. Mainly a
completion (post-arrival) effect. Prefix-only (B) null at a weak strength. Verified independently.

**Established (closed studies; verdicts unchanged)**
- M4 (F10): aggregate equivalence. F11: post hoc K=3/early-BC mixed preservation +0.045 (5 seeds).
- R1 (F12): +0.040, Holm-2 not met. R2 (F14): +0.0097 [-0.0035, +0.0229], not supported; the interval constrains
  effects of the motivating size (F18 wording).
- E1 (F15, corrected F18): cohort/panel contrasts with intervals; panel effects of ~0.02-0.04 not excluded.
- E2 (F16): suffix-only +0.055 in 3/3 seeds at 251,904 (exploratory) -> motivates A3.
- Component-code audit (F18, Amendment 5 B): no defect.

**Uncertain:** dose/allocation within the tested range (C = D = E); prefix preservation at an effective strength;
whether the initialization gives high entry competence with low access; reset/preservation value in such a regime.

**Owner limits:** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid/remote compute. Battery watch:
stop below 20%. Two-hour research reviews.

**Budget:** 130M from 158,314,282 (`tools/run_program2.py --status`). Required conservative ~97.3M; pilot ~9.1M;
12M reserve held for calibration/pilot admission.

**Monitoring state:** see "Monitors" below (updated at each launch).
- Monitors: battery watch (session task by3gm8o1w; log `.mae/monitor/battery_watch.log`); review cron d308a314
  (every 2 h at :47; session-only, recreate in a new session). Data r3-v1 batch 20261101T131324-69803; gate pass.
  Tests 288 + smoke 3/3; canary s43 batch 20261101T131538-69982 passes. Seeds driver `tools/run_program2.py` PID 71896
  (create 1793540164.95) finished 24/24 (exit 0). Calibration driver PID 79491 (create 1793568098.28; log
  `.mae/monitor/cal.log`) running cal-s67..69; watcher task b05nv58a6 bound to it.

**Recovery:** `tools/run_program2.py --status` lists incomplete batches; rerun them in plan order (complete jobs
count by summary or exit 0; an incomplete batch is rerun in full from its input checkpoints under a new batch ID).
Pilot batch files are placeholders until `make_batches.py --pilot RHO UPDATE --cal-batches B67 B68 B69`.

**Next action:** calibration finishes -> `tools/analyze_cal.py` -> `plot_program.py --which cal` -> (if selected)
`make_batches.py --pilot RHO UPDATE --cal-batches B67 B68 B69`, commit, battery check, run pilot -> analyze_pilot
-> verify_program2 -> p2-tests -> synthesis and report.
