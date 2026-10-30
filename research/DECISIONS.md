# Decisions

Dated record of protocol decisions, owner amendments, budgets and their reasons.

## 2026-10-30 — Manuscript provenance

- File: `mac-agentic-engineering/context/_BC2RL__Can_Early_Behavior_Guide_Sparse_Reward_RL_Training_.pdf`
  (13 pages, created 2026-10-30 14:56 EDT; locally excluded from Git).
- SHA-256: `38326ef009986ea7a1c3e2e5a68492977952ad2a957a03914bd8557c596f92b4`.
- Sections used: 1 Introduction, 2 Additional definitions, 3 Prior research.
- Section 4 (Preliminary experiments) is excluded. Its text appeared in a full-text extraction.
  It was not used to choose any task, model, checkpoint, hyperparameter, hypothesis or outcome.
- Harness: `mac-agentic-engineering` at `b53f29a51d32c5b0e744627c17b52d9bd25fcef8`
  (branch `mac-host-fixes`; base `b56e626` plus one macOS fix, see IMPLEMENTATION.md).

### Research questions (exact manuscript wording)

1. **RQ1:** When do demonstration-state starts, behavior preservation, or their combination improve
   subsequent PPO learning?
2. **RQ2:** Can early measurements predict which option will help on held-out task conditions, more
   effectively than simpler selection methods after accounting for their cost?

### Definition mapping (manuscript -> this study)

| Manuscript | Study implementation |
|---|---|
| Task condition `x`, limit `H_x` | One layout: full map, object placements, agent start, `H_x = L_prefix + S_prefix + T_suffix` |
| Start distribution `rho_x` | Point mass at the layout's start. Attempts differ only by policy sampling. Recorded here so `Ck`/`Rk` use exact-start attempts |
| Study "condition" | (K, suffix family, BC checkpoint). Metrics average over its fixed layout set with equal layout weights |
| Boundary, `tau_x` | First gateway entry into the suffix after all required doors are open |
| `q_pi(x)`, `p_pi(x)` | From the same normal-start attempts |
| `nu_x`, `c_pi(x; nu_x)`, `Delta c` | Fixed competence bank from planner rollouts on separate donor layouts; same bank, weights and attempt seeds for all policies |
| `mu_{pi,x}` | Logged first-crossing states; reported as support checks, never assumed equal to `nu_x` |
| Light-BC / extended-BC | Early / extended checkpoints on one BC training path per replicate |
| `Y_ap` (a = starts, p = preservation) | `Y_ab` in project.md; same four arms 00/10/01/11 |
| `Delta_access = Y10 - Y00` | Reported as "demonstration-start benefit". The manuscript name is kept in tables, with the caveat that resets do not isolate access |
| `Delta_preserve`, `I` | Same definitions. project.md adds `Y11 - Y10` and `Y11 - Y01` |
| `P1`, `Ck`, `Rk` | Per-layout unbiased estimators, averaged with fixed weights; equal weights across K x checkpoint strata |

### Conflicts between manuscript and project.md

No substantive conflict was found. Points that needed an explicit resolution:

1. **Predictive test inside RQ1.** The manuscript says RQ1 tests whether low access with substantial
   competence predicts a reset benefit, and whether declining competence predicts a preservation benefit.
   The core has four condition averages. Resolution: report these as descriptive paired scatterplots
   with uncertainty (project.md 8.3). No inferential predictive claim is made from the core alone.
2. **Short-trial selection episodes.** The manuscript says trials are evaluated "on development episodes".
   Resolution: these are selection evaluations on the selection/diagnostic split, never on final
   evaluation layouts, and they are charged against the allowance `B`.
3. **Contrast naming.** See the mapping table (row `Delta_access`).

## 2026-10-30 — Environment

- Replaced the empty owner venv (CPython 3.14.6 from miniconda) with CPython 3.12.14 arm64 (uv).
  Reason: the harness requires native arm64 Python 3.11 or 3.12. The old venv held only pip.
- Pinned in `requirements.lock`: torch 2.15.0, minigrid 3.2.0, gymnasium 1.4.0, numpy 2.5.4, psutil 7.0.0.
- MPS is built and available; a small MPS matmul ran. `PYTORCH_ENABLE_MPS_FALLBACK=0` (runner default).

