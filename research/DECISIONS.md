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
Freeze commit `7f94f18`; `research/PROTOCOL_FREEZE.md` SHA-256
`2b5c5252de4824910a26e20c06b419a78056b98b1a286c85493abebcc28ab8f1`. Confirmation data are not generated
yet: per the owner's instruction, work pauses here for review before any M4 step.

## 2026-10-31 — Owner amendment: bounded pre-M4 development campaign (pre-registration)

Authority: owner amendment of 2026-10-31, recorded verbatim at the end of `mac-agentic-engineering/project.md`
(harness commit `366786a`). The freeze of 2026-10-30 (`7f94f18`) is kept unchanged; changes to the M4
design will be a dated amendment to `PROTOCOL_FREEZE.md`. No confirmation data are generated.
Campaign start 00:48 EDT; limit 4 h of active work.

**Development allowance (computed before any new training).**
- Remaining campaign capacity: 80,000,000 - 28,689,024 = 51,310,976.
- Conservative cost of the retained M4 design (freeze, 250k), from measured per-job maxima:
  - Branches: 251,904 train + curves (max 22,453 K=1 / 29,042 K=3) + final at 32 x 16 and 64 x 4 (2 x the M3
    maximum: 69,148 / 94,272). That is 343,505 / 374,218 per branch, x 40 each = 28.71M.
  - Probes: 17,003 warm-up + 51,200 + two diagnostics at 32 x 4 and 64 x 4 (135.5k / 148.1k) x 10 each = 2.84M.
  - BC evaluation: 10 checkpoints x 90k = 0.90M.
  - Data: 0.50M.
  - Total: 32.95M.
- Protected reserve: 10.26M (20% of the 51.31M remaining at the freeze). It is kept for M4 failures and
  retries, the post-M4 audit and cost overruns. It is not reduced as development spends.
- Allowance = 51.31 - 32.95 - 10.26 = 8.10M; min(8.10M, 8M) = **8.0M**.

**Engineering finding that shapes the plan.** M3 branch `final.pt` files hold actor, critic and counters only.
They have no optimizer, RNG, sampler or in-flight environment state. A continuation from them would restart
from weights alone, which the amendment forbids presenting as a continuous trajectory. All longer runs are
therefore **fresh runs from the hashed post-probe fork** (a declared separate pipeline segment:
501,760 continuation actions per branch, full cost counted). The code now saves complete hashed learner
state (`state_<n>.pt`) at 251,904 and 501,760, and adds a `resume` mode. On CPU, a resume reproduces the
uninterrupted run exactly (test `test_scheduled_branch_resumes_exactly`). The PPO pipeline has no
learning-rate or other schedule (constant Adam lr), so nothing ends at 250k and nothing is stretched.

**Quantization (verified in code).** Rollout 16 x 128 = 2,048. The probe executes 51,200 (25 updates; 50,000
requested). Endpoints 126,976 (62 updates), 251,904 (123), 376,832 (184) and 501,760 (245) are exact.
Configuration `continuation_actions` 500,000 executes 501,760.

**Pre-registered experiments** (batch `experiments/dev2/campaign.batch.json`; 26 jobs; one job at a time):

| ID | Question | Comparison and sampling | Max cost |
|---|---|---|---|
| E3a | Is evaluation repeatable, and how large is Monte Carlo variation for one fixed policy? | Re-evaluate M3 K3/16k/s0 arm 00 `final.pt`: (i) original seed 727000 (expect identical attempts); (ii) seed 727500 (32 x 8, 64 x 2) | 0.09M |
| E3b | Does the planner bank represent actual arrivals, and does arrival state or time explain the K=3 conditional-success gap? | K3/16k, seeds 0 and 1: first-crossing banks from pi0, arm 00 and arm 11 (32 x 2 normal starts each, success never consulted); evaluate pi0, probe, 00, 01, 10, 11 x 2 attempts per state, original clocks. Labelled separate condition "clock_extended": same 00/11 states with remaining = 104, policies 00 and 11 | 0.25M |
| E3c | Is lambda = 0.01 materially active? | Anchor KL and gradient norm of 0.01 x KL for probe, 00, 01, 10, 11 actors on all 8 M3 forks, compared with logged PPO actor gradient norms | 0 actions |
| E1 | Do effects emerge after 250k, and does ordinary PPO keep learning? | K=3, extended BC (16k), seeds 0 and 1, all four selected arms (alpha 0.25, lambda 0.01), fresh from the M3 forks to 501,760. Evaluations: 126,976 and 376,832 at 32 x 2 (normal only); 251,904 and 501,760 at 32 x 8 and 64 x 2. Balanced arm/seed order | 4.79M |
| E2 | Does the pattern survive an independent initialization? | New development seed 2 (seeds 10-14 untouched): BC with the unchanged dataset and rule (4k, 16k saved); probe and four arms at K=3/16k to 501,760, same evaluation schedule | 2.67M |

Total maximum 7.80M (at most 8.0M). Costs are from measured maxima for K=3/16k: final evaluation 33,222 + 6,653
and curve 8,331 actions.

**Scope limitation decided now.** All 16 continuations (K=1 and K=3) at fresh-run cost need ~9.6M, so they
do not fit. Following the amendment's priority, K=3 comes first, and an independent replicate is preferred over
the K=1 extension. Consequence: the moderation estimand D_seed (K=3 vs K=1) cannot be computed at 501,760.
Extended-BC-only results are labelled as that narrower estimand. A third seed of the extended-BC K=3 component
effects becomes available at 251,904 and 501,760.

**Stopping rules.**
- Engineering: stop a job only for non-finite statistics, a hash mismatch, a crash, a resource-limit breach or
  a stall of more than 400 s without heartbeat. A deterministic failure gets a fix and a new run ID. A verified
  transient failure gets one retry. Never stop because of an outcome.
