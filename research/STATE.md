# State

**Current milestone:** M2 (PPO canary). Four-arm continuation running: batch 20261030T211303-98764.

**Established**
- Manuscript SHA-256 `38326ef0...f92b4`; no substantive conflict with project.md.
- Host: Apple M5, 10 cores, 24 GiB. Backend: MPS (1,404 actions/s vs 331 on 4 CPU threads).
- M0: canaries 7/7; 251 tests pass (task, planner, restore, splits, evaluation, PPO, RL smoke).
- M1: dataset dev-v2; BC rule early = 4k, extended = 16k updates (FINDINGS F1). K=3 access << K=1 at
  equal suffix competence.
- M2: default PPO (lr 3e-4, ent 0.01) collapses the BC policy (F2). Screen selected actor lr 3e-5,
  entropy 0, early-stopped critic pre-fit (F3). It holds but does not yet improve p in 50k actions.

**Uncertain**
- Whether ordinary PPO improves at all within 250k-500k actions (main risk to RQ1).
- Critic is near a constant predictor; advantages are noisy.

**Owner limits:** 4 cores, 6 GiB, 1 job (raise after benchmarking), no hour cap, 80M-action cap.
Pause after PROTOCOL_FREEZE.md. Two-hourly reviews in research/REVIEWS.md (next ~19:25 EDT).

**Resources used:** ~0.7 h batch wall; ~2.5M of 80M actions.

**Blockers:** none.

**Next action**
- Analyse four-arm curves. If arm 00 is flat: prespecified rollout-size check on development data.
- Then M3 development comparison (K=1/3 x 2 checkpoints x 2 seeds) and intervention screen.