## 2026-10-30 — Owner resource limits and working rules

Owner answers, applied with `mae configure --cpus 4 --memory-gb 6 --jobs 1 --hours 8`:

- CPU: 4 aggregate core equivalents. Memory: 6 GiB (RSS + MPS driver proxy).
- Parallel jobs: 1. The owner authorizes raising this after benchmarking, within 4 cores and 6 GiB.
- Cumulative experiment hours: **no cap** (owner). The project.md cap of 80M executed environment
  actions still applies, and so does the 20% reserve for confirmation, audit and failures.
- Batch wall limit: owner set no hour cap. 8 h is used only as a per-batch stall safeguard. It is
  not a budget; long phases are split across batches.
- The Mac is kept awake by Amphetamine. The harness adds no sleep control.
- Pause after committing `research/PROTOCOL_FREEZE.md` (end of M3) and report to the owner before M4.
- The agent sets scientific thresholds (effect size, equivalence margin, precision rules) as the
  responsible scientist, before seeing confirmation outcomes, and records the reasons here.
- Git: track `.gitignore` (venv, .DS_Store, caches, `.mae/`, `data/`). Commit on `main`;
  pushing to `origin` (github.com/FlightVin/minigrid-study) is authorized.
- Harness repository (owner amendment): not listed in `.gitignore`; treated as a nested,
  independent sub-repository. It is not a Git submodule, because the runner rejects snapshots
  containing `.gitmodules` and the harness has no remote. The `mae init` local exclusion in
  `.git/info/exclude` stays, so the outer tree is clean for the runner. Every run manifest records
  the harness SHA; harness commits are made in its own repository.

## 2026-10-30 — Owner amendment: periodic research reviews

Every two hours of active work, pause new submissions and write a research review: validity of
comparisons against RQ1/RQ2, failures, assumptions, alternative explanations, evaluation leakage,
resource use, risks, wasted effort and the next most informative experiment. Verify claims against
artifacts. Record reviews in `research/REVIEWS.md` and update the plan. Running jobs stay monitored.
Active work began 2026-10-30 ~16:00 EDT; first review due ~18:00 EDT.

## 2026-10-30 — Task and data protocol choices (development; freeze pending at M3)

| Decision | Choice | Reason |
|---|---|---|
| Canvas and K | Fixed 21x9 for all K; inactive slots solid wall; gateway (12,4) fixed and yellow | Same tensor and parameter count for every K; same gateway and final key |
| Boundary | First step with agent x >= 13 | Possible only after every door unlocks (door chain), so the grid certifies the prefix; no hidden flag |
| Success | On the delivery floor while carrying the purple ball | Pickup alone is not success; key/distractor on delivery is not success |
| Deadline | Terminal (not truncation) at `H_x` | Remaining time is observed, so the deadline is part of the MDP; bootstrap value is zero |
| `H_x` | `tau_planner + 24 + 80` (development values) | project.md starting values; may be adjusted once on dev data, then frozen |
| Time scale | remaining / 200 for every K | Common normalizer; max `H_x` observed is 163 |
| Suffix matching | Suffix drawn from its own RNG stream; suffix planned on its own stream inside gateway+suffix | Same layout seed gives identical suffix, suffix plan, arrival pose and remaining time across K |
| Final-key convention | Planner always carries the yellow key across the boundary | Restricted suffix search; same total plan length as unrestricted search (300 layouts tested) |
| Splits | 10 roles, SeedSequence namespaces; full-layout disjoint; evaluation/bank roles also suffix-disjoint from training and from each other | Removes exact-suffix memorization as an explanation for competence results |
| Confirmation data | Seeds registered now; layouts/banks generated only at the freeze | `H_x` constants may still change; avoids any early contact with confirmation data |
| Competence bank | 64 donors per K (64 distinct layouts); bins by donor index 50% entry / 25% retrieval / 25% carrying; retrieval = uniform strictly between entry and pickup; carrying = first half of the delivery leg, never the last action | Fixed mixture; avoids near-terminal dominance; identical items across K (asserted in data generation) |
| Reset bank | Reset-donor planner states per K; bin by the same 50/25/25 mixture, then uniform state in bin | Same distribution for arms 10 and 11; original remaining time kept |
| Anchor bank | Anchor-donor planner states per K; 25% prefix / 75% suffix, uniform within | project.md default emphasis on suffix states |
| BC weighting | Transition-level, balanced across K: each batch is half K=1 and half K=3, uniform within K | Long K=3 prefixes do not dominate; one joint actor serves both K |
| Evaluation sampling | Per-attempt uniform streams (inverse-CDF), same seeds for every policy | Common random numbers for paired comparisons; batch-independent (tested) |
| Branch streams | Coin / normal-layout / bank-state streams separate; action-sampling stream continues from the fork | The k-th normal layout is the same in all arms; trajectories diverge naturally |
| Initial critic | Pre-fit on pi0 normal-start returns (gamma = 1) before the probe; shared by all branches | Avoids a random critic driving early actor updates (WSRL concern); its cost is reported as preprocessing |