- Budget: before each new submission, spent development actions plus the conservative remaining cost of the
  queued jobs must stay at or below 8.0M. If a projection exceeds it, drop E3b's clock-extended part first,
  then the curve points.
- Scientific: no extension beyond 501,760 in this batch. A 750k/1M extension needs a separate gate (amendment
  section 8) and is costed in the report.

**What would change the recommendation.**
- Arm 00 rises substantially from 251,904 to 501,760 (for example > 0.05 mean P1 over the three seeds):
  favour a longer M4 endpoint.
- A paired contrast at 501,760 grows to >= 0.05 with a consistent sign across 3 seeds: keep that arm central
  and size M4 for it.
- All contrasts stay within about ±0.03: M4 at 250k is the efficient design, and equivalence becomes the
  realistic claim.
- Arrival-bank P1 tracks normal P1 better than planner-bank c: report competence on arrival states as a
  secondary measure in M4.

## 2026-10-31 01:05 EDT — Ledger gap found; E2 deferred for budget (no outcome inspected)

The ledger audit found environment actions executed outside the runner. These are the pytest runs (one full
run = 278,618 actions, mostly the RL smoke tests) and interactive checks. Estimated from measured per-test
counts and the test runs in the session transcript: point estimate 2.75M, range 2.5-3.1M. The conservative
3.1M is now a ledger role (`research/ledger_adjustments.json`, read by `tools/ledger.py`). The RL smoke tests
now run only with `BC2RL_SMOKE=1`.

Recomputed allowance: 80 - (28.69 + 3.10) - 32.95 (retained M4) - 10.26 (reserve) = **5.0M** (5.35M at the point
estimate). E3 + E1 cost at most 5.13M; that fits at the point estimate and is 0.13M over at the upper bound.
E2 (2.67M) would cut the protected reserve to ~7.5M. Decision: the running batch is stopped when job
`e2-bc-s2` starts, before it executes any environment action (its first evaluation is at BC update 4,000,
~67 s). Reason: budget only. At the time of this decision no E1 or E3 outcome had been read.
Consequence: no third development seed. Replication evidence stays at 2 seeds; E2 is costed in the report.

## 2026-10-31 — Owner decision on M4: option A at 250k and 500k

Owner, verbatim (end of `mac-agentic-engineering/project.md`, harness `ea3d7ad`): "Don't worry about the cap. Do
A but for both 250K as well as 500K." Implemented as `PROTOCOL_FREEZE.md` Amendment 2, written before any
confirmation data. Decisions taken under the delegated scientific judgement:
- **One trajectory, two endpoints.** Each branch runs once to 501,760 and is evaluated at 251,904 and 501,760
  with identical conf_final 64 x 8 + conf_bank 64 x 4 evaluations and the same attempt seeds. This costs less
  than separate 250k and 500k runs, keeps E250 identical in distribution to the frozen design (evaluation does
  not touch training RNG: separate environments and numpy streams, no dropout or batch norm), and pairs the
  endpoints.
- **Multiplicity: one Holm family of 6** (3 primary contrasts x 2 endpoints). Both endpoints are confirmatory;
  separate families would leave the family-wise error rate uncontrolled. Cost: the first-step critical value
  rises from 3.96 (Holm 3) to 4.85 (t, df 4). The A7 planning table had used 2.776 for "80% power"; that was
  optimistic for a Holm claim and is corrected in B4 (detectable effect about 0.065-0.10).
- **Curves on conf_select** (126,976 and 376,832; 64 x 1, bank 64 x 1). conf_final is touched only at the endpoints.
- **BC inside each seed batch** (as A8 proposed), so batch files are fixed before launch and reference
  `@/m4-bc-s<S>`.
- **Budget.** Conservative M4 cost 61.57M (B5); ledger before M4 37.17M including 0.35M of pre-launch tests.
  Projected ~98.7M. Stop and report if the ledger passes 109M or a batch exceeds 1.25 x its estimate.
  Resource limits unchanged (4 cores, 6 GiB, 1 job). Expected wall time ~6-7 h (E1: ~210 s per 501,760-action
  branch).
- More seeds would be the most effective lever for precision; the owner chose 5 seeds (option A), so the
  design is not changed.


**Execution log (M4).**
- `PROTOCOL_FREEZE.md` SHA-256 after Amendment 2 (commit `39c7901`):
  `2037aa145288d0a84f2ca7c6980e8d029a90cea49657a842ab2fd3682bf4691b`.
- Batch `20261031T144145-65447` (data) failed at import: the runner was started with the system Python, which
  has no `gymnasium`. 0 environment actions. Deterministic invocation error; rerun with `.venv/bin/python`
  as batch `20261031T144204-65491` (new ID).
- conf-v1 generated, 0 planner failures; registry SHA-256 `c2652c12...b8be`. Gate (`reports/m4_data_gate.json`)
  **passes**: all training trajectory files, banks_index, the dev bank and every dev-v2 role in layouts.json are
  identical; conf_select, conf_bank, conf_final have 64 layouts per K, disjoint from every dev role and from each
  other; conf_bank bins 32/16/16 per K. Ledger after data: 37.63M.
- Seed batches run through `tools/run_m4.py` (B5 checks; conservative estimate 12.24M per seed).
- Battery guard (owner request, 15:30 EDT): the laptop ran on a 20 W adapter, and the battery drained slowly under
  MPS load. A scratchpad script checked the battery every 5 minutes (interval set by the owner) and would write
  the batch STOP file at the next job start below 25%. It never triggered (minimum 52%); it exited with the
  driver.
- All five seed batches exited normally (105 jobs, 0 failures, 0 retries): 11.06, 11.09, 11.11, 11.08, 11.05M
  actions. Ledger 93.02M. Analysis run unchanged from `c53b63f`; results in FINDINGS F10.

## 2026-10-31 — Post-M4 audit and interpretation revision (owner instruction after M4)

