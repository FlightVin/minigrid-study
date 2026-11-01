# Literature notes for the Amendment 5 synthesis (2026-11-01b)

Purpose: position A3 and the pilot against established work (owner instruction sections 3 and 11). Notes, not claims.

- Wolczyk et al. 2024, ICML, "Fine-tuning RL models is secretly a forgetting mitigation problem"
  (https://arxiv.org/abs/2402.02868). Frames poor fine-tuning as forgetting of pre-trained capabilities on Far states
  rarely visited early. Compares EWC, behavioural cloning on stored pre-training states (a KL/BC loss on a replay
  buffer), kickstarting on current-policy states, and episodic memory. BC-replay suits the state-coverage gap,
  kickstarting the imperfect-cloning gap. Establishes: preservation on stored states is a known remedy; which state
  source helps depends on the gap type. Does not (as summarised) vary the allocation of the stored-state penalty
  across stages of one task with a uniform-strength control.
- Rusu et al. 2016 "Policy distillation" (https://arxiv.org/abs/1511.06295): distillation in RL; no state selection.
- Recent preprints on state-selective distillation for LLM post-training (e.g. selective supervision on top-scoring
  states; https://arxiv.org/abs/2609.28145 and related) report that where the KL is applied can matter, with
  single-setting evidence. Not RL from sparse terminal reward; not peer-reviewed; cited only as context.
- Reset assistance: Florensa et al. 2017 (reverse curriculum), Uchendu et al. 2023 (JSRL), Tao et al. 2024 (RFCL),
  all in the manuscript. Establish that changing start states can make sparse reward usable; gains belong to full
  algorithms.

Positioning for A3: state-selective retention is not new. A3 contributes controlled evidence on one question in one
task family: holding the stored demonstration bank, sampler, estimator and PPO fixed, does restricting the same
forward-KL penalty to post-boundary states change normal-start success, and is any difference explained by a uniform
reduction of the mixed penalty? 24 independent seeds, prespecified gate. The pilot contributes only exploratory
evidence on whether reset and suffix-preservation value depends on a calibrated access/competence regime.
