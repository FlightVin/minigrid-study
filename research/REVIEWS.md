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

## Review 2 — 2026-10-30 ~19:25 EDT (after the M3 screen; no submissions during review)

**RQ fit.** The main risk from Review 1 is resolved: with R2, ordinary PPO improves in 7/8 forks (mean
P1 0.26 -> 0.37). RQ1 now compares interventions against a learning baseline. The K x checkpoint grid
spans P1 from 0.05 to 0.70 and access q from 0.25 to 1.0, so the conditions "where" each intervention
helps can be tested. The K=3 early forks sit near the floor; they contribute little signal.

**Validity.** Forks are hash-matched across arms; arms share streams; no confirmation data exist. The
screen chose alpha and lambda only from dev_eval P1 by a rule written before the batch. Applied
literally, the 0.02 tie rule picks alpha = 0.25 although alpha = 0.5 scored higher. I keep the rule:
changing it after seeing the data would be selection on the outcome.

**Evidence vs claims.** Screen differences (+0.017 to -0.047) are smaller than the fork-to-fork SD of
paired differences (0.04-0.06). Part of that SD is MPS nondeterminism (F5). I do not know how much.
This matters for M4: if the noise of a paired contrast is dominated by run-to-run nondeterminism, more
forks are the only remedy; if it is dominated by fork heterogeneity, stratified analysis helps.

**Alternative explanations.** (1) Preservation lowers P1 monotonically in lambda. This can be the
expected cost of holding the policy near a weaker pi0, not a failure of the mechanism. (2) Reset raises
bank P1 more than normal P1: suffix practice may help competence, while the binding limit for P1 at K=3
is access (q). This supports measuring q and c separately in M4.

**Leakage, resources.** No leakage found. Batch wall 1.56 h. Actions: 23.8M of 80M (29.7%). Peak
memory per job < 1 GiB. M3 used ~15.7M (estimate 17M).

**Waste.** None significant. The 3-value lambda grid was informative (monotone pattern).

**Plan update.**
- Run arm 11 (alpha 0.25, lambda 0.01) on the 8 forks, as prespecified.
- Add one replicate of arm 00 per fork in the same batch (identical config; differs only by MPS
  nondeterminism). This measures the null spread of a paired contrast and sizes M4. Cost ~2.5M.
- Endpoint: 250k is favoured. A 4-arm fork at 250k costs ~1.36M actions versus ~2.36M at 500k. Within
  the remaining budget less a 20% reserve, that is ~26 versus ~15 forks; with paired SD ~0.05 the
  forks, not the length, decide power. Final choice at the freeze.