Authority: owner instruction recorded verbatim at the end of `mac-agentic-engineering/project.md` (harness `b37997a`).
No new training. The frozen primary analysis (`tools/analyze_m4.py`, `reports/m4_*`) is unchanged; new analyses are
in `tools/postm4_audit.py` -> `reports/postm4/` and FINDINGS F11; report revised (`reports/REPORT.md`, C1-C9).
- **Provenance** (REPORT C1): Amendment 2 (both endpoints) committed 10:41:34 EDT, before data generation
  (10:42:04-10:43:57) and before the first conf_final outcome (10:52:55); analysis code `c53b63f` at 10:47:03. The
  64 x 8 design was first written in `d928291` (01:37) and approved with Amendment 2.
- **Budget status** recorded as: no numeric hard cap after the owner's 2026-10-31 decision; 109M was a
  self-set submission stop line; no protected reserve was in force for M4 (Amendment 2 replaced A8 without
  restating it). The 80M cap is not reinstated.
- **Bootstrap note**: conf_final is matched across K; the frozen bootstrap resampled K=1/K=3 layouts independently.
  A matched-index sensitivity bootstrap differs by <= 0.0014 at any endpoint; the frozen analysis stands.
- **Multiplicity for the stratum family (post hoc)**: Holm over the 24 arm-vs-00 stratum contrasts and over the 48
  contrasts examined in F10, plus BH-48 and exact sign-flip p. Chosen to match the family actually examined.
- **Accounting fix**: `src/bc2rl/accounting.py` counts every `StageTask.step`; outside the runner it records
  per-process totals in `.mae/unmanaged_actions/` (added by `tools/ledger.py` as measured) and stops after 1M steps.
  The ledger now reports runner-measured, outside-runner measured and outside-runner estimated separately and no
  longer prints the 80M fraction. Tests `tests/test_accounting.py`.
- **Data gate** now also checks pairwise separation among conf_select, conf_bank and conf_final (passes;
  `reports/postm4/data_gate.json`).
- **Follow-up**: R1 (replication of the conditional preservation effect; 8 fresh seeds; ~25.8M) proposed, not run.
- **Harness reproducibility**: the harness repository has no remote; commits `b53f29a` (runner fix used by every
  batch), `366786a`, `ea3d7ad`, `b37997a` are local only. Nothing to push; recorded as a limitation.
- Battery watch (owner instruction): checks every 5 minutes, stops execution below 20%; scratchpad script
  `battery_watch2.py`. Two-hour self-reviews scheduled as a session job.

## 2026-10-31 — R1 approved; Amendment 3
- Owner approved R1 with refinements (verbatim in project.md, harness `4d4fc31`): K=3, 4k/16k, seeds 15-22, arms 00
  and 01 (alpha 0), 501,760 primary, 251,904 descriptive; 128 x 4 final panel; H1/H2 with Holm-2; hard 28.4M budget.
- Data: new roles in a dataset that copies conf-v1 unchanged (`base_dataset`) rather than regenerating every role.
  Why: identical training files by construction and ~0.06M planner replay instead of ~0.5M.
- Admission per batch (all its jobs at their conservative cost), not per job: the runner admits jobs within a
  batch, and reserving every job of the batch up front is the stricter check.
- Canary = the first fork of seed 15 with the preservation arm (exercises the anchor/KL path). It is a design job
  and is kept; its outcome is not read until all seeds finish.
- Support = Holm-adjusted p < 0.05 (seed-level, conditional on the panel). The crossed bootstrap is reported as the
  layout-sampling sensitivity, not as a second gate (owner: bootstrap agreement is a sensitivity check).
- Non-replication thresholds (half and full M4 estimate) and the 0.05 magnitude rule fixed before data.
- RL smoke tests (~0.22M) not rerun: RL code is unchanged except step recording, which the canary checks directly.

## 2026-10-31 21:00 — Self-review 6 corrections (R1 running)
- Arithmetic: Amendment 3 C6 gives the per-seed conservative cost as 3,333,150; the correct sum of its own job
  costs is 3,334,150 (`tools/run_r1.py` uses the job costs, so admission was always computed correctly). Total
  conservative for 8 seeds 26.67M (26,673,200), overall 26.97M: unchanged at the stated precision.
- A quiet deterministic watcher (`tools/watch_batch.py`, 600 s stall threshold, loop bound to the driver's
  verified PID and create time) was armed only at this review, after seed 15. Before that, only the driver's
  exit notification would have reported a failure; a silent stall would not. No stall occurred.
- `pip freeze` recorded in `reports/r1/pip_freeze.txt`. The venv site-packages directory was last modified on
  2026-10-30 16:03, before M4 and R1, so the package set did not change during R1.

## 2026-10-31 21:10 — R1 seed 17 failure: telemetry race (deterministic code defect)
- Classified as a code defect, not a transient infrastructure failure: two writers shared one temporary file.
  Policy: fix, test, new run ID. Seed 17 is rerun (not replaced); no seed is dropped.
- No new canary: the change is confined to the telemetry write; the launch, training and evaluation paths are
  unchanged. The rerun's jobs are checked by the same frozen analysis checks (lineage, hashes, panels, counters).
- Budget after the failure: R1 spent 6,509,776; remaining conservative 6 x 3,334,150 + audit 0.2M gives 26.91M
  <= 28.4M, so completion stays secure.

## 2026-11-01 — R1 complete; scientific execution stopped
- All six rerun batches (seeds 17-22) exited 0, each below its conservative cost. Frozen analysis run once with
  `--check-states`; no exclusions or problems. Final test suite as a runner job (`20261101T025500-19209`): 266
  passed, 3 skipped.
- The frozen rules decide the outcome: H1 and H2 not supported under Holm-2; interpretation cell "inconclusive".
  Nothing was re-analysed with other rules. The unadjusted p and bootstrap are reported as sensitivity only.