## 2026-10-30 — BC checkpoint rule and time constants (before any PPO outcome)

Evidence: BC curve batch `20261030T204407-76602`, dev seeds 0 and 1 (dataset dev-v2; 50 bc_val layouts per K and the dev bank;
see FINDINGS F1). Rule, fixed across all seeds and conditions:
- **Early (light) BC = 4,000 updates; extended BC = 16,000 updates** (batch 256, Adam 3e-4).
  Early has useful but limited competence (c 0.26-0.42) and some normal-start success; extended has
  c ~0.66 and is past the held-out-loss minimum (~8,000), i.e. longer fitting on one training path.
  Neither saturates (p <= 0.65). Selected on BC validation/dev-bank data only, before any PPO run.
- **Time constants unchanged: S_prefix = 24, T_suffix = 80.** Access and competence are both measurable
  at both checkpoints for both K, so the feasibility gate gives no reason to adjust.
- BC replicates for M3 development: seeds 0 and 1 (these runs). Confirmation BC seeds will be new.

## 2026-10-30 — M2 ordinary-PPO stability screen (prespecified before running)

Trigger: canary probe `20261030T205335-81100` collapsed (see FINDINGS F2): first update approx-KL 0.35,
ratios 0-13.6, entropy 0.24 -> ~1.3, 0 successes in 428 probe episodes, p 0.25 -> 0. The pre-fit
critic was worse than a constant on held-out episodes. This is an optimization defect, not evidence
about stage practice. Fixed for all variants: critic pre-fit with episode-level 60/20/20 split and
early stopping on validation MSE (up to 2,000 steps).
- Conditions (development, seed 0): (K=1, early BC u4000) and (K=3, extended BC u16000). Probe only
  (ordinary PPO, 50k actions). No intervention arm is run or inspected.
- Variants: S1 lr 3e-4 ent 0.01; S2 lr 1e-4 ent 0.01; S3 lr 1e-4 ent 0; S4 lr 3e-5 ent 0;
  S5 lr 1e-4 ent 0 target-KL 0.02; S6 lr 3e-4 ent 0 target-KL 0.02. Advantage normalization on.
- **Selection rule:** highest mean post-probe normal-start p over the two conditions (dev_eval,
  32 layouts x 4 attempts); among variants within 0.03 of the best, the smallest mean approx-KL.
  Delta-c is reported but **not** used for selection. The chosen setting is then used in M2/M3 for all
  arms, and frozen at M3.

## 2026-10-30 — PPO setting selected by the prespecified screen

S4 selected: actor lr 3e-5, critic lr 3e-4, entropy coefficient 0, advantage normalization on, no
target-KL, critic pre-fit with early stopping. Applies to all arms. Open risk: learning may be too slow
for the planned budgets; the M2 continuation (250k actions per arm, K=3 extended, seed 0) checks
whether ordinary PPO improves at all. If every arm is flat, the next lever is rollout batch size
(more environments per update), changed for all arms together, on development data only.

## 2026-10-30 — M2b rollout-size check on ordinary PPO only (prespecified)

Question: is ordinary PPO noise-limited by its 512-action rollout batch? Arms with interventions are
not run. Conditions (dev, seed 0): (K=1, early) and (K=3, extended). Each run: critic pre-fit, 50k
probe, 250k continuation of arm 00, final evaluation (dev_eval 32 x 16; dev bank 64 x 4).
- R1: 4 envs x 128, minibatch 128, actor lr 3e-5 (current; K=3 result reused from batch
  20261030T211303-98764, arm 00).
