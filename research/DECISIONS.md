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