- The next-question power figures (R1.9) use R1's observed seed SD. They are planning numbers, not a test, and
  nothing is launched. Per the owner's instruction, no RQ2, no other task family, no further training.

## 2026-11-01 — Owner programme: R2 final replication, E1 cross-panel, E2 anchor components (Amendment 4)
Instruction recorded verbatim in `mac-agentic-engineering/project.md` (harness `000fd83`), with an agent note on
superseded limits. Reconciliation with the evidence and the decisions taken:
- **Scope and why.** M4's K=3/early-BC preservation effect was post hoc; R1 (8 seeds) met neither Holm-2 hypothesis
  but estimated +0.040 with seed SD 0.043. The one open RQ1 question is whether that single effect is real. R2
  tests it alone (early BC only; the checkpoint interaction is dropped, which is not a retroactive R1 success).
  E1 asks whether the M4/R1 differences in baseline and seed SD depend on the evaluation panel. E2 asks which
  anchor component carries the penalty's effect. RQ2 selection, other task families and more replications stay
  out of scope.
- **Budget.** 50M incremental from the corrected ledger 118,670,430 (R1 audit added 128 actions). Unused R1
  allowance not carried. The 109M M4 stop line and the R1 28.4M budget are replaced. No wall-time limit.
  Allocation: R2 <= 38M (may use the reserve for failures), E1 <= 4M, E2 <= 4M (hard), reserve 4M, audit 0.3M.
  Enforcement: `tools/run_program.py` (admission before every batch, committed R2 cost always held; exploratory
  work only after R2 and never from the reserve). Projected conservative total 41.84M + 0.3M: the design fits.
- **Fixed design.** R2: seeds 23-42, K=3, BC to 4k only (constant lr, so the 4k checkpoint is unchanged), arms
  00/01 at alpha 0, 501,760 primary, 251,904 descriptive, fresh roles r2_select/r2_bank/r2_final, eval seed 949000,
  one two-sided paired t-test at 0.05 on R2 data only. Decision cells relative to 0, 0.03 and 0.05 (Amendment 4 D).
  E1: 4 attempts per layout (hard bound 2.90M <= 4M). E2: forks of R1 seeds 15-17, arms 00/01p/01s/01, 251,904
  actions, 32 r1_select layouts x 4 + r1_bank 64 x 2.
- **Choices made here (ordinary engineering, recorded):** E2's development-only evaluation uses r1_select (first
  32 K=3 layouts) and r1_bank, because pi0/probe values exist on those states and these roles were never a
  confirmatory panel; r2 roles are reserved for R2. Interrupted jobs are rerun in full from their last complete
  input checkpoint rather than resumed mid-branch, so every R2 branch record has the same shape (resume stays
  available and is tested on CPU). The interruption drill uses the sleep canary (no environment actions).
- **Interpretation rules.** Training seed is the only replicate. No interim look at paired differences or arm
  means (the analysis is blinded until 20/20). If R2 is inconclusive: report and stop. A positive R2 states the
  condition (K=3, early BC, lambda 0.01, 501,760) and magnitude only; no checkpoint dependence is inferred.
  Synthesis with R1 is descriptive, without a p-value, and discloses adaptive study selection; M4 is excluded.
- **R1 audit outcome** (before any new training; REPORT R1.10): inventory exact (64 endpoint records; "48" was a
  documentation error); statistics reproduce; one accounting correction (+128); interpretations corrected
  (compatible-with wording; limited not zero power; SD reasons not separated; "mainly access" withdrawn for R1 and
  qualified for M4 by the exact decomposition).
- **Monitoring.** Battery watch moved into the repo (`tools/battery_watch.py`, log `.mae/monitor/`), session task
  brnp52lai; two-hour review cron 19ac8cf7 (session-only; recreate in a new session). No duplicate monitor existed
  (checked by process listing before start).
- 2026-11-01 (after the R2 test batch): the lost r2-smoke step record is a deterministic accounting defect. Fixed
  and tested; the actions are added as a conservative estimate (250,000; point 219,343) rather than rerunning the
  smoke tests to measure them (that would spend ~0.22M again). No rerun of the test batch: the fix touches only
  the record path; the final runner test job and the canary exercise it.
- 2026-11-01 (R2 complete): all 20 seeds finished; the frozen analysis was run once on 20/20 (F14). Result
  not supported, interval excludes 0.03. Replication stops as instructed; no further R2 work. E1 and E2 proceed
  as exploratory studies inside their 4M ceilings (admission checked; reserve held).
- 2026-11-01 (deviation, agent error): the runner refused batch xp-r1 at its start because I had left an
  uncommitted file (tools/verify_program.py) in the tree. 0 actions; no run directory was created. The tree
  was cleaned by commit and the remaining batches (xp-r1, comp-s15..17, final-tests) were restarted unchanged
  (driver PID 83489, log `.mae/monitor/explore2.log`). xp-m4 had completed normally (1,088,680 actions).
  Not a failure of the job; no retry counted. New files are now written and committed in one command.
- 2026-11-01 (programme complete): E1, E2 and final tests done; independent verification passed; report section
  P written. Recommendation: close the RQ1 line (REPORT P8). Owned monitors stopped (battery watch 35448 by PID
  and create time; review cron a43d3f65). No further scientific execution.

## 2026-11-01b — Owner programme: A3 anchor allocation, initialization calibration, pilot (Amendment 5)
- **Instruction** recorded verbatim (harness `7ed7285`). It supersedes the Amendment 4 completion stop and the
  REPORT P8 "close the RQ1 line" recommendation as a stop rule. Closed-study verdicts (M4 F10, R1 F12, R2 F14) and
  the E1/E2 records stay unchanged.
