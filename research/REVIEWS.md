# Research reviews

Two-hourly reviews (owner amendment 2026-10-30). Newest last.

## Review 1 — 2026-10-30 ~17:25 EDT (after ~1.5 h of active work)

**Status.** M0 verified. M1 gate passed (F1). M2: canary probe collapsed (F2); stability screen chose
S4 (F3); four-arm continuation (250k/arm, K=3 extended, seed 0) running as batch 20261030T211303-98764.

**Does the work still answer RQ1/RQ2?** Yes, conditionally. The task separates access from competence
as intended: at extended BC, K=3 has q ~0.45 versus ~0.98 for K=1, with the same suffix competence
(~0.66) on a K-matched bank (F1). RQ1 now depends on one thing not yet shown: that ordinary PPO can
improve at all in this regime. With actor lr 3e-5 the probe holds performance but does not improve it
within 50k actions. If all arms stay flat over 250k-500k, RQ1 would compare interventions on a
non-learning baseline. That would be a weak answer to "improve subsequent PPO learning".

**Are the comparisons valid?** Mechanically yes: forks are hash-verified and exactly reproducible on CPU;
branches share the normal-layout stream; evaluation uses common random numbers; confirmation data do
not exist yet. Two qualifications:
- "Ordinary PPO" is now conservative PPO (lr 3e-5, no entropy bonus), chosen because larger steps
  destroyed the BC policy. This is a legitimate, prespecified development choice, but the report must
  say that the tested PPO is step-size-limited and that results may not transfer to other settings.
- The critic is barely better than a constant (F3). Advantages are therefore mostly a noisy baseline.
  Any later decline in c could reflect value-estimation noise as much as missing stage practice. The
  analysis must keep this competing explanation explicit.

**Evidence vs claims.** No scientific claim has been made. Probe Delta-c values (e.g. -0.27 in F2) are
labelled optimization artifacts. S4 K=3 Delta-c of -0.09 is within noise (64 items x 2 attempts).

**Leakage.** Selection steps used only bc_val, dev_eval and dev_bank. Confirmation layouts and banks are
not generated. The screen selected on ordinary-PPO p only; Delta-c and intervention arms were not used.

**Failures and waste.** dev-v1 regenerated (bank mismatch, 3 min); one launch refused (dirty tree); one
probe failed on a seed-type bug (4 s); the first canary used a poorly fit critic. All cheap. The RL smoke
test now catches integration bugs before runner time.

**Resources.** 0.67 h batch wall; ~2.5M environment actions of the 80M cap (probe/branch summaries
1.52M; BC-curve evaluation ~0.6M; benchmarks ~0.3M; continuation ~1.2M running). Peak memory < 1 GiB,
no swap growth. MPS ~1,400 actions/s ordinary, ~950/s with the KL arm.

**Unresolved risks.** (1) PPO may not learn within budget (main risk). (2) 512-action batches hold ~4
episodes, so per-update signal is tiny; a larger rollout batch is the obvious next lever and on MPS it is
nearly free per action. (3) Estimates from 128 normal-start attempts have SE ~0.04, too coarse for a
5-point effect threshold in development screens.

**Next most informative experiment.** Read the four-arm curves. If arm 00 does not improve, run a
prespecified development check of rollout size (e.g. 16 envs x 128) at lr 3e-5 and 1e-4, selecting on
ordinary-PPO p after a fixed action budget, then start M3. Do not tune on intervention arms.
