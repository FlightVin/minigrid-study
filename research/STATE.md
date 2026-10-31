# State

**Current milestone:** Pre-M4 development campaign complete (owner amendment 2026-10-31). Protocol
Amendment 1 proposed. **Waiting for owner approval** before confirmation data or M4.

**Established**
- Manuscript SHA-256 `38326ef0...f92b4`; no substantive conflict with project.md.
- Host: Apple M5, 10 cores, 24 GiB. Backend: MPS (1,404 actions/s vs 331 on 4 CPU threads).
- M0: canaries 7/7; 251 tests pass (task, planner, restore, splits, evaluation, PPO, RL smoke).
- M1: dataset dev-v2; BC rule early = 4k, extended = 16k updates (FINDINGS F1). K=3 access << K=1 at
  equal suffix competence.
- M2: default PPO (lr 3e-4, ent 0.01) collapses the BC policy (F2). Screen selected actor lr 3e-5,
  entropy 0, early-stopped critic pre-fit (F3). It holds but does not yet improve p in 50k actions.

- M2b/M3: with R2, ordinary PPO improves in 7/8 forks (mean P1 0.26 -> 0.37 over 250k; F5, F6).
  No screened intervention separates from arm 00 on development data.
- M3 four-arm (F7): all six contrasts average within 0.02 of 0; arm 00 replicate SD 0.027.
- Frozen: alpha* 0.25, lambda* 0.01, 250k endpoint, 5 new seeds, conf_final 32 x 16, delta 0.05.
- Audit (F8): no correctness defect; metrics recompute exactly; corrections C1-C5 recorded.
- Campaign (F9): learning continues to 500k (+0.065 mean); no contrast separates; same-fork path SD 0.048;
  the M3 K=3 combined benefit did not reproduce; arrival-state competence < planner-bank c.

**Uncertain**
- Whether any intervention differs from arm 00 by >= 0.05 on confirmation data (M4).
- Within-seed correlation of stratum contrasts (precision scenarios rho 0-0.5).
- Cause of the arrival-state competence gap beyond time (prefix configuration?).
- Critic is near a constant predictor; advantages are noisy.

**Owner limits:** 4 cores, 6 GiB, 1 job (raise after benchmarking), no hour cap, 80M-action cap.
Pause after PROTOCOL_FREEZE.md. Two-hourly reviews in research/REVIEWS.md (review 3 done 2026-10-31 01:35).

**Resources used:** 3.74 h batch wall; 36.82M of 80M actions (46.0%), including 3.10M estimated test actions.

**Blockers:** none.

**Next action**
- Owner decision on M4 option A + Amendment 1. Then: generate conf-v1 (with conf_final 64), data gate, BC
  seeds 10-14, M4 batches per seed.