- **Budget.** 130M hard, from 158,314,282. Unused Amendment 4 allowance (10.36M) not added. Allocation: ~3M prep,
  ~100M A3, <= 15M calibration + pilot, ~12M protected. Admission rules in Amendment 5 A (`tools/run_program2.py`).
- **Order.** Audit and freeze -> data r3-v1 + gate -> tests -> A3 canary (seed 43) -> seeds 44-66 -> calibration
  (seeds 67-69) -> calibration selection -> pilot (if a variant qualifies) -> final tests -> verification -> synthesis
  and report. A3 runs first because it is the fixed confirmatory study and its completion is protected; calibration
  does not depend on A3 outcomes and is analysed only by its frozen rule.
- **Choices delegated to me** (fixed now, before outcomes): A3 primary endpoint 251,904 (owner); evaluation roles
  a3_select/a3_bank/a3_final (new); eval seed 959000; no curve evaluations (the instruction asks to avoid
  unspecified evaluations); Latin-rotation branch order; arm E as config scale 0.75 on the mixed estimator;
  update-size diagnostics on fixed anchor rows (no RNG); crossed-bootstrap RNG 20261103; calibration evaluation on
  the existing development roles bc_val + dev_bank via the BC job (eval seed 525000; 4 attempts); "room for
  learning" = normal-start P1 <= 0.60 for both K; selection tie-break smaller rho; pilot roles pl_* (new) with
  64 layouts per K; pilot eval seed 989000.
- **Audit outcome.** No implementation defect (Amendment 5 B). Action sampling and minibatch permutation share one
  generator; consumption is arm-invariant without target_kl; kept for comparability, documented.
- **Interpretation corrections** (REPORT P2, P4, P5, P8; FINDINGS F18): "not a power failure" replaced by a
  statement of achieved precision; no noise-share claim from re-evaluation; cohort/panel contrasts with intervals;
  no logical conflict between a positive suffix-only arm and a null mixed arm; P8 superseded as a stop rule.
- **Monitoring.** Battery watch and two-hour review cron restarted at launch (identities in STATE). Batch watcher
  bound to each driver PID and create time.

## 2026-11-01b — Calibration selection and pilot launch (Amendment 5, C–D)

- **Calibration.** Batches 20261101T212138-79498 (s67), 20261101T212609-80088 (s68) and 20261101T212943-80369 (s69).
  All exit codes were 0; the batches used 1,475,592 actions. Results are in `reports/cal/` (`cal_summary.json`,
  `cal_variants.csv`, `access_entry.svg`).
- **Selection (frozen rule, three-seed means).** Only rho 0.2 at 8,000 BC updates qualifies, so it is selected.
  - K1: q 0.962, entry 0.604, P1 0.577.
  - K3: q 0.205, entry 0.604, P1 0.110.
- Every other variant fails the entry target. More prefix sampling raised access and lowered boundary-entry
  competence; 4,000 updates were too few for entry ≥ 0.55.
- **Caveat recorded before the pilot.**
  - Only 1/3 seeds (s69) meets every target on its own. s67 misses K3 entry (0.531) and s68 misses K1 room
    (P1 0.645 > 0.60).
  - K1 P1 0.577 leaves little room for normal-start learning in K1.
  - The rule is applied as frozen: the selection uses the means, and every seed is kept.
- **Pilot.** `make_batches.py --pilot 0.2 8000 --cal-batches <the three IDs>` rewrote experiments/pilot/pilot-s67..69.
  - Each probe forks from its own seed's `cal-bc-p2-s<S>/actor_u8000.pt`.
  - Arms are 00, 10, 01s and 11s for K1 and K3, at 251,904 actions.
  - Conservative cost is about 9.1M (dev total about 10.6M, within the 15M ceiling).
  - Battery was 59% at launch, with an expected drain of about 9 points.
  - The analysis (`tools/analyze_pilot.py`) and the figure code were committed before any pilot run. The pilot is
    exploratory, with no retuning.

## 2026-11-01c — Owner programme: A4 calibrated long-budget study; battery rule 31% (PROTOCOL_FREEZE Amendment 6)

- **Instruction.** Recorded verbatim in project.md (harness `d8155d4`). It supersedes the 2026-11-01b completion state
  and every earlier "below 20%" battery rule; those records are historical. Completed-study verdicts are preserved.
- **Budget.** 70,000,000 actions from ledger total 255,665,568 (= 158,314,282 + 97,351,286; nothing ran in between).
  Earlier unused allowances are not carried over.
- **Plan.**
  - Worst case: about 61.8M. This is a hard bound in which every evaluation attempt runs to its time limit; it is
    64.4M with every limit at 157.
  - Expected: about 59.5M.
  - Protection left: about 8M worst case and about 10.5M expected, close to the requested 8M. The driver admits a
    batch only if the remaining fixed study still fits in the worst case.
- **Delegated design choices.** All were fixed before any A4 run.
  - **Arrival-bank cap: 96 states × 2 attempts.** "Modest" in the instruction's sense, and it keeps the protection
    near 8M. 512 donors × 1 attempt is about 100 expected arrivals at the calibration K3 access of about 0.2.
  - **Arrival-bank sources and assignment:** the three calibration BC policies, round-robin, so no policy is
    selected by outcome.
  - **min_remaining 1:** a state needs time left to be evaluated.
  - **BC evaluation:** one checkpoint, identical to the calibration evaluation, so cohort stability is directly
    comparable with F20 at about 80k actions per seed.
  - **Recovery interval: 100,352 actions** (49 rollouts, about 45 s of training). It bounds lost work. 501,760 is
    also a multiple.
  - **Guard settings:** 15 s polling, a 300 s horizon for the early pause, and escalation after 8 unavailable
    readings.
  - **Eval seeds:** 969000, 969001 and 969002 are new; collection seed 979500.
  - **Branch order:** alternating by seed.