- R2: 16 envs x 128 (2,048 per update), minibatch 512, actor lr 3e-5.
- R3: 16 envs x 128, minibatch 512, actor lr 1e-4.
**Rule:** choose the highest mean final P1 of arm 00 over the two conditions. If the best is within
0.03 of R1, keep R1. Delta-c and all intervention outcomes are excluded from this choice.
Caveat: R2/R3 also change the probe (same rollout setting in probe and branches); the probe allowance
stays 50k actions.

## 2026-10-30 — Rollout setting R2 selected; M3 design (prespecified before running)

**PPO setting (all arms, all later runs):** 16 envs x 128 steps (2,048 actions per update), 4 epochs,
minibatch 512, actor lr 3e-5, critic lr 3e-4, entropy 0, clip 0.2, GAE 0.95, gamma 1, grad clip 0.5,
advantage normalization on, critic pre-fit (16k actions, early-stopped). Selected by the F5 rule
(mean final P1 0.41 vs 0.30 and 0.10). Anchor batch stays 128 per actor minibatch.

**M3 design.** 8 forks = K {1,3} x BC {4k,16k} x BC seeds {0,1}; probe 50k each. Branches per fork:
00; 10 with alpha {0.25, 0.5}; 01 with lambda_KL {0.01, 0.1, 1.0}. 250k continuation actions each.
Final evaluation dev_eval 32 x 8 attempts, dev bank 64 x 2; curve every 125k (32 x 2, bank 64 x 1).
Fork order and arm order within each fork are shuffled with a fixed seed (20261030).
**Selection rule:** alpha* = the alpha with the higher mean final P1 of arm 10 over all 8 forks (equal
weight per fork); lambda* = the lambda with the highest mean final P1 of arm 01. If candidates are
within 0.02, choose the weaker intervention (smaller alpha / lambda). One value each, for all K and
checkpoints. Then arm 11 with (alpha*, lambda*) runs on the same 8 forks to complete the M3 comparison.

**Budget estimate (environment actions).** Used so far ~6.5M. M3: 8 probes x ~0.12M + 56 branches x
~0.29M ~ 17M. M4 at a 500k endpoint: 20 probes x 0.12M + 80 branches x ~0.57M ~ 48M. Total ~ 72M of the
80M cap, reserve ~8M. That reserve is below 20% of the remaining estimate (~13M), so a 500k M4 endpoint is
**not affordable** under the cap unless M3 curves justify a shorter endpoint or evaluation is trimmed.
The endpoint will be chosen from M3 development curves before confirmation (DECISIONS at freeze).

## 2026-10-30 — M3 selection applied; arm 11 and replicate batch

Rule applied to batch `20261030T214937-19577` (F6): mean final P1 arm 10 alpha 0.25 = 0.3770, alpha 0.5
= 0.3901 (difference 0.013 < 0.02 -> weaker value): **alpha* = 0.25**. Arm 01: lambda 0.01 = 0.3589,
0.1 = 0.3403, 1.0 = 0.3262: **lambda* = 0.01**. Not revised after seeing the data.
Batch `experiments/m3/arm11.batch.json` (16 jobs, order shuffled with seed 20261031): arm 11 (alpha
0.25, lambda 0.01) on each of the 8 M3 forks, plus one replicate of arm 00 per fork (`-rep`). The
replicates are a noise measurement only. They are excluded from contrasts and from every selection.

## 2026-10-30 — Protocol freeze

`research/PROTOCOL_FREEZE.md` fixes the M4 design: alpha* 0.25, lambda* 0.01, 250k endpoint (budget; F6),
BC seeds 10-14, conf_final 32 x 16 and conf_bank 64 x 4, smallest effect of interest 0.05 P1, t-interval
over seeds plus crossed cluster bootstrap, equivalence margin ±0.05 (TOST), stop rule at 72M actions,
M5 as a costed proposal. Arm 00 replicates (F7) informed the precision estimate only. The freeze SHA-256
is recorded in the commit that follows it.
