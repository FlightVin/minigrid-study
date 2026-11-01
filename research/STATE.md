# State

**Current milestone (2026-11-01b):** owner programme under PROTOCOL_FREEZE Amendment 5 (instruction verbatim in
`mac-agentic-engineering/project.md`, harness `7ed7285`). Phases: (1) audit + freeze [done]; (2) A3 anchor
allocation, seeds 43-66 (confirmatory); (3) initialization calibration, seeds 67-69; (4) calibrated-regime pilot
(conditional); (5) synthesis, verification, report. No wall-time limit. Do not stop at "nothing authorised" while a
later phase is feasible.

**Active objective:** A3 — does suffix-only preservation (C, 0.0075 E_suffix KL) improve normal-start P1 vs ordinary
PPO (A) at 251,904 on 24 fresh seeds? Gate: then C-D and C-E (Holm). Arms A 00, B 01p, C 01s, D 01, E 01w.
Analysis blinded until 24/24 (`tools/analyze_a3.py`).

**Established (closed studies; verdicts unchanged)**
- M4 (F10): aggregate equivalence. F11: post hoc K=3/early-BC mixed preservation +0.045 (5 seeds).
- R1 (F12): +0.040, Holm-2 not met. R2 (F14): +0.0097 [-0.0035, +0.0229], not supported; the interval constrains
  effects of the motivating size (F18 wording).
- E1 (F15, corrected F18): cohort/panel contrasts with intervals; panel effects of ~0.02-0.04 not excluded.
- E2 (F16): suffix-only +0.055 in 3/3 seeds at 251,904 (exploratory) -> motivates A3.
- Component-code audit (F18, Amendment 5 B): no defect.

**Uncertain:** whether suffix-only helps on independent seeds; allocation vs strength; persistence to 501,760;
whether the initialization gives high entry competence with low access; reset/preservation value in such a regime.

**Owner limits:** 4 cores, 6 GiB, one job, native MPS/CPU via the runner, no paid/remote compute. Battery watch:
stop below 20%. Two-hour research reviews.

**Budget:** 130M from 158,314,282 (`tools/run_program2.py --status`). Required conservative ~97.3M; pilot ~9.1M;
12M reserve held for calibration/pilot admission.

**Monitoring state:** see "Monitors" below (updated at each launch).
- Monitors: battery watch (session task by3gm8o1w; log `.mae/monitor/battery_watch.log`); review cron d308a314
  (every 2 h at :47; session-only, recreate in a new session). Data r3-v1 batch 20261101T131324-69803; gate pass.

**Recovery:** `tools/run_program2.py --status` lists incomplete batches; rerun them in plan order (complete jobs
count by summary or exit 0; an incomplete batch is rerun in full from its input checkpoints under a new batch ID).
Pilot batch files are placeholders until `make_batches.py --pilot RHO UPDATE --cal-batches B67 B68 B69`.

**Next action:** freeze commit -> data r3-v1 batch -> `tools/data_gate.py --r1 data/r1-v1 --r2 data/r2-v1 --r3
data/r3-v1` -> tests batch -> canary-s43 -> `tools/a3_canary_check.py` -> seeds 44-66.