- **Unchanged components.** The task, architecture, reward, horizon, PPO settings, critic preparation, probe, anchor
  data and estimator are unchanged. There are no resets, stronger penalties or new BC variants. Online training is
  K=3 only, and BC stays joint.
- **Interpretation corrections.** Section 3 of the instruction is applied in F23 and REPORT, marked "corrected
  2026-11-01c". No numbers changed.

## 2026-11-01c — A4 data, arrival bank frozen, conservative costs recomputed (before any A4 training)

- **Data.** r4-v1 (batch 20261102T004051-31202, 110,066 actions). The gate passes (`reports/a4/data_gate.json`).
  The entry bank has 128 K=3 states, each with 104 steps remaining.
- **Arrival bank.** data/a4-arrival-v1 (batch 20261102T004138-31283, 71,265 actions), frozen with SHA-256
  15f5f18ad297811e94cc9361d7676503f49a51edc1959be3de8ecef22f729dea.
  - 512 donors run; 100 arrivals (19.5%); 96 kept (cap), so no shortfall. The last kept donor is index 491.
  - Kept by source (s67/s68/s69): 41/32/23. The sources' access differs, so the bank weights s67's arrivals most.
  - Remaining time at arrival: median 65 (range 2-103). The arrival tau has median 78.5. Every kept state carries
    an object at arrival.
  - The bank is not representative of any A4 policy's own arrival distribution.
- **Conservative costs** (hard bounds from the real limits): BC 102,432; probe 183,920; branch 1,339,374;
  endpoint evaluation 112,634.
  - Remaining required work: 59,952,000 conservative (58,998,880 expected).
  - Spent so far: 310,213 (local tests, data and bank).
  - Worst-case total: about 60.56M with the 0.3M audit, so the protection left is about 9.44M.

## 2026-11-02 — A4 complete; recommendation

A4 H1 is not supported: d(1M) = +0.0047 [-0.0152, +0.0246], p 0.63, n = 20. H2 was gated out. The descriptive pattern
is an early benefit (+0.020 at 251,904) followed by catch-up. Decision: suffix-only preservation is not recommended for
final normal-start success. There is no automatic extension and no RQ2 selector. Any further work needs a new owner
instruction; the suggested target is access (q). Spend 55,727,013 of 70M; ledger 311,392,581. Monitors are stopped at
completion. See FINDINGS F24-F25 and REPORT section S.

## 2026-11-02 — Access-focused programme (Amendment 7)

- **Instruction.** Recorded verbatim (harness `936e761`). Starting ledger 311,392,581; new hard budget 70M. The
  battery rule (31% or lower) is unchanged.
- **Corrections.** Section 2 corrections are F26 (within-panel A4 learning; K=3 targets 17/20).
- **Diagnostics before training.**
  - Policies: fixed checkpoints (A4 seeds 70-73, arm 00, probe and final).
  - Layouts: the new d5_trace role.
  - References and certification as in Amendment 7 B.
  - The opportunity rule decides whether the pilot runs.
- **Pilot.** Seeds 90-95; arms 00, B5, C5, D5; shared withdrawal schedule (alpha 0.25 before 376,320 executed
  actions); module-entry banks from reset_donor planner trajectories (module 1 entry = initial donor state); final
  pilot endpoint 501,760 on p5_eval 64 x 4.
- **Gate.** Recorded before any pilot outcome (Amendment 7 D).
- **Confirmation.** Seeds 96-115, A against the selected method, primary 501,760 on c5_final 256 x 2. Certification
  at the primary endpoint only, so the conservative reserve (38.8M) keeps about 9.6M protection worst case.
- **Engineering.**
  - New modules: `bc2rl.suffix_cert`, `bc2rl.trace`, `bc2rl.diag5`.
  - Sampler schedule and module bins in `bc2rl.ppo`.
  - Allocation counters (`track_allocation`): assisted and normal steps by region, and episodes, successes, access
    and end-door counts by start type.
  - Evaluation options `certify_arrivals` and `trace_eval`.
  - Driver `tools/run_program5.py`.
  - Tests: `tests/test_p5.py` and the opt-in `tests/test_p5_smoke.py`.
- **Splits.** Namespace 130 for p5_eval was replaced by 135 before any use, because a raw seed collided with
  r2_select (the registry would have rejected the duplicate layout).
- **Accounting fix.** Subprocess smoke-job records are now mirrored to the parent. The A4 `a4-smoke` gap will be
  measured and added as an adjustment.

## 2026-11-02 — Diagnostics failure (deterministic) and fix

- **Failure.** Batch 20261102T102002-57224 (p5-diag-v1) failed after 20,498 actions. These actions are counted, and
  the records are kept.
- **Cause.** An actual arrival on the final step (0 remaining time) cannot be restored as a snapshot.
- **Fix.** `suffix_cert.certify` classifies such an arrival as impossible without search, because no action remains.
  New test added.
- **Scope.** Only certification. No earlier result used it. Rerun under a new batch ID.

## 2026-11-02 — Diagnostics complete; opportunity rule met; pilot proceeds

- **Batch.** 20261102T102039-57342, 199,824 actions:

  | Role | Actions |
  |---|---|
  | Planner prefixes | 2,588 |
  | Normal starts | 134,271 |
  | Certification replays | 10,019 |
  | Reference 1 | 52,946 |
- **Opportunity rule** (means over the four final checkpoints): 1 - q = 0.328 (rule >= 0.25); reference 1 - P1 =
  +0.311 (rule >= 0.05). Met.
- **Correctness checks clean.** No arrival with a locked door, no "impossible" arrival with a fitting plan, no failed
  feasible replay, and no missing trace. No arrival was unresolved.
- **Descriptive** (`reports/p5/diag/diag.md`). At the final checkpoints, most pre-boundary failures ended in the middle
  module (m1: 0.11-0.41 of attempts). Arrivals certified impossible were 3-6% of attempts. Failed attempts showed many
  toggles on locked doors and no-op actions.

  This is accounting and does not establish which intervention would help. The design is not changed.

## 2026-11-02 — Pilot canary s90 passes engineering checks (no outcome read)

- **Batch.** 20261102T102122-57488: 2,636,241 actions (85% of the conservative 3.11M).
- **Checks** (`tools/analyze_p5.py --engineering 90`): lineage, fork hash and identity, frozen schedules, row counts,
  traces, certification, and step records equal to summary actions. No problems.
- **Allocation.** Executed continuation was 501,760 in every arm. Assisted-step fractions: B 0.077, C 0.159, D 0.161.
- **D phase timing** (from the update counters): module 3 starts ended by 129,024 (boundary 125,440), module 2 from
  129,024 to 253,952, and module 1 to 378,880. The last assisted episode in B ended at 378,880 (withdrawal at 376,320).
  In-progress episodes finished normally.
- Seeds 91-95 follow unchanged.

## 2026-11-02 — Pilot complete; frozen gate selects no method; no confirmation

- **Pilot.** Seeds 90-95 were complete (24 branches) with no problems, retries or exclusions. Batches:
  20261102T103848-59602, 20261102T105600-61618, 20261102T111302-68146, 20261102T112956-69875 and
  20261102T114609-71690, plus canary 20261102T102122-57488.
- **Gate (Amendment 7 D, applied exactly by `tools/analyze_p5.py`; `tools/verify_p5.py` agrees).**

  | Method | Mean P1 − A @501,760 | Positive | Qualifies |
  |---|---|---|---|
  | B | +0.008 | 4/6 | no |
  | C | +0.012 | 4/6 | no |
  | D | +0.028 | 5/6 | no (below 0.05) |

  Checks passed, and the budget fit (protection 16.4M).
- **Decision.** Selected: none. Per section 7, I do not run the confirmation and do not add doses, schedules or
  seeds. The confirmation tools (`tools/make_confirm_p5.py`, `tools/analyze_c5.py`, `tools/verify_c5.py`) stay
  committed but unused.
- **Close.** The final tests passed (308 passed, 10 skipped; batch 20261102T120422-87797). The programme total is
  16,835,872 of 70M. The next question is proposed in F28 and REPORT T8. It needs an owner instruction and has not
  been launched.

## 2026-11-02b — Programme: frozen-policy controller diagnostics (owner instruction 2026-11-02b)

- **Authorization.** At most 2,000,000 executed actions from ledger 328,228,453 (`tools/run_program6.py`). No training,
  reward change, longer horizon, new reset curriculum or new training seed. The reset pilot and its confirmation are
  not reopened.
- **Preserved.**
  - The pilot did not meet its frozen 0.05 rule; seeds 96-115 were correctly unused.
  - D's +0.028 is exploratory (the largest of three) and establishes neither a benefit nor equivalence.
  - Earlier preservation and reset results stay scoped to their procedures, task family and allowances.
  - No cost-effective selector has been established.
- **Position checks (no actions).**
  - The tree was clean at 5d5b31d. No worker was running.
  - The ledger total, 328,228,453, equals the previous start plus 16,835,872.
  - The eight frozen policies load with hashes equal to their run summaries:

    | Policy | Hash prefix |
    |---|---|
    | A4 s70 | 39e5fcd6 |
    | A4 s71 | c320d16c |
    | A4 s72 | 8fd58ae0 |
    | A4 s73 | 0068d0be |
    | pilot s90 | 46739e2a |
    | pilot s91 | cdec2cd0 |
    | pilot s92 | fb985af9 |
    | pilot s93 | 52b909d5 |

    A4 policies are arm 00 at 1,001,472; pilot policies are arm 00 at 501,760.
- **Denominator audit** (`tools/audit_p5_denominators.py` → `reports/p6/audit_p5.md`).
  - All rates were recomputed from pooled counts. No numeric error was found.
  - Labels were corrected:
    - "impossible 3-6%" is a share of attempts (5-10% of arrivals).
    - The pilot "r" column is the mean of per-seed r; pooled r for A is 0.507.
    - "binding", "headroom" and causal readings of loop behaviours are withdrawn.
    - Reference 1 is an assisted reference, not a bound.
  - Marked corrections were inserted into F27, F28 and REPORT T. The original text is kept.
- **Plan** (frozen in Amendment 8 before any outcome on the new panel).
  1. Generate the new disjoint panel d6_ctrl (namespace 136; data r6-v1 on top of r5-v1).
  2. Write the controller module (key-acquisition and door-transition helpers, physical mask, step-indexed common
     random numbers), its tests, the frozen analysis and the independent verifier.
  3. Compute the conservative cost and choose 64 or 32 layouts before outcomes.
  4. Run the tests batch, then an engineering canary on d5_trace layouts (not the new panel).
  5. Run eight evaluation batches (one per policy; 8 conditions × layouts × 2 attempts).
  6. Run the verification replay sample, then the analysis, verification, write-up and final tests.

## 2026-11-02b — Tests batch failed deterministically (test design); fixed; rerun

- **Failure.** Batch 20261102T142856-32688 (p6-tests): 3 failed, 318 passed, 10 skipped; 70,354 actions, counted.
  The three new main-loop tests (budget interruption, pause flag, resume) read `data/r6-v1` through ROOT. The runner
  runs tests in a code snapshot that has no `data/`.
- **Effect.** No controller or analysis code is affected. No outcome had been produced; the canary did not start.
- **Fix.** The tests now write a self-contained two-layout dataset in a temporary directory. The frozen controller,
  analysis and verifier files are unchanged (Amendment 8 L). The tests rerun under a new run ID.

## 2026-11-02b — Tests pass; engineering canary passes (no d6_ctrl outcome read)

- **Tests.** Batch 20261102T143015-32997: 321 passed, 10 skipped; 71,001 actions.
- **Canary.** Batch 20261102T143112-33037: d5_trace 4 layouts × 1 attempt × 8 conditions, a4_s70; 4,133 actions
  (3,373 in episodes, 760 in certification replays). `tools/analyze_p6.py --canary` found no problems:
  - rows and clocks are correct;
  - helpers appear only in their scope and reach their goals;
  - no ineffective prefix action was executed under the mask;
  - every arrival is certified;
  - step records equal the summary.
- **Throughput.** About 5,500 actions/s.
- **Spend.** Programme spend so far is 191,649, including the failed tests batch and local tests.
- **Next.** Run the eight evaluation batches.

## 2026-11-02b — Controller diagnostics complete; recommendation recorded; nothing launched

- **Evaluation.** Eight batches, 20261102T143155-33217 to 20261102T143530-34801: 1,116,009 actions, all complete.
- **Verification.**
  - The replay (20261102T143602-39773, 17,554 actions) re-ran 128 sampled episodes with 0 mismatches.
  - `tools/verify_p6.py` agrees with `tools/analyze_p6.py`.
  - Action totals from the rows, the job summaries and the step records are equal for all 8 jobs.
- **Final tests.** 20261102T143755-40217: 321 passed, 10 skipped. Total spend 1,396,213 of 2,000,000.
- **Result (frozen rules).** key_all, both_mid and both_all give material, consistent relief. door_mid, door_all
  and mask_prefix do not. key_mid is material only in the pilot cohort. key_all exceeds masking by ≥ 0.05 in both
  cohorts.
- **Decision.** Under this authorization nothing more is run. One training study (corrective imitation of the
  module subroutine; REPORT U5) is proposed, with "close the line" as the alternative. It needs an owner instruction.
- **Monitors.** The owned battery guard and the review loop are stopped at completion.

## 2026-11-02c — Owner instruction: corrective prefix imitation study (80M ceiling)

- Instruction recorded verbatim (harness `1efcb5f`). Start ledger 329,624,666. Ceiling 80,000,000; scientific
  batches capped at 72,000,000; 8,000,000 itemised reserve (verification replay, final tests, interruption retries,
  close-out). Earlier allowances do not carry over.
- Monitors: no duplicates found; battery guard restarted (background task, `.mae/monitor/battery_guard.pid`);
  two-hour review cron `14175706`.
- Section 1 record audit done locally (349,457 counted actions; F31). Corrections marked in F29, F30, REPORT U.
- Design frozen as PROTOCOL_FREEZE Amendment 9 before any development outcome:
  - arms A (00), R (R7: demonstration replay), C (C7: corrective labels); coefficient 0.1; matched examples per
    update (R reads C's per-update counts for the same seed);
  - every 4th eligible prefix transition at most; stride adapts upward to keep ≤ 306 queries per update; hard cap
    75,000 queried states per branch, enforced in code;
  - development seeds 116-121, confirmation 122-141 (96-115 stay retired as the closed pilot's reservation);
  - dataset r7-v1 with new roles r7_select, r7_dev, r7_conf (256 × 2), r7_recov;
  - gate and confirmation rules exactly as in the instruction (Amendment 9 G-H).
- Choices made under the instruction (engineering, not tuning):
  - the label set is every shortest first action (uniform target), to avoid arbitrary tie-breaking;
  - the frontier module is the first locked door, a function of the observation;
  - R keeps the original one-hot demonstration actions (ordinary replay); the label-form difference is documented;
  - if R alone is selected, confirmation R uses the rounded mean development C schedule (frozen now);
  - no suffix competence bank in branch evaluations (not required; saves cost); the probe keeps its established
    diagnostics.

## 2026-11-02c — Canary, gate and close-out (Amendment 9)

- **Canary (seed 116).** Health only, no outcomes inspected: 245 updates per arm; C7 69,110 queries (cap not
  reached), 0 observation conflicts; R7 matched C7 exactly; C7 entropy 0.81 vs A 0.41 and single-update KL maxima
  up to 0.34 on prefix states. Judged acceptable under Amendment 9 (no tuning of λ allowed); seeds 117-121 run
  unchanged.
- **Gate.** Applied as frozen: C − A −0.111 (0/6), R − A +0.004 (3/6), C − R −0.115. Neither arm qualifies; the
  independent recomputation agrees. No confirmation batches were written; `make_confirm.py` wrote only the reserve
  batches (evaluation replay, final tests).
- **Reserve spending (itemised).** Evaluation replay 5,160 actions (36 episodes, 0 mismatches); final tests 73,554
  (334 passed, 11 skipped). Total reserve 78,714. Nothing from reserve funded a new hypothesis, dose or seed.
- **Unmanaged actions reconciled.** Ledger total minus batch actions = 577,518 = section 1 audit 349,457 + local
  development and validation runs 228,061 (planner trials, pytest runs, local smoke with mirrored step records).
- **Post hoc observations** (entropy, tie labels, suffix interference) are labelled as candidate explanations in
  F33. A follow-up is proposed only; it needs an owner instruction.
- **Monitors.** Battery guard (background task) and review cron `14175706` stopped at completion.

## 2026-11-02d — Owner instruction: stop training, consolidate, write up, reassess

- Recorded verbatim (harness `d015799`). The corrective-imitation programme had already completed at its gate;
  no checkpointing was needed. No environment actions were executed under this instruction.
- Write-up placed in a new file `reports/WRITEUP.md` rather than a further REPORT section, because REPORT is a
  layered historical record; REPORT's status block points to it. Corrected wording is used throughout.
- Reassessment choice: the unresolved claim named is the representational premise behind every access
  intervention (F32 label agreement 0.647 → 0.675 under direct supervision is the main hint; it is confounded).
  The proposed test is offline and supervised because either outcome changes the next step, and it costs at most
  about 0.5M actions. It is not launched. Suffix completion is noted as a second, later question.
