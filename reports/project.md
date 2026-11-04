# Initial controlled MiniGrid study

## 1. Purpose and authority

Determine when demonstration-state starts, behavior preservation, or their combination improve PPO
after behavior cloning. The central distinction is between **reaching a later stage** and **being
able to finish from specified states within that stage**. Measure both before choosing an intervention.

The latest manuscript in `context/` supplies the broader motivation, definitions and literature.
Read its Introduction, Additional definitions and Prior research. **Disregard Preliminary experiments
entirely.** Do not use those results to choose a task, model, checkpoint, or desired outcome.
The manuscript takes precedence on substantive conflicts. Record its SHA-256 and the resolution of
each conflict in the outer repository's `research/DECISIONS.md` before freezing the protocol.

The manuscript research questions are:

1. **RQ1:** When do demonstration-state starts, behavior preservation, or their combination improve subsequent PPO learning?
2. **RQ2:** Can early measurements predict which option will help on held-out task conditions, more effectively than simpler selection methods after accounting for their cost?

This file specifies the concrete MiniGrid study. The agent implements it in the outer repository.
This delivery contains no task implementation or experimental result. Engineering choices below are
starting defaults, not validated hyperparameters. Adapt them on development data within the stated gates.

**Priority:** establish valid measurements and a credible RQ1 comparison first. RQ2 is conditional on
meaningful variation in intervention benefits and enough independent conditions. Do not force a selector
result from four condition averages. A rigorous null RQ1 result is an acceptable scientific outcome.

## 2. Scope, units, and claims

Use one fully observed, symbolic, discrete-action task family. Use one small feed-forward actor and
a separate critic. Train by BC, run a common PPO probe, then make four matched continuation branches.
All online training rewards are terminal-only. There is no reward shaping, auxiliary task, intrinsic
reward, curriculum adaptation, or privileged planner access during policy evaluation.

For this initial study:

- A **layout** is one complete generated map, including object placements and the episode action limit.
- A **condition** specifies prerequisite length, suffix-family distribution, and a BC checkpoint rule.
  Within it, evaluation averages over a fixed layout/start distribution. In manuscript notation,
  resolve this average into individual task conditions `x` when computing repeated-attempt metrics.
- A **training replicate** is an independently seeded BC training run and its downstream PPO tree.
  Early and extended checkpoints from that BC run stay grouped. Branches are paired, not independent.
- An **attempt** is one independently sampled stochastic evaluation episode under a frozen policy.
  More attempts improve measurement precision; they do not create more training replicates.

Changing prerequisite length changes a task family, not only a scalar difficulty label. Report the
actual optimal action lengths and stage times. Additional BC is a checkpoint comparison along one
training path. It does not isolate initial accuracy, entropy, representation, or competence.

The study can identify intervention effects under its controlled protocol. Associations between early
measurements and those effects do not identify a unique optimization mechanism. A small gridworld
does not establish conclusions about language models, robotics, or arbitrarily long horizons.

## 3. Task construction

### 3.1 A required prefix and a fixed retrieval suffix

Build a small custom MiniGrid environment using its grid, keys, doors and object interactions.
Use UnlockPickup and KeyCorridor as implementation references, not as interchangeable ready-made tasks.
Implement an explicit retrieval-and-delivery suffix so that crossing the boundary is not almost success.

The task is: **complete a sequence of locked-door prerequisites, enter a retrieval area, pick up the
designated object, and carry it to a marked delivery cell.** A normal episode begins before the first
prerequisite. Success requires the correct carried object at the delivery cell after the required boundary.

Use `K=1` and `K=3` required key/door modules in the first comparison. Reserve `K=2` for later validation.
Use a fixed canvas large enough for `K=3`; pad inactive prefix space with inaccessible walls. Fix all
dimensions before confirmation. Do not let a larger input tensor or extra network parameters accompany K.

Each active module requires acquiring a matching key and unlocking its door. Chain modules so the
next required key cannot be reached before its preceding door opens. Use distinct key colors within
a chain; use the same **final** key color for every K. Inventory holds one object. The planner and
policy must handle dropping previous keys. Provide legal drop pockets so the task cannot become
accidentally unsolvable through a required inventory transition. No door, target, or delivery cell
may be reached through an alternate route. Test these invariants with a state-aware planner.

After the last door, all variants enter the same suffix through the same gateway. Match the suffix's
relative map coordinates, target/delivery placement distribution, initial door state, and final-key
inventory convention across K. The suffix includes a short obstacle route, disposal of the final
key, target pickup, and transport to the delivery cell. It must require several decisions and a
nontrivial action sequence. It must not contain another prefix-dependent lock.

Use a fixed target specification, such as a designated colored object, encoded in the symbolic
observation or fixed task definition. If distractor objects are included, they receive no reward.
Do not add language understanding as a requirement. Choose the smallest suffix that provides a
measurable completion range without perception or memory confounds. Tune its complexity only on
development layouts using initial competence and learnability, never the presence of forgetting.

### 3.2 Boundary and success events

Define access as **first entry through the gateway into the suffix after all required doors have
been unlocked**. Let its first crossing time be `tau`. Log the complete crossing state and remaining
action budget. Every accepted success must have crossed this boundary strictly before the episode limit.

Make the crossing event a deterministic function of simulator state and the transition. Keep its
history flag for metrics and success validation. A feed-forward policy must have all behavior-relevant
state in its observation; do not expose an extra hidden progress signal only to one branch.
If the success flag depends on history not inferable from the grid, expose that flag consistently or
change the environment so required door states already certify the prefix. Prefer the latter.

Tests must establish `success => access`, that only the first crossing counts, and that target pickup
alone is not terminal success. Include trajectories that turn back through the gateway or drop/reacquire
objects. Failures, invalid actions and action-limit exhaustion receive zero reward.

### 3.3 Time control without changing the continuation problem

The manuscript requires saved states to retain their **original remaining time**. Never refresh the
clock on a demonstration reset or continuation test. Never silently grant a full new episode horizon.

For each layout, calculate the planner's optimal or verified shortest-prefix length `L_prefix`.
Use `H_x = L_prefix + S_prefix + T_suffix`, with common nonnegative prefix slack `S_prefix` and suffix
allowance `T_suffix`. Start with development candidates near 24 and 80 primitive actions, respectively;
adjust once using measured solution lengths and feasibility, then freeze. These are not fixed facts
about MiniGrid. The planner must verify sufficient time for the complete task in every accepted layout.

This construction gives an expert crossing the boundary approximately the same suffix allowance across K.
It does **not** equalize the time left for a slow learned policy. In normal episodes, prefix delay
uses time that the policy can no longer spend in the suffix. That is part of the task. Record arrival
time, remaining-time distributions, and arrival-state difficulty rather than hiding this difference.

Match the fixed competence-bank distribution of suffix substates and remaining time across K as far as
valid trajectories permit. Retain the true prefix map in each snapshot; whole states cannot be identical
when prefixes differ. Stratify competence by bank progress bin and remaining-time bin. If timing explains
an apparent access-versus-competence result, state that conclusion. A large-slack sensitivity check on
development conditions can test whether deadline pressure dominates. Changing H defines a new condition.

### 3.4 Observations and actions

Use full symbolic grid observations, with no rendered pixels or partial-observation crop. Include object
type, color, door state, agent position/orientation, carried-object identity and remaining time. Scale
time by one common maximum horizon, not a K-specific denominator. Include any variable needed to make
the observation Markov. The policy receives no planner path, optimal action, distance-to-goal reward,
future random seed, or hidden success label.

Retain the standard seven-action MiniGrid interface, including turn, forward, pickup, drop and toggle.
Handle unused actions consistently. Do not introduce planner-derived action masks. Evaluation samples
the categorical policy; report greedy behavior only as an explicitly secondary analysis.

### 3.5 Reward contract

Return exactly one on valid full completion and zero on every other transition. Terminate on success
or the true action deadline. Override MiniGrid's default time-dependent success reward and any base-class
goal reward. Verify logged reward values and returns, not only the wrapper's intended configuration.
Training, assisted-start training and evaluation use this same reward contract.

## 4. Data and split protection

### 4.1 Generate data with a privileged planner

Implement a deterministic reproducible planner over the full symbolic state, including inventory and
door changes. Randomize shortest-path tie-breaking through explicit seeds to avoid only one arbitrary
action order. Validate every demonstration by replaying it through the actual environment API.
The planner may use privileged state to generate demonstrations. The trained policy may not use it.

Begin with about **1,000 successful trajectories total**, balanced over K and selected development suffix
layouts. Increase toward 2,000 only if development evidence shows inadequate coverage. Record failures
of generation and planner search; do not silently reject hard layouts based on learned-policy behavior.
Layouts can be rejected for a prespecified structural impossibility or planner-verified invalidity.

Each transition stores the observation, action, reward, termination flags, complete state snapshot,
remaining time, layout ID, planner seed and stage event. Save the generation configuration, code SHA,
seed lists, schema version, episode counts, action counts and SHA-256 manifest.

BC uses full successful trajectories. Do not train a separate prefix/suffix controller or supply a
stage-specific expert at evaluation. Fit one joint policy on the balanced K=1/3 dataset per independent
training replicate. Its early and extended checkpoints serve both K conditions; do not refit separate
BC actors for each prefix length. Use one dataset and one BC training path per replicate.
Keep the BC dataset fixed across training
replicates initially; this estimates training-seed variation conditional on that dataset.

### 4.2 Separate roles before extracting transitions

Split complete layouts/donor episodes first. Never split adjacent transitions randomly across roles.
Use independent seed namespaces and a machine-checkable registry:

| Role | Allowed use |
|---|---|
| BC train | Supervised fitting only |
| BC validation | Development of checkpoint times and fitting settings; no PPO branch outcomes |
| Normal-start RL train | Rollout layouts; all branches share the same distribution |
| Reset donor bank | Training starts in assistance branches |
| Anchor donor bank | Preservation loss inputs; fixed original-BC distributions are cached here |
| Development diagnostics/evaluation | Engineering checks and hyperparameter selection |
| Confirmation selection/diagnostic bank | Frozen early measurements; no actor or critic fitting |
| Confirmation final evaluation | Endpoint outcomes only; never used for tuning or selection |

Reset and anchor donors are legitimate training data. Keep them disjoint by donor layout/episode for
clean provenance, while matching their intended progress distributions. Competence evaluation snapshots
must be disjoint from both and from BC fitting data. Held-out final normal-start layouts must be distinct
from training and selection layouts. Check canonical state/layout hashes, not only filenames.

Keep individual **layout** generalization separate from held-out **condition-family** generalization.
New random maps from a known generator do not by themselves establish RQ2 transfer to new conditions.

### 4.3 Fixed competence bank

Create the bank using successful **planner** rollouts on independent evaluation donor layouts, not states
selected because a tested policy succeeded. Include nonterminal boundary-entry states and later suffix
states. Use an explicit fixed mixture, initially 50% entry, 25% partway through retrieval, and 25% after
target pickup but before delivery. Prevent near-terminal states from dominating the score. Freeze the
exact sampling rule after development checks and publish per-bin counts.

Start with 64 snapshots per condition, with at least 32 distinct donor layouts. Match suffix placements,
progress bins and original remaining-time bins across K and BC checkpoints. Select corresponding
substates from valid full trajectories; do not fabricate unreachable combinations to obtain a match.
Use the **same** bank, weights and attempt seeds for both BC checkpoints and every PPO branch.

Use two sampled continuation attempts per snapshot for early diagnostics, increasing only through a
predeclared precision rule applied equally to all conditions. Use four per snapshot for final competence
measurement if the profiled budget permits. Record the cost of every executed continuation action.
Keep confidence intervals aware of repeated attempts from the same snapshot and layout.

The bank defines `nu_x`. Its result is competence on that distribution, not competence on every state
the policy might encounter. Report support differences against actual arrival states: position,
orientation, inventory, door state and remaining time. Do not use an empty arrival sample as zero competence.

### 4.4 Restoring states correctly

Version snapshots explicitly. Include the grid and object states, object identities/references, agent
position/direction, carrying relation, task configuration, elapsed action count, task flags and environment
RNG state. Restoration must recreate the same observation and continuation transition semantics.
The policy is feed-forward, so there is no recurrent memory to reset. Policy action-sampling RNGs are
independent across attempts. Restore environment RNG correctly, then apply the prespecified attempt seed
protocol if additional stochasticity is intentionally varied; distinguish these two tests.

Before learning, replay multiple fixed action sequences from uninterrupted and restored trajectories.
Require identical observations, rewards, boundary flags, terminal behavior and time counters through
completion on CPU. Verify random-action continuations as well as successful planner continuations.
Include a test that an almost-expired saved state cannot receive extra time after restoration.

## 5. Model and behavior cloning

Use one actor with categorical embeddings for grid categories. A suitable starting architecture is:
object/color/state embeddings, three 3x3 convolutions with 16/32/32 channels and padding, a flattened
spatial representation, a 128-unit hidden layer, and a seven-action categorical head. Concatenate
orientation, inventory, normalized remaining time and other required scalar state before the hidden
layer. Preserve position information. Use ReLU activations and ordinary stable initialization.

Use a **separate critic network** with the same input information and comparable encoder width, ending
in a scalar value. Do not share actor/critic parameters in the main experiment: value-loss interference
would add an avoidable ambiguity. Freeze the architecture, observation encoding and action interface
across K, BC checkpoints and branches. Record parameter counts and tensor shapes.

BC minimizes mean cross-entropy of expert actions with Adam. Begin near learning rate `3e-4`, batch
size 256, no label smoothing, and no extra entropy loss. Shuffle transitions within the training split.
Document whether the dataset weights trajectories or transitions; use a fixed balanced sampler across K
so long prefixes do not silently dominate. Preserve a held-out supervised loss and rollout validation.

Choose **early** and **extended** update counts from BC development learning curves, before inspecting
PPO branch effects. Use fixed update-count rules across seeds, not per-seed endpoint selection.
Both checkpoints come from the same dataset, initialization, optimizer path and seed. Save the actor,
optimizer, sampler and RNG state. PPO gets its own optimizer; do not carry Adam's BC moments into PPO
unless a later explicit ablation tests that choice. Preserve the early-to-extended training path.

BC feasibility requires some useful later-stage competence and room for further learning. A default
development target is roughly `0.3 <= c_pi0 <= 0.9` in at least one checkpoint and measurable normal-start
access across the selected lengths. These are feasibility ranges, not filters for confirmation seeds.
Prefer a pair of checkpoints that differs behaviorally without both saturating. Do not select on
negative delta-c, a preferred branch winner, or a desired BC rank reversal.

If all policies fail, first inspect observations, planner labels, inventory handling, bank restoration,
and action sampling. Increase data or simplify the smallest relevant task component on development
layouts. If all saturate, adjust prefix difficulty or suffix complexity before freezing. Log all changes.

## 6. PPO procedure and the common probe

Use ordinary **clipped, critic-based PPO with GAE**, not GRPO, DAgger, replay-buffer PPO, or a new algorithm.
Use a well-understood implementation or a small implementation whose returns and probability ratios
can be audited. Preserve sparse rewards. A development starting point is:

| Setting | Initial value or rule |
|---|---|
| Discount | `gamma=1`, finite-horizon completion objective |
| GAE | `lambda=0.95` |
| Policy ratio clip | `0.2` |
| Actor/critic learning rates | Begin near `3e-4`; separate optimizers |
| PPO update epochs | 4 |
| Value coefficient | 0.5 if using a combined reporting convention; no shared parameters |
| Gradient norm clipping | 0.5 |
| Entropy coefficient | Begin at 0.01; common fixed schedule after development |
| Rollout collection | Start with 4 synchronous environments x 128 transitions |
| Minibatch | 128 transitions, adjusted only to divide the rollout batch |
| Evaluation action choice | Stochastic categorical sampling, gradients disabled |

Use remaining time in observations. At the true deadline, the task is over and its bootstrap value
is zero, even if a wrapper calls this `truncated`. A collection-batch boundary is not terminal:
bootstrap the critic and preserve episode state. Respect the final observation in vector autoreset
APIs. Do not compute a target from the next episode's reset observation. GAE must stop across episode
boundaries, including assisted resets.

Advantage normalization is over the rollout batch and is identical across branches. Apply value
targets to the original completion returns, not to the preservation penalty. Keep reward normalization,
value normalization and value clipping off initially; if development justifies one, document and freeze
it across branches. Fit the critic without privileged features.

### Critic check before actor updates

Collect normal-start trajectories with each frozen BC actor. Fit the critic briefly using actual
finite-horizon returns on development data, and inspect held-out calibration/MSE across visited stages
and remaining-time bins. A pilot of about 10,000–20,000 actions is sufficient to start this check;
increase only with evidence. This is a shared preprocessing cost and does not supply later-stage
success labels unavailable in ordinary rollouts. If no suffix is visited, report that calibration
there is unknown. A constant target can make explained variance undefined or uninformative.

Start PPO after verifying finite losses, correct terminal handling, sensible probability ratios,
nonzero learning signal where successes occur, and a critic that is not numerically unstable.
For unexplained deterioration, use a development-only sensitivity check with improved critic fitting
or smaller actor updates. Do not attribute decline to lack of stage practice while ignoring an obvious
value-estimation or optimization defect. Diagnostics establish changed behavior, not its unique cause.

### Probe and branching

Run a fixed ordinary-PPO probe, initially **50,000 environment actions** per condition/checkpoint/seed.
Measure initial and post-probe normal-start access and fixed-bank competence using independent evaluation
episodes. Use one probe allowance, rollout configuration and checkpoint time across the comparison.
Do not stop the probe at a visually attractive loss or forgetting event.

Copy the complete post-probe state into all four branches: actor, critic, both optimizers, schedulers,
RNGs, environment sampler state and interaction counters. Fork at a clean rollout/update boundary so
there are no partly consumed advantages. The immutable preservation reference is **pi0**, the original
BC checkpoint, not the post-probe actor. Record hashes to verify exact equality at the fork.

Use branch-specific reproducible random streams derived from a shared replicate seed. Couple layout
and evaluation schedules where valid; do not force identical trajectories after actions diverge.
Run order should be randomized or balanced across branches to reduce thermal/time-of-day confounds.

## 7. Four interventions: one factorial comparison

Let `a` indicate demonstration-state starts and `b` indicate behavior preservation:

| Arm | Episode-start distribution | Actor loss addition |
|---|---|---|
| `00` | Normal starts | None |
| `10` | Fixed normal/demo mixture | None |
| `01` | Normal starts | Original-BC forward KL on anchors |
| `11` | Identical normal/demo mixture | Identical forward KL |

**Assisted starts.** At each episode reset, independently choose a demonstration-state reset with fixed
probability `alpha`. Start development at `alpha=0.5`. Draw from the frozen reset bank using the same
progress mixture for arms 10 and 11. Restore original time and terminal conditions. Do not refresh
the clock, insert expert actions, change rewards, or adapt the reset fraction using outcomes in the
main study. An annealed schedule is a later explicit condition, not an unrecorded implementation detail.

**Preservation.** Add to the minimized actor loss:

`lambda_KL * mean_s KL(pi0(.|s) || pi_theta(.|s)), s drawn from D_anchor`.

Compute the exact categorical KL over all seven actions, with stable log-softmax calculations. Cache
the original BC action distribution on the fixed anchor bank in inference mode. Sample an anchor batch
of 128 per actor minibatch update, without changing the on-policy minibatch or update count. Include
all required stages in the bank, with a fixed deliberate emphasis on suffix states; begin with 75%
suffix and 25% prefix. Publish per-stage weights. The competence bank has separate donors and weights.
Do not apply the penalty to the critic or replace it with action cross-entropy without accounting for
the omitted constant and reference distribution. Log KL magnitude and its gradient contribution.

Tune `alpha` and `lambda_KL` only on development conditions. Keep this small: first compare alpha 0.25/0.5
and KL strengths 0.01/0.1/1.0, expanding only after showing these scales fail numerically or behaviorally.
Use a tiny two-seed screen; then freeze a **single** alpha and KL strength across K and BC checkpoints.
Do not give each condition an oracle-tuned intervention. Preserve enough budget for replication.

All branches receive the same subsequent **environment-action allowance**, PPO rollout size, update
epochs, minibatches and schedules. Assisted starts cause more or shorter episodes; count executed
actions, not episodes. A restored state is not counted as executing its skipped prefix, but record
reset overhead and demonstration-generation costs separately. Additional KL computation is real compute
cost and must be reported. This is an interaction-matched main comparison, not automatically a compute-matched one.

Evaluate from ordinary starts. Assisted-start training success is a diagnostic only. Resets affect
state access, reward exposure and suffix practice together. A gain from resets does not isolate exploration.

## 8. Measurements and analysis

### 8.1 Distinguish the three quantities

For each frozen policy and task condition, estimate:

| Quantity | Definition | Sampling source |
|---|---|---|
| `p_pi(x)` | Probability of complete success | Normal starts |
| `q_pi(x)` | Probability of first crossing before the deadline | Same normal-start attempts |
| `c_pi(x; nu_x)` | Completion probability from the fixed nonterminal suffix bank | Independent saved-state continuations |
| `delta_c` | `c_probe - c_pi0` on that same bank | Paired pre/post measurements |

Low initial c indicates a weak initial suffix policy. Negative delta-c indicates deterioration on
the specified bank during the probe. Low q indicates rare access from normal starts. These may coexist.
Never estimate competence solely from successful normal episodes. Never replace a missing conditional
arrival statistic with zero. Report uncertainty near floors and ceilings.

Because the boundary is necessary,
`p = q * E[v_pi(s) | s drawn from the policy's first-crossing distribution]`.
The fixed bank generally has a different distribution. **Do not claim `p = q*c`.** Conditional success
after actual arrival, when estimable, is a useful separate descriptive statistic. Changing its value
can reflect both changed arrival states and changed continuation behavior.

Measure actual suffix visitation, stage occupancy, number of successful training episodes, arrival-time
quantiles, timeouts, action entropy, exact anchor KL, PPO approximate KL/clip fraction, critic error,
gradient norms and actor updates. These help diagnose implementations and competing explanations.
Do not turn all logged quantities into post-hoc primary hypotheses.

### 8.2 Primary and secondary endpoints

The primary RQ1 outcome `Y_ab` is final **normal-start mean single-attempt success P1** at a fixed
post-probe interaction budget. Use equal prespecified weights across K and BC checkpoints, and publish
each stratum. No best-checkpoint selection. Development curves may guide the frozen endpoint; final
learning curves are descriptive unless a curve statistic was also prespecified.

Report paired branch contrasts for each condition and seed:

- Reset benefit: `Y10 - Y00`.
- Preservation benefit: `Y01 - Y00`.
- Combined benefit: `Y11 - Y00`.
- Interaction: `(Y11 - Y01) - (Y10 - Y00)`.
- Combined versus each single arm: `Y11 - Y10` and `Y11 - Y01`.

A positive interaction is not proof that both interventions are necessary. A positive combined-versus-00
contrast alone does not show superiority to either single arm. State the relevant comparison explicitly.

Secondary outcomes include fixed-bank competence and repeated-attempt coverage/reliability at `k=4`.
For each exact evaluation layout/start condition with `n` independent attempts and `z` successes, use:

- `P1_hat = z/n`.
- `Ck_hat = 1 - choose(n-z,k)/choose(n,k)`.
- `Rk_hat = choose(z,k)/choose(n,k)`.

Use zero for `choose(a,k)` when `a<k`. Average per-task estimates with fixed weights. Do not plug the
overall mean success into the nonlinear formulas. Do not treat overlapping attempt subsets as independent.
Do not describe repeated-attempt reliability as adversarial robustness. Omit unsupported large-k claims.

### 8.3 Evaluation scale and uncertainty

Development diagnostics begin with 32 layouts x 4 normal-start attempts, and the competence bank above.
Final normal-start evaluation begins with **32 held-out layouts x 16 attempts per arm/condition/seed**.
Use independent stochastic attempts and common layout/seed schedules across policies. Freeze sample
sizes before examining final outcomes. Increase by a prespecified precision rule using development
variance, not because a confidence interval misses a preferred conclusion.

Target **five independent BC/PPO training replicates** for the confirmatory core. Show every paired seed
contrast and an interval across replicates. Checkpoints from the same BC run are nested in that replicate.
Use a cluster/hierarchical bootstrap over independent replicates and layouts, preserving branch pairs
and checkpoint grouping, or a justified equivalent. Label episode-only intervals separately. With five
seeds, intervals remain uncertain; many test episodes cannot fix this. Three seeds are a pilot, not a
silent substitute for confirmation. If compute prevents five, report the narrower evidence honestly.

Set a practical effect threshold before confirmation; begin with **five percentage points in P1** as
the development planning value. Claim a useful improvement only with effect size and uncertainty, not
just the sign of an average. A wide interval containing zero is inconclusive, not evidence of no effect.
Do not claim equivalence without precision and an explicit equivalence margin.

For small numbers of conditions, show transparent scatterplots of q, c0 and delta-c against paired
intervention benefits. Do not fit a large predictor or multiply significance tests across metrics.
Report whether a competence feature adds information beyond initial p and q, including its uncertainty.

## 9. Staged execution and decision gates

The agent owns implementation details and ordinary debugging. Preserve the frozen scientific contract.
Keep a dated record of changes and all exploratory runs. Initial resource use is local only; no Modal,
Babel, paid service or remote experiment is authorized by this specification.

| Milestone | Work and budget guidance | Exit criterion |
|---|---|---|
| M0: host and correctness | Profile actual Mac; confirm limits; synthetic process/resource canaries; task/planner/restore/return tests | Resource response and task invariants verified; no leaked workers or split overlap |
| M1: throughput and BC | CPU/MPS benchmark; ~1,000 demonstrations; small BC curve on development layouts | Measurable access and suffix competence, headroom, stable learning and valid banks |
| M2: PPO canary | One K/checkpoint/seed; 50k-action probe and short four-arm continuation | Finite updates, exact forks, reward/time/GAE checks, meaningful final evaluation |
| M3: development comparison | K=1/3 x two checkpoints, two seeds; begin at 250k continuation actions; small intervention screen | Freeze task, checkpoints, PPO settings, alpha, KL, probe, endpoint, splits and analysis |
| M4: core confirmation | K=1/3 x two checkpoints x five seeds x four arms; target 500k continuation actions per branch | Complete paired endpoints and audit on untouched confirmation layouts |
| M5: conditional RQ2 | Only after M4 supports useful heterogeneous effects and expansion fits the remaining budget | Independent held-out-condition selection test, or explicit justified deferral |

The 500k endpoint is a starting planning value, not a guaranteed learning time. Profile and inspect
development learning curves before freezing. If 500k leaves every arm flat for known optimization
reasons, fix the cause or choose a feasible common endpoint before M4. Do not move it after inspecting
confirmation outcomes. A stable null result under a validated setup is not a reason to keep searching.

The full M4 core contains 80 continuation branches and about **40 million continuation actions**,
plus probes, BC, diagnostics and final evaluation. Pilot first; do not launch that workload blindly.
At M1 and M3, extrapolate measured sustained steps/second, updates/second, memory and thermal behavior.
Give an estimated wall-time range for the full matrix. Reduce development sweeps before reducing
independent replication. If the full matrix exceeds the owner-confirmed cumulative time budget,
complete a clearly labeled smaller pilot and report what prevents confirmation. Do not silently exceed it.

Keep the first study within **80 million total executed environment actions** and the owner's cumulative
active experiment-hour allowance (suggested initial ceiling: 48 hours), whichever binds first. Include
planner replay, diagnostics, failed runs, tuning and evaluation in the campaign ledger; count BC updates
and planner computation separately. Record actual batch wall times; parallel jobs share machine time
but still consume their own environment actions. Reserve at least 20% of the estimated remaining budget
for confirmation evaluation, independent audit and failures. Stop before overspending. Any expansion
beyond these bounds requires an explicit owner amendment.

### When a development gate fails

- **q near zero everywhere:** inspect legal reachability, BC prefix coverage and horizon. First try a shorter prefix
  or better demonstrations. Do not immediately add rewards or discard failing seeds.
- **c near zero everywhere:** inspect restoration, observation sufficiency and suffix BC coverage. A preservation
  experiment is uninformative if there is no competence to preserve.
- **p near one everywhere:** reduce saturation through a prespecified development adjustment. Keep a nontrivial
  suffix and genuine prerequisite sequence.
- **PPO receives almost no positive returns:** check the critic and implementation, then assess whether normal-start
  learning is feasible within budget. Assisted resets may legitimately help, but all-zero arms alone do not
  establish a fine-grained selector.
- **No competence decline:** report it. Preservation may still regularize training or constrain it; do not manufacture
  forgetting or rename low initial competence as deterioration.
- **All arms similar:** report the uncertainty and stop RQ2 unless development evidence supports a real expansion.
- **One arm dominates everywhere:** that supports a fixed intervention under this regime and weakens the selection motivation.

## 10. RQ2: gated selection study with honest costs

The core two-length/two-checkpoint experiment is primarily RQ1. It cannot by itself support a reliable
general-purpose selector. M5 requires additional independent condition variation, not extra attempts
on the same four averages. Expand only if the core exhibits reproducible differences large enough
to matter and profiling shows sufficient budget.

### Condition expansion and held-out outcomes

Predefine several suffix-geometry families with the **same objective and observation/action contract**.
Within each family, cross prerequisite length while holding its suffix distribution fixed. A concrete
expanded target is 3 lengths x 4 suffix families = 12 layout-condition groups, each with both BC
checkpoints. Use two entire suffix families for selector development and two for held-out testing;
do not split checkpoints or seeds from the same group across fit/test. This is a small transfer test,
not evidence about an arbitrary task population. Make the transfer axis explicit.

This expanded study is not part of the minimum core confirmation. At five seeds and 500k actions,
it exceeds the initial campaign cap even before selection baselines. Normally deliver a costed
follow-up proposal after M4. Proceed within the initial budget only if development evidence already
validated a substantially shorter frozen endpoint and the complete comparison still fits. Do not
reduce replication or change the endpoint after opening held-out outcomes to make M5 appear affordable.

Collect development intervention outcomes for fitting and freeze the feature transform, selection rule,
hyperparameters, fallback and cost allocation before opening held-out branch outcomes. Held-out condition
diagnostics are allowed inputs at deployment; held-out outcome labels are not. Reserve fresh final
evaluation layouts within each held-out condition. If affordable condition diversity is inadequate,
defer RQ2 and deliver the RQ1 evidence. Do not compress the expanded plan into unreplicated runs merely
to claim completion.

### A simple selector and required alternatives

Prefer an interpretable depth-2 decision tree or a prespecified small threshold rule. Candidate features
are early p, q, c0, post-probe c and delta-c; fit thresholds only on development condition groups.
Use grouped development validation, keeping all seeds and both BC checkpoints from each group together.
Account for noisy delta-c. Prespecify a fallback to the best fixed arm on development data when a
required measurement is unavailable or too imprecise. Do not give a missing value a convenient sign.

Compare against **each** fixed arm, the best fixed arm selected on development data, a matched-complexity
selector using only overall success and stage access, and short trials of all four arms. Identify whether
competence/decline features improve decisions beyond p/q. All methods use the same BC and PPO-probe
procedure. Do not select feature sets or a final model from held-out performance.

### Cost accounting is an experiment, not a correction to a plot

Give every method the same total post-probe allowance `B` of executed environment actions. For methods
using them, **pre-probe competence/access measurements are also charged against B**, despite occurring
earlier in time. The common BC preparation and probe costs are reported separately. Charge method-specific
critic warmup or extra measurements as appropriate; do not hide unequal preparation in a common-cost label.

For a diagnostic selector, reserve `D` actions for all pre/post-probe measurements and selection evaluation.
Continue its selected arm for `B-D` actions. Measure actual executed lengths, enforce diagnostic action
ceilings, and freeze the fallback if the ceiling prevents enough samples. Offline selection computation,
snapshot generation and cached BC distribution computation are reported as compute, even without actions.

For short trials, fork the common post-probe state into four arms. Spend `t` training actions on each
and `E` actions across independent **selection** evaluations, with fixed allocations. Choose the highest
selection P1, using a frozen tie-break. Continue the selected **trial checkpoint** for `B-4t-E` more actions.
Its optimizer, RNG and training state must resume from that trial. The chosen arm therefore receives
`t + B-4t-E` training actions; the other `3t` and all selection episodes remain charged. Do not give
the winner a new full continuation budget. Require `B >= 4t+E` before launching.

A fixed arm can spend its full B on continuation because it does not need diagnostics or trials.
All methods then receive the same separate final evaluation, which cannot change the choice or
training. Report interactions and wall/CPU/MPS compute independently; equal actions do not imply equal
compute when KL or model-selection overhead differs.

**RQ1 endpoints cannot simply be reused for RQ2** if their chosen branches had longer training.
Run the cost-adjusted continuation endpoints or frozen checkpoints at the required exact action counts.
In a research benchmark, unselected counterfactual branches may be run to estimate intervention effects;
report that total study cost separately from the simulated deployment cost of each selector. Counterfactual
outcomes must remain unavailable to the selector. A hindsight best arm is an oracle reference, not a baseline.

The RQ2 primary outcome is final normal-start P1 at equal B, with paired training replicates and held-out
condition groups. Report regret to the hindsight best arm only as secondary, with its uncertainty.
A useful selector must outperform sensible fixed or trial alternatives enough to justify measurement
cost. Accurate branch classification without better final performance is not the target.

## 11. Local execution and resource safeguards

### Host profiling and backend choice

Do not assume the claimed Apple M5/24 GB specification has been measured here. Profile the actual
machine, OS, architecture, physical/logical cores, unified memory, free disk, swap and PyTorch/MPS
availability. Confirm owner CPU and memory budgets before training, data generation or heavy tests.
Keep the machine responsive and leave headroom for the coding agent and operating system.

Benchmark the **same implementation and configuration** on CPU and MPS: forward/backward updates,
rollouts, end-to-end steps/second, peak/conservative memory and checkpoint latency. Synchronize MPS for
timing. Use a short warmup followed by a sustained 10–15 minute check for thermal effects; the Air
is passively cooled. Use small vector batches first. Environment Python overhead and device transfers
can dominate a small CNN. Choose the measured faster stable backend; MPS is an option, not a requirement.

Prefer one backend for confirmatory comparisons. Check selected CPU/MPS runs for numerical or implementation
differences before any pooling. Fix PyTorch, MiniGrid, Gymnasium and NumPy versions in a resolved lock;
record deterministic settings and unsupported operators. Keep MPS fallback disabled initially. If an
operator requires a fallback, change implementation or document explicit fallback and reprofile.
Do not promise bitwise reproducibility on MPS.

### Resource canaries and polling

Use the supplied runner for heavy work. Before the first experiment family, write tiny **non-scientific**
canaries in the outer repository to verify CPU throttling, memory-stop response, wall timeout, owner stop,
missing/stale MPS telemetry, and cleanup of CPU children. Test an intentionally low memory limit using
a small allocation, not a system-threatening allocation. Restore owner limits afterwards. Benchmark
parallel CPU jobs against the same aggregate budget; begin scientific MPS runs sequentially.

Write a token-efficient progress watcher for each experiment family. Require atomic telemetry at least
every 10 seconds, progress updates at predictable action/update intervals, a completion summary and
checkpoint paths. During long BC/evaluation/checkpoint phases, keep resource telemetry alive. A simple
background thread may read process-wide MPS allocator counters if tested safe; it must not perform model
operations. The deterministic watcher reports meaningful state changes and stalls; it does not retry,
retune, or change scientific decisions.

The memory guard conservatively combines aggregate RSS and MPS driver allocation, which may overlap.
Keep the individual readings so false pressure triggers can be understood. Polling cannot prevent
all transient peaks; do not label it hard enforcement. Reserve model/buffer memory conservatively and
avoid multiple MPS-owning processes. Explicitly set PyTorch thread counts and use spawn for CPU workers.
Account for all parallel experiments under one supervisor. Never bypass limits with an untracked shell pool.

### Tracking and resumability

Every run needs a unique immutable ID and a committed resolved config. Log:

- Purpose, milestone, exploratory/confirmatory status, hypothesis, condition and split IDs.
- Outer and harness SHAs, manuscript hash, package lock, Python/backend/hardware profile.
- Dataset/bank hashes, all RNG seeds, checkpoint lineage, branch and exact fork hash.
- Environment actions by training/probe/diagnostic/selection/final-evaluation role; BC/actor/critic updates.
- Episode/attempt/layout counts, sampled-policy metrics, raw per-attempt outcomes and failure reasons.
- Wall time, throughput, CPU and memory sensors, MPS telemetry, resource stops and actual parallelism.

Write `config.resolved.json`, `metrics.jsonl`, `attempts.csv` or equivalent typed records, `summary.json`,
resource telemetry and atomic checkpoints under `MAE_RUN_DIR`. Keep an index in `reports/REPORT.md` linking
the evidence. Checkpoint actor/critic/optimizers/schedules, sampler/environment states, counters and RNGs.
If exact mid-rollout restoration is impractical, checkpoint at clean update boundaries and report any
replayed/lost work. Lost actions still count toward consumed compute; do not silently count only retained
updates. Save periodically and on a bounded cooperative SIGTERM handler. Never overwrite a failed run.

Use unique paths for resumes and record parent run IDs. A resource kill or backend crash is an execution
failure, not a policy failure. A valid episode timeout is a policy failure. Distinguish these in denominators.
Fixed final evaluation includes all valid episodes; exclusions require a documented implementation defect,
with the same correction applied to every affected arm. Do not rerun seeds until outcomes improve.

## 12. Confirmation freeze, reporting and interpretation

Before M4, commit `research/PROTOCOL_FREEZE.md` containing the manuscript mapping, task generator and
reward/time/boundary contract, splits, bank weights, model, BC checkpoint rules, PPO settings, intervention
strengths, seed list, budgets, endpoint, sample sizes, weighting, contrasts, uncertainty method and failure
policy. Hash the manifest. Generate or reveal confirmation outcomes only after this freeze. No automated
inspection of final metrics may feed development tuning. If a correctness defect forces a change, version
the protocol, identify affected runs, and start a fresh confirmation batch. Retain the invalidated record.

Maintain **one consolidated `reports/REPORT.md`**. Use linked appendices for implementation details and
milestone audits, not separate competing final narratives. Keep the main report concrete:

1. Exact question and tested regime, including what was frozen and what was tuned.
2. Feasibility, correctness tests, resource profile and measured campaign cost.
3. Initial/post-probe p, q and c with uncertainty; arrival-state/time checks.
4. Four-arm final normal-start P1 and paired intervention contrasts, including every seed.
5. Secondary coverage/reliability and competence results, clearly labeled.
6. RQ2 equal-cost held-out results, or an explicit evidence-based reason for deferral.
7. Limitations, competing explanations and the next discriminating experiment.

Generate precise SVG/PDF figures reproducibly from saved data: a task/boundary schematic only if it
clarifies the implemented layout; p/q/c before and after the probe; paired intervention-effect plots;
and fixed-budget learning curves where useful. Use numerical axes, denominators and uncertainty. Avoid
decorative diagrams or a separate plot for every logged quantity. Ship the plotting commands and source
CSV. Verify reward histograms, sample metric recomputation, split hashes and at least one fork independently.

Interpret outcomes conservatively:

| Observation | Supported conclusion | Not established |
|---|---|---|
| Low q and high fixed-bank c | Policy rarely reaches the stage while succeeding from those saved states | All naturally reached suffix states are easy, or low access is the sole cause |
| Negative delta-c | Competence declined on the common bank during the probe | Unique mechanism, broad skill erasure, or inevitable PPO forgetting |
| Resets improve final P1 | This altered training-start distribution helps at the tested budget | Exploration alone explains the gain |
| Preservation improves final P1 | This BC-reference constraint helps under the tested setup | Initial competence loss was the only relevant bottleneck |
| Combined beats both single arms | Joint use is beneficial here | Both components are universally necessary |
| One fixed arm wins consistently | A simple fixed strategy is strong in this regime | Diagnostics necessarily add practical value |
| Diagnostics predict branch labels but lose at equal cost | Measurements can be informative yet uneconomic | A successful RQ2 selector |

The desired scientific progression is **validated separation of access and competence -> replicated
intervention effects -> conditional test of useful selection**. Proceed through those gates even if
the evidence supports a simpler conclusion than the motivating hypothesis.

## 13. Implementation references and owner amendments

Read the manuscript literature discussion before making novelty claims. It identifies preservation,
reverse curricula, JSRL/RFCL, critic instability, uncertainty and selection-cost precedents. This project
does not reproduce all those algorithms. Its core contribution must be the controlled intervention
evidence and, if supported, cost-effective selection.

Use primary implementation references and record the exact versions actually installed:

- [MiniGrid source and environments](https://github.com/Farama-Foundation/Minigrid)
- [MiniGrid wrappers](https://minigrid.farama.org/api/wrappers/)
- [Gymnasium vector API](https://gymnasium.farama.org/api/vector/)
- [PPO paper](https://arxiv.org/abs/1707.06347)
- [PyTorch MPS API](https://docs.pytorch.org/docs/stable/mps.html)
- [Slurm harness reference](https://github.com/FlightVin/slurm-agentic-engineering), inspected at `6fe1d6f8cac6db7fe0ec8a79964998dc66aebff2`

**Owner amendment, 2026-10-30:** support native MPS when profiling shows a benefit. Use soft resource
limits with token-efficient polling scripts written by the agent when starting experiment families.
This supersedes the earlier Docker/CPU-only proposal. Keep all useful reproducibility, writing,
tracking and report-consolidation invariants. Implement the lightweight harness and specification only
in this delivery; the subsequent local agent implements and runs the science.

---

**Owner amendment, 2026-10-31: expanded, bounded development campaign before M4.** Recorded verbatim.

Continue autonomously with an expanded, bounded development campaign before M4. Your goal is to determine what the current results mean, whether important effects emerge after 250k training actions, and which confirmation design would provide the strongest evidence within budget.

Think like a senior research scientist and engineer. Prioritize experiments that distinguish plausible explanations. Complete useful work without routine clarification. Preserve null results and failed experiments.

Do not generate confirmation data or start M4. Return an evidence-based recommendation and wait for my approval before confirmation.

## **1\. Authority, scope, and limits**

Read and follow `mac-agentic-engineering/agent.md`, `project.md`, the manuscript excluding Preliminary experiments, and the current research records. The manuscript remains the scientific authority.

This instruction expands development beyond the existing freeze. Preserve that freeze and document all subsequent changes as dated amendments.

You may inspect code, fix defects, improve analysis, evaluate saved checkpoints, resume development training, run justified development controls, and make local commits.

Use these limits:

* At most four hours of active work for this campaign.  
* At most 8M additional executed environment actions, including training, diagnostics, evaluation, generation, failed runs, and retries.  
* The existing 80M total campaign cap remains binding.  
* Retain the owner-confirmed four CPU cores, 6 GiB memory, and one concurrent experiment job.  
* Protect enough budget to complete the proposed M4 and its audit. The 8M allowance is a ceiling, not permission to consume confirmation capacity.  
* Do not increase resource limits, purchase compute, or expand to other domains.

Before starting new training, calculate the affordable development allowance:

remaining campaign capacity  
− conservative cost of the retained M4 design  
− protected audit/failure reserve.

Use the smaller of this allowance and 8M. Do not shrink the reserve automatically as development consumes actions. The previous reserve was approximately 10.3M actions; reconcile its intended use explicitly.

If these constraints prevent an experiment, complete lower-cost work and report the tradeoff. Do not repeatedly ask me to choose routine details.

## **2\. Complete the pre-confirmation audit first**

Perform the previously requested audit before interpreting new training results. Use raw artifacts and source code, rather than treating reports as verified evidence.

Reconcile these specific issues:

* The selected M3 contrasts reproduce using the original arm-00 runs.  
* `m3_branches.csv` contains 64 branch rows, including eight original arm-00 runs and eight repeats. Their `variant` fields are blank. Distinguish jobs, probes, branches, and repeats.  
* Ordinary PPO improves over pi0 and the probe in all eight original M3 forks, rather than seven.  
* The supplied ledger totals 28,689,024 actions. Check completeness, including stopped and failed work.  
* Remove the unsupported attribution of repeat variation to “GPU nondeterminism alone,” and the claimed variance decomposition.  
* Correct the independence assumptions behind the stated precision and power.  
* Separate early normal-start diagnostics from the final confirmation layouts.

Create an explicit analysis manifest mapping fork, original baseline, repeat, intervention, alpha, lambda, source commit, and checkpoint hash. Never choose rows by order or silently overwrite duplicates.

Independently recompute selected-arm and repeat metrics from raw attempts. Preserve correction history. Verify whether the intervention-selection rule was genuinely recorded before its outcomes were examined.

Audit the scientific contract:

* Binary terminal reward and necessary boundary crossing.  
* Original remaining time on restored states.  
* Full observation and valid inventory/state restoration.  
* Matched suffix distributions across K.  
* Disjoint BC, reset, anchor, diagnostic, and evaluation roles.  
* One BC training path per replicate with fixed checkpoints.  
* Complete actor/critic/optimizer/scheduler/RNG state at each fork.  
* Preservation toward the original BC checkpoint.  
* Correct PPO ratios, GAE, termination, and bootstrapping.  
* Matched executed-action budgets and optimization settings.

Resolve correctness defects before new scientific comparisons. If a defect invalidates existing checkpoints or conclusions, identify exactly what is affected. Do not resume invalid artifacts merely to save compute.

## **3\. Build a compact information map from existing results**

Before selecting new runs, produce a condition-level table containing:

* Initial and post-probe p, q, c, and delta-c.  
* Final p, q, c for the selected four arms.  
* Arrival-time and remaining-time distributions.  
* Conditional success after actual arrival, where estimable.  
* Training successes, suffix visitation, and assisted-start counts.  
* Anchor KL, PPO update magnitude, and critic calibration.  
* Original-versus-repeat variation.  
* Available intermediate checkpoints and their exact action counts.

Separate these possible regimes:

1. Low access with useful initial suffix competence.  
2. Low initial suffix competence.  
3. Measured competence deterioration.  
4. Deadline or arrival-state mismatch.  
5. Unstable or ineffective optimization.  
6. Saturation or insufficient learning time.

Do not assign a regime confidently when the measurements are too noisy.

Verify intervention activity. Report realized reset fractions and sampled states. Determine whether lambda=0.01 materially changes anchor KL or actor gradients compared with arm 00\.

Use this table to select experiments by expected information gain. Record each experiment’s question, comparison, expected discrimination, cost, and stopping rule before launching it.

## **4\. Extend the selected four-arm comparison beyond 250k**

Longer training is the first training priority after correctness.

Start with the extended-BC checkpoint because it provides substantial initial suffix competence. Use both K=1 and K=3 and both existing development seeds. This supplies a high-access comparison and a lower-access comparison while retaining the same BC checkpoint rule.

Where complete resumable checkpoints exist, continue all four selected arms from their original trajectories to approximately 500k cumulative post-probe actions.

For the current 2,048-action rollout batch:

* Existing endpoint: 251,904 actions.  
* First longer endpoint: 501,760 actions.  
* Additional training per branch: 249,856 actions.

Confirm these values against the actual implementation. Record all quantization and actual probe counts.

The full proposed extension is:

2 existing seeds × 2 lengths × extended BC × 4 arms \= 16 continuations.

This requires approximately 4M additional training actions before evaluation. Admit it only if the full cost fits.

Important controls:

* Longer training does not mean longer episodes. Keep the task horizon, reward, boundary, and saved-state clocks unchanged.  
* Keep alpha, lambda, preservation reference, and PPO settings fixed.  
* Preserve optimizer, environment/sampler, RNG, and schedule state.  
* Do not restart from weights alone and describe the result as a continuous trajectory.  
* Check whether any learning-rate schedule ended at 250k. Do not arbitrarily reset or stretch it during continuation.  
* If a longer-budget schedule requires a fresh run from the post-probe fork, declare that as a separate development pipeline and count the full cost.  
* Keep branch comparisons paired and use balanced execution order.  
* Do not extend only the branch that currently looks best.

Save intermediate checkpoints cheaply. Evaluate at prespecified endpoints, rather than repeatedly checking performance until a favorable result appears.

If all 16 continuations cannot fit, preserve complete four-arm comparisons across both existing seeds for K=3 extended BC first. Add the K=1 comparison next. State the resulting scope limitation.

## **5\. Add one independent development replicate**

The next priority is checking whether the most important pattern survives another independently trained initialization.

Reserve a new development seed, such as seed 2\. Do not use seeds 10–14, which remain reserved for confirmation.

Train BC using the unchanged dataset and checkpoint rules. Save both checkpoints. Do not select the new seed’s checkpoint using its PPO outcomes.

If affordable, run the common probe and all four selected arms for K=3 extended BC to the same longer endpoint used above. This costs approximately 2M continuation actions, plus BC evaluation, warmup, probe, and evaluation.

This replicate should test the existing setup. Do not retune it specially to reproduce the earlier result.

Use the original two seeds and the new seed to assess:

* Whether ordinary PPO continues learning.  
* Whether the combined intervention’s apparent K=3 benefit persists.  
* Whether preservation limits useful adaptation.  
* Whether reset benefits emerge later.  
* How much conclusions depend on individual training paths.

Three development seeds still do not constitute confirmation. Keep all results exploratory.

If the budget cannot support both broader continuation and a fresh replicate, explain the tradeoff. Prefer independent replication over additional doses once the basic longer-training comparison is established.

## **6\. Improve evaluation where it resolves an ambiguity**

Use evaluation to answer specific questions, not simply to accumulate attempts.

For new development endpoints, use common normal-start layouts and attempt seeds across arms. A reasonable starting allocation is 32 layouts × 8 attempts, plus the existing 64-state competence bank × 2 attempts. Increase precision selectively through a rule recorded before inspecting the additional outcomes.

Reuse existing attempts where the protocol permits. Avoid paying separately for an endpoint curve point that can be derived from the same prespecified evaluation sample.

Retain per-attempt records and uncertainty grouped by layout and training seed.

### **Fixed-bank versus actual-arrival competence**

Investigate whether the planner-derived competence bank represents states that trained policies actually reach.

Where existing saved arrivals permit it, compare their:

* Remaining time.  
* Position and orientation.  
* Inventory and object configuration.  
* Suffix progress.  
* Layout distribution.

If this mismatch could explain the results, construct a small development-only arrival-state evaluation:

* Collect first-crossing states without selecting on eventual success.  
* Use states from ordinary PPO and the combined arm, and from the BC/probe policy where useful.  
* Evaluate the same frozen policies on each common source bank.  
* Preserve each state’s original remaining time.  
* Record how sampling and weighting define each bank.  
* Report sparse or missing arrival samples honestly.

This cross-policy evaluation can distinguish sensitivity to arrival-state distribution from differences on the fixed planner bank. It does not identify a unique training mechanism.

Keep the original competence bank and its longitudinal results intact. A retrospectively constructed bank is an additional diagnostic, not a replacement primary metric.

### **Deadline sensitivity**

If arrival timing appears important, run a small, explicitly labeled development evaluation under a longer task deadline.

Treat this as a new task condition. Account for remaining-time observations changing policy inputs. Do not refresh clocks in the original condition or merge these results with it.

Run this only if it distinguishes an actual uncertainty. It is not a mandatory extra benchmark.

### **Evaluation repeatability**

Use saved checkpoints to check evaluation repeatability and Monte Carlo variation. Distinguish that from variation produced by training. Keep this small and avoid a large CPU/MPS comparison unless a concrete defect requires it.

### **Compute and time limits in general**

In general, you are to be complete and precise. If any meaningful and informative task would take up more time than we were initially comfortable with, you should absolutely go ahead with it – do not worry about deadlines.

## **7\. Run at most one targeted intervention/control family**

After the paired longer runs and replication are budgeted, choose at most one additional family based on the most important unresolved explanation.

Record the trigger and comparison before launching it. Prefer two existing seeds and one scientifically informative condition. Preserve matched controls and count evaluation costs.

Possible families are:

### **A. Intervention-dose check**

Use this if the selected intervention is barely active or existing dose results leave a specific unresolved question.

Prefer extending existing alpha=0.5 or lambda=0.1 checkpoints rather than starting a broad grid. Compare against the corresponding selected-strength and ordinary-PPO trajectories at the same budget.

A combined alternative may be tested only if justified and affordable. Keep dose changes clearly identified. Do not assume that separately selected strengths are optimal jointly.

Do not rerun lambda=1 merely because it is available; existing evidence should justify any additional cost.

### **B. Suffix-learning positive control**

Use this if later-stage learning remains weak even with assistance.

Run a short development-only suffix-start training control, potentially alpha=1, from a common probe state. Retain binary terminal reward and original snapshot clocks.

Measure both suffix competence and normal-start success. This tests whether PPO can learn the suffix with abundant practice. It does not establish that suffix-only training solves the full task.

Do not add this control to the main four-arm comparison or describe it as the original reset intervention.

### **C. Preservation-location check**

Use this if evidence suggests preservation constrains prefix adaptation while helping suffix behavior.

Compare the existing anchor mixture with a clearly specified suffix-focused anchor distribution. Hold the remaining training procedure fixed and report the changed KL weighting.

Treat this as a new intervention. Any benefit may reflect both the chosen state distribution and the effective constraint strength.

### **D. Optimization sensitivity check**

Use this if longer runs reveal a concrete instability or critic problem that threatens interpretation.

Make one justified change, such as improved critic fitting or a smaller update. Evaluate matched controls under the revised pipeline. Do not compare a repaired baseline against interventions trained under a different pipeline.

Do not dismiss every competence decline as a defect, and do not preserve a defective implementation to obtain an intervention benefit.

These are conditional choices, not a list to execute in full. Do not introduce reward shaping, a new model class, a large architecture search, or additional algorithms.

## **8\. Consider training to 750k or 1M only through an explicit gate**

After the 500k results, assess whether another extension would resolve an important question.

Possible reasons include continued substantial learning, emerging intervention separation, or unresolved late deterioration. “More training is available” is insufficient.

If justified and affordable:

* Prespecify the condition, seeds, arms, endpoint, and evaluation.  
* Preserve paired comparisons across both original seeds.  
* Extend at least ordinary PPO and the relevant intervention together.  
* Use all four arms if the claim concerns their relative ranking.  
* Do not choose the extension condition solely because it produced the largest favorable effect.  
* Count the full incremental cost and retain M4 capacity.

For 2,048-action batches, nominal endpoints would be approximately 751,616 and 1,001,472 actions. Verify actual implementation counts.

A single-condition two-arm extension can answer a narrow question. It cannot establish the full four-arm ranking or generalize across BC checkpoints.

If the reserve makes this infeasible, stop at 500k and report what a longer study would cost.

## **9\. Analyze trajectories, mechanisms, and uncertainty carefully**

For each new endpoint, report:

* Normal-start P1 and stage access.  
* Fixed-bank competence and change from pi0/probe.  
* Conditional success after actual arrival.  
* Arrival-time and deadline effects.  
* Training visitation and reward exposure.  
* Intervention activity and optimization diagnostics.  
* Paired intervention contrasts, by K and BC checkpoint.  
* Compute and action cost.

Plot complete development learning trajectories with the same evaluation protocol where possible. Report fixed-budget endpoints. Do not select each arm’s best checkpoint.

Keep these conclusions distinct:

* An intervention accelerates learning.  
* An intervention improves the later endpoint.  
* An intervention preserves measured competence.  
* An intervention trades prefix access against suffix performance.  
* An intervention helps only under particular conditions.  
* The data remain inconclusive.

Do not infer p=q×c for the fixed bank.

The observed combined-effect pattern is approximately −0.034 at K=1 and \+0.040 at K=3 at the original endpoint. Track whether that difference persists with longer training and another seed.

For each seed, calculate:

D\_seed \= mean\_BC\[(Y11−Y00 at K=3) − (Y11−Y00 at K=1)\],

where both checkpoints were evaluated. For an extended-BC-only analysis, label that narrower estimand explicitly.

Report component effects. Positive moderation alone does not establish benefit at K=3.

Keep training seed as the independent block. Do not treat lengths, checkpoints, branches, attempts, or checkpoints along one trajectory as independent replicates.

Use interval estimates and transparent seed-level plots. Additional development remains exploratory. Avoid significance-driven stopping and large predictive models.

Withdraw unsupported power claims. Use planning scenarios that preserve within-seed dependence. Distinguish pointwise uncertainty, multiplicity-adjusted claims, and practical equivalence.

## **10\. Preserve adaptive-development validity**

Adaptation is allowed within development. Make it traceable.

Before each experiment, record:

* The unresolved question.  
* Why existing evidence cannot answer it.  
* The comparison and sampling plan.  
* The maximum cost.  
* The engineering and scientific stopping rules.  
* What possible outcomes would change the recommendation.

Afterward, record what changed and what did not.

Use existing data to choose informative development conditions, but do not describe those conditions as representative of an unseen population. Do not tune toward a required forgetting effect or preferred intervention winner.

Keep confirmation layouts, outcomes, and reserved seeds untouched. Never use confirmation data to resolve a development ambiguity.

If a new setting appears better, assess whether the evidence supports changing the pipeline. Do not silently replace the original selection rule. Document the old setting, new evidence, proposed change, and remaining uncertainty.

## **11\. Maintain precise execution and monitoring**

Use the resource-controlled harness for heavy work. Keep all parallel activity within the single-job and aggregate resource limits.

Every run must have a committed configuration, unique ID, source/data hashes, exact seeds, checkpoint lineage, action counters, and resumable state.

Use deterministic polling scripts. Keep monitoring quiet until completion, failure, resource pressure, or a genuine stall. Do not repeatedly invoke the model to inspect unchanged logs.

Perform the two-hourly research review. Check whether the next experiment remains the most informative use of the remaining budget.

Stop a run for correctness, resource, or execution failures. Do not stop or rerun it because its result is unfavorable. Preserve partial and failed records.

Before every submission, account for unfinished work and conservative remaining job costs. The “72M submissions” rule is insufficient by itself. Ensure the campaign, required evaluation, and audit can finish within 80M.

## **12\. Deliver a complete pre-M4 decision report**

Update the consolidated report and research state. Keep exploration clearly separated from confirmation.

Provide:

1. Audit findings and corrected historical claims.  
2. Exact new experiments, costs, deviations, and failures.  
3. Learning curves and paired effects at the original and longer endpoints.  
4. Evidence about access, competence, arrival-state mismatch, time pressure, and intervention activity.  
5. Replication evidence and remaining uncertainty.  
6. Whether further development is justified or has diminishing value.  
7. A recommended M4 design and its conservative budget.

Present costed M4 options where relevant:

* The full two-length, two-checkpoint, five-seed matrix at the shorter endpoint.  
* The full matrix at a longer endpoint, with the additional budget required.  
* A scientifically focused longer-endpoint matrix that reduces scope while retaining independent replication.

Do not silently reduce seeds, remove difficult conditions, or change the scientific estimand. Explain exactly what each option can and cannot establish.

Recommend one option decisively. The objective is a valid and informative confirmation study, not the largest experiment count.

Preserve the original protocol freeze and prepare a dated amendment specifying the final task, data roles, checkpoint rules, PPO pipeline, interventions, exact endpoint, hypotheses, uncertainty, multiplicity, equivalence rules, and budget controls.

Keep RQ2 as a costed follow-up proposal unless separately authorized. Development heterogeneity can motivate it; these few conditions cannot establish a useful held-out-condition selector.

Finish with a concise readiness report and wait for my explicit approval before generating confirmation data or launching M4.

**Owner decision, 2026-10-31 (reply to the pre-M4 readiness report).** Recorded verbatim.

> Don't worry about the cap. Do A but for both 250K as well as 500K.

**Owner instruction, 2026-10-31 (after M4): post-M4 scientific audit and interpretation revision.** Recorded verbatim.

> Complete a post-M4 scientific audit and interpretation revision before declaring the project finished. Do not launch another broad training campaign.
>
> The primary aggregate result appears reproducible. Preserve it. The immediate task is to distinguish that result from stronger claims that the data do not establish, investigate the condition-level pattern, and correct the competence-bank comparison.
>
> Use existing artifacts first. You may inspect source, recompute analyses, write tests, generate figures, and revise reports. Do not modify the frozen primary analysis, discard unfavorable results, or start new training. Prepare any follow-up experiment as a concrete proposal for my approval.
>
> Read the manuscript, excluding Preliminary experiments, the latest protocol and amendments, FINDINGS F8–F10, REPORT, and all M4/development analysis artifacts.
>
> ## **1\. Establish the final protocol and provenance**
>
> Recover the exact final protocol, including both approved amendments.
>
> Record:
>
> * When both endpoints became part of confirmation.
> * When the 64-layout × 8-attempt evaluation design was fixed.
> * Which hypotheses were primary, secondary, or descriptive.
> * The multiplicity and equivalence procedures.
> * The approved campaign cap, submission stop line, and protected reserve.
> * Source and harness commits needed to reproduce execution.
>
> Verify timing against data generation and the first accessible confirmation outcome. Committing analysis code before outcomes is useful, but does not by itself establish that every inferential decision was prespecified.
>
> Do not reinstate the earlier 80M cap if the owner subsequently increased it. Distinguish the current hard budget from a submission stop line.
>
> The final ledger includes approximately 3.45M estimated test actions outside the runner. Present measured and estimated consumption separately. Do not describe 93.02M as an entirely exact count.
>
> Fix future accounting at the common environment-step boundary so tests and interactive checks cannot silently escape the ledger or resource controls. Keep this implementation small.
>
> ## **2\. Preserve the correct aggregate conclusion**
>
> Independently reproduce the six primary aggregate contrasts and their uncertainty from branch records.
>
> Verify:
>
> * Five independent training-seed blocks.
> * Equal weights over the four K/checkpoint strata.
> * Correct grouping of the two checkpoints from one BC path.
> * Pairing across arms and endpoints.
> * Correct layout resampling, including any cross-K matching.
> * No treatment of episodes, checkpoints, or endpoints as independent training replicates.
>
> Report the TOST statistics and p-values explicitly, rather than only a verdict inferred from interval containment. Distinguish multiplicity handling for directional tests from the equivalence procedure. If presenting a joint “all six are within the margin” statement, specify its statistical construction.
>
> Keep the conclusion limited to the prespecified aggregate estimand:
>
> “At the tested strengths and budgets, the equal-weight average intervention effects were practically equivalent to ordinary PPO within an absolute ±0.05 P1 margin.”
>
> Do not replace this with:
>
> * Every condition is equivalent.
> * The interventions change nothing.
> * No learning-curve effect exists.
> * No useful intervention can exist in this task family.
> * The interventions cannot help beyond 500k.
>
> Bootstrap agreement is a sensitivity check, not independent replication. State which uncertainty is conditional on the fixed evaluation panel and which addresses sampling layouts.
>
> ## **3\. Audit the overlooked condition-level effects**
>
> Reproduce every arm-versus-ordinary contrast for all four strata and both endpoints. Use paired seed-level differences.
>
> The supplied tables show:
>
> * Preservation, K=3/early BC, 500k:
>   mean \+0.0453125;
>   pointwise 95% t-interval \[0.0352548, 0.0553702\];
>   all five seed differences positive.
> * Preservation, K=1/early BC, 250k:
>   mean −0.0480469;
>   pointwise interval \[−0.0767721, −0.0193217\].
> * Preservation, K=3/extended BC, 500k:
>   mean −0.0273438;
>   pointwise interval \[−0.0571930, 0.0025056\].
>
> Confirm these directly from raw attempts and the analysis manifest.
>
> Do not judge these effects by whether they exceed the unpaired seed-to-seed spread of arm performance. Pairing exists specifically to remove shared training-replicate variation.
>
> For the K=3/early-BC signal:
>
> 1. Verify row selection, hashes, evaluation layouts, attempt counts, and weighting.
> 2. Show every seed’s baseline, preservation result, and paired difference.
> 3. Compute a crossed seed/layout interval for this subgroup.
> 4. Inspect per-layout effects and leave-one-seed/leave-one-layout-group sensitivity.
> 5. Check whether gains are broad or concentrated in a few shared layouts.
> 6. Treat any zero-arrival baseline as valid data; do not drop it.
> 7. Apply a transparent multiplicity analysis over the actual subgroup family examined.
> 8. State the dependence of small-sample t inference on its assumptions.
>
> Do not promote a discovered subgroup to a prespecified primary result. Conversely, do not erase a coherent signal because the global average is near zero or its point estimate is slightly below 0.05.
>
> At a baseline near 0.062, a gain of 0.045 is substantial relative to baseline performance. Report both absolute and relative changes, while retaining the prespecified absolute margin for the original primary claim.
>
> Examine checkpoint dependence within K as well as length dependence. Averaging checkpoints can conceal a preservation benefit for early BC and a cost for extended BC. Report any intervention × K × checkpoint analysis as secondary or post hoc according to the final protocol.
>
> ## **4\. Correct the competence-bank comparison**
>
> The current comparison mixes two changes:
>
> * Progress within the suffix.
> * Differences between planner and policy-generated states.
>
> Separate them before attributing a gap to prefix configuration.
>
> For each policy, seed, and relevant condition, report:
>
> * Planner entry-state competence.
> * Planner retrieval-state competence.
> * Planner carrying-state competence.
> * The original weighted mixed-bank score.
> * Competence on each policy-generated arrival bank.
> * Remaining-time and layout distributions for every bank.
>
> For example, M3 K=3/extended-BC seed-0 ordinary PPO has mixed-bank c=0.59375 but entry c=0.390625. Its competence on its own arrival bank is about 0.38. Verify this example and quantify how much of the apparent gap is due to progress composition.
>
> Also note cases where actual-arrival competence exceeds planner entry competence. Do not summarize every policy with a uniform mismatch claim.
>
> The original mixed bank is a valid declared ν. Its score remains useful as a distribution-specific measure. It is not automatically an estimate of completion from boundary entry.
>
> Do not replace the original metric retrospectively. Add the decomposed analysis and explain the different estimands.
>
> Do not conclude that bank mismatch caused the lack of P1 benefit. The current results establish coexistence of bank-score changes and small average P1 effects, not that causal explanation.
>
> ## **5\. Separate access changes from arrival-conditioned completion**
>
> For normal-start evaluation, retain the exact identity:
>
> p \= q × r,
>
> where r is completion conditional on actual arrival.
>
> This r is not mixed-bank c. It also changes when the policy reaches different states.
>
> The aggregate 500k preservation results approximately give:
>
> * Ordinary PPO: p=0.4463, q=0.7057, pooled r≈0.6324.
> * Preservation: p=0.4494, q=0.7459, pooled r≈0.6025.
>
> Verify the pooling weights before using these figures. Do not multiply averages with incompatible weighting.
>
> Compute a descriptive decomposition, preferably within seed and condition:
>
> Δp \= Δq × (r1+r0)/2 \+ Δr × (q1+q0)/2.
>
> This can show numerical cancellation between access and arrival-conditioned completion. It does not identify deterioration of a fixed skill, because r averages over policy-dependent arrival distributions.
>
> When q=0, r is undefined. Do not fill it with zero to force a decomposition. Report the unsupported component explicitly.
>
> For the K=3/early-BC preservation signal, inspect whether the benefit accompanies:
>
> * Greater access.
> * Different arrival timing or states.
> * Better completion from a common fixed entry bank.
> * Preservation of behavior already present at pi0.
> * Improved behavior beyond pi0.
>
> Use the same fixed competence states for longitudinal comparisons. Do not compare early normal-start scores on conf\_select with final scores on conf\_final as if their difference measured learning.
>
> ## **6\. Revisit the secondary outcomes and curve claims**
>
> Report C4 and R4 alongside P1 without changing the primary endpoint.
>
> At 500k, preservation has approximately:
>
> * C4 difference \+0.0329, pointwise interval \[0.0098, 0.0560\].
> * R4 difference −0.0189, pointwise interval \[−0.0366, −0.0012\].
>
> Verify these estimates, their uncertainty, and their status under the planned analysis.
>
> These may describe a redistribution of success across tasks or attempts despite similar mean P1. They do not establish generalization, policy-support expansion, or broad skill retention.
>
> Correct “the interventions neither accelerate nor slow learning.” Endpoint equivalence does not establish learning-curve equivalence. The change in treatment contrasts between 250k and 500k already suggests some early deficits close later.
>
> Show prespecified endpoint contrasts and the descriptive curves. Do not invent a confirmatory area-under-curve test after seeing them, and do not choose a best checkpoint per arm.
>
> Similarly, do not infer that PPO is “step-size-limited” solely because gradients were clipped frequently. Report the learning rate, clipping activity, actual policy changes, and observed learning. A clipping threshold being active is not itself a diagnosis of the optimization bottleneck.
>
> ## **7\. Evaluate the value of selection separately from heterogeneity**
>
> Correct the research-question mapping:
>
> * RQ1 concerns when interventions help.
> * RQ2 concerns whether early measurements select useful interventions on held-out conditions after charging their cost.
>
> Aggregate equivalence does not imply absence of heterogeneity. Heterogeneity does not automatically justify an expensive selector.
>
> Compute an explicitly labeled hindsight reference:
>
> 1. Average each arm’s P1 over training seeds within each condition.
> 2. Choose the best observed arm separately in each condition.
> 3. Compare that average with the best observed fixed arm.
>
> The branch table gives approximately 0.46035 versus 0.44990 at 500k, a 0.01045 gap. Verify this.
>
> Explain that this is an optimistic in-sample reference subject to selection noise. It is not a formal upper bound on population performance.
>
> Assess whether plausible gains could survive diagnostic and selection costs. Include simple condition-identity rules as future baselines; an expensive competence diagnostic must add value beyond knowing K and the BC checkpoint.
>
> Do not train a selector on M4 and call its performance on those same conditions a held-out RQ2 result. Leave-one-seed-out analysis still tests new training replicates on the same condition family, not generalization to unseen conditions.
>
> RQ2 may remain deferred because the demonstrated selection headroom is small and validation is incomplete. Do not defer it using the false premise that no condition-level signal exists.
>
> ## **8\. Verify execution without repeating the entire campaign**
>
> Check the raw artifacts needed to support the revised report:
>
> * All 20 forks and 160 branch-endpoint records.
> * Complete configuration and state lineage.
> * True diagnostic/final split separation.
> * Pairwise overlap checks among confirmation roles, not only confirmation-versus-development checks.
> * Required bank composition and matched donors.
> * Metric recomputation and correct missing conditional statistics.
> * Exact versus estimated resource accounting.
> * Final protocol and analysis timing.
>
> The attached data gate alone reports zero overlap with development; verify separation between conf\_select, conf\_bank, and conf\_final independently.
>
> Inspect local-only harness commits and record the versions needed to reproduce the campaign. Respect existing push permissions. Do not claim remote reproducibility if required harness changes remain unavailable remotely.
>
> Stop leftover watchers and workers by verified identity. Preserve checkpoints and evidence. Do not delete data to simplify the record.
>
> ## **9\. Recommend the smallest justified follow-up**
>
> Do not automatically extend everything to 1M, increase intervention strengths, or switch domains.
>
> First finish the offline subgroup and bank-composition analyses. Then propose one follow-up, with a precise question and cost.
>
> Two possible directions are:
>
> A. Independent replication of conditional preservation effects:
> K=3, early versus extended BC, ordinary PPO versus the selected preservation arm, fresh training seeds, fresh evaluation layouts, and a frozen 500k endpoint.
>
> This tests whether checkpoint-dependent intervention benefits reproduce. Five seeds would require approximately 10M continuation actions before BC, probes, diagnostics, and evaluation. Cost it accurately. Specify which claims and effect sizes it could support.
>
> B. A small measurement-validity study:
> Compare planner entry states and actual arrival states with matched layouts, time, pose, inventory, and progress. Only after those controls should prefix configuration be tested.
>
> Any prefix-state intervention must preserve success-relevant variables and valid simulator semantics. A clock extension changes both available time and the policy’s observed input. Do not describe it as a pure test of time alone.
>
> If the existing artifacts resolve the bank question, do not spend additional actions on it.
>
> If later proposing arrival-aligned resets or preservation anchors, name that as a new intervention. Do not quietly substitute it for the original demonstration-state intervention.
>
> Do not choose a new task because it produces a preferred intervention winner. Any task revision must be justified by measurement validity or the research question, with feasibility criteria defined independently of branch outcomes.
>
> Do not execute new training until I approve the concrete proposal.
>
> ## **10\. Deliver the revised scientific closeout**
>
> Update the consolidated report with:
>
> 1. The valid aggregate equivalence result and its exact scope.
> 2. Condition-level effects and uncertainty, including the overlooked preservation signal.
> 3. Progress-matched competence comparisons.
> 4. Access/arrival-conditioned completion analysis and causal limitations.
> 5. Secondary coverage, reliability, and trajectory observations.
> 6. Execution and accounting limitations.
> 7. A corrected assessment of RQ1 and RQ2.
> 8. One decisive, costed recommendation for what to do next.
>
> Produce a compact effect plot across all four conditions and both endpoints, with seed-level paired points and uncertainty. Add a bank-component plot only if it clarifies the interpretation. Generate figures reproducibly from saved tables.
>
> Preserve historical findings, but mark superseded interpretations clearly. Remove the stale “Not started” status. Do not leave the current headline contradicting the detailed tables.
>
> Prepare manuscript-ready wording in the report. Do not modify the authoritative manuscript unless separately instructed.
>
> The intended conclusion may be:
>
> “Small average effects coexist with possible condition-dependent preservation benefits, and the interpretation of competence depends strongly on the saved-state distribution.”
>
> Establish whether that wording survives the audit. Do not treat it as a required outcome.
>
> You are tasked with recording this in your project statement, updating your state and checklist, and executing with precision and accuracy. You must also start the battery watches and end execution in case the battery falls below 20% (check every 5 minutes).

**Owner instruction, 2026-10-31 (after the post-M4 audit): R1 replication approved with refinements.** Recorded verbatim.

> I approve the focused R1 replication described in section C9, subject to the refinements below. Complete the preflight, freeze the protocol, and execute autonomously. Do not request routine confirmation again.
>
> ## 1. Scope and resources
>
> Run only:
>
> - K=3.
> - Early and extended BC checkpoints: 4k and 16k updates.
> - Eight fresh training seeds, 15–22.
> - Ordinary PPO and preservation.
> - Primary endpoint: 501,760 post-probe actions.
> - Descriptive checkpoint: 251,904 actions.
>
> Keep the original joint BC training dataset and sampler unchanged. Restrict online R1 experiments to K=3; do not retrain BC on a K=3-only dataset.
>
> Both arms must use normal starts: alpha=0. Compare lambda=0 with lambda=0.01. Keep the original BC checkpoint as the preservation reference.
>
> Retain all other task, model, reward, horizon, probe, PPO, anchor-bank and checkpoint rules. Do not add doses, architectures, K=1, or a longer endpoint.
>
> Maintain four CPU cores, 6 GiB, and one concurrent experiment job.
>
> I authorize a maximum of **28.4M additional environment actions** for R1, including data replay, tests, diagnostics, training, evaluation, failures and retries. This is a hard incremental budget, not a submission stop line.
>
> Record the starting ledger total. For R1 only, this authorization supersedes the old 109M submission stop line. Do not interpret the earlier removal of the campaign cap as unlimited authorization.
>
> Before admitting each job, account for unfinished commitments, its conservative cost, and remaining required evaluation and audit. Keep approximately 2M actions available for failures and audit until completion costs are secure.
>
> If the complete design cannot fit, report the specific shortfall. Do not silently reduce seeds or alter the estimand.
>
> ## 2. Improve layout coverage without increasing episode count
>
> For the primary normal-start evaluation, use **128 fresh layouts × 4 independent stochastic attempts** per policy, rather than 64 × 8.
>
> This retains 512 attempts while increasing coverage of layout variation. P1 is primary. C4 and R4 may remain descriptive; acknowledge their changed measurement precision.
>
> Use the same layout panel and attempt-seed schedule across arms, checkpoints and training seeds. Keep the two BC checkpoints paired within each replicate.
>
> Maintain a separate fixed competence bank with the original progress composition, and report entry, retrieval and carrying scores separately.
>
> Generate new diagnostic, bank and final roles without changing any existing role. Verify disjointness from all previous training, development and confirmation evaluation roles. Preserve the unchanged-training-data gate.
>
> Recompute the conservative cost after this change. Episode lengths may change even when episode counts do not.
>
> ## 3. Freeze hypotheses and analysis before R1 data generation
>
> Keep two primary tests:
>
> H1: the mean paired preservation effect on final normal-start P1 with early BC.
>
> H2: the mean paired difference between the preservation effects with early and extended BC.
>
> Use two-sided paired tests and Holm correction across these two hypotheses.
>
> For seed i:
>
> Δearly_i = P1(preservation, early) − P1(ordinary, early)
>
> Δextended_i = P1(preservation, extended) − P1(ordinary, extended)
>
> Interaction_i = Δearly_i − Δextended_i.
>
> The independent unit is the training seed: n=8 for both tests. Checkpoints, layouts, attempts and endpoints are not additional training replicates.
>
> Report paired seed-level intervals and crossed seed/layout bootstrap intervals. Preserve arm and checkpoint pairing when resampling layouts.
>
> State which inference is conditional on the frozen panel and which addresses layout sampling. Bootstrap agreement is a sensitivity check, not independent replication.
>
> Reproduce the power calculation with an executable script. Include plausible variance scenarios and layout uncertainty. Do not rely primarily on the unusually small SD observed in the selected M4 subgroup or promise 80% power unconditionally.
>
> Do not require the new effect to equal +0.045 or +73% relative. Selection can inflate the original estimate. Estimate the replication effect honestly.
>
> A positive effect is not automatically evidence that the true effect exceeds five percentage points. Keep statistical direction, magnitude and practical importance distinct.
>
> ## 4. Preserve independence and execution integrity
>
> For each seed:
>
> 1. Train one BC path and save both fixed checkpoints.
> 2. Run the unchanged critic preparation and common probe separately for each checkpoint.
> 3. Fork the complete post-probe state into ordinary PPO and preservation.
> 4. Train both branches to the frozen endpoint.
> 5. Save complete resumable states and immutable evaluation artifacts.
>
> Retain every valid seed, including floor performance or zero arrivals. Do not replace a seed because its BC or PPO behavior is inconvenient.
>
> Run a single initial engineering canary before releasing the remaining jobs. Check configurations, hashes, counters, telemetry and output schemas. Do not use its outcome to retune or reconsider sample size.
>
> Route heavy tests and interactive environment checks through the resource-controlled runner. The unmanaged step counter does not enforce CPU or memory limits and is not a substitute.
>
> Respect the existing failure policy. No performance-driven retries or automatic scientific changes.
>
> ## 5. Keep the secondary analysis informative but bounded
>
> Report, by checkpoint and arm:
>
> - P1 and paired effects.
> - Stage access q.
> - Completion conditional on actual arrival.
> - Fixed-bank entry, retrieval and carrying competence.
> - Changes from pi0 and the probe on the same fixed bank.
> - Arrival timing and inventory.
> - Anchor KL, training visitation and optimization diagnostics.
>
> Preservation’s access gain does not by itself demonstrate protection of a suffix skill. It may retain prefix behavior, improve subsequent learning, or affect several behaviors.
>
> Keep p=q×r separate from fixed-bank competence. Do not impute r=0 when no arrivals occur.
>
> Compare longitudinal normal-start scores only on the same layout role. Keep diagnostic and final-panel curves separate.
>
> The 250k checkpoint is descriptive. Do not introduce an additional confirmatory endpoint or choose a best checkpoint after observing results.
>
> Do not launch a selector study or a causal-mechanism experiment during R1.
>
> ## 6. Prespecify interpretation and stopping discipline
>
> Interpret the primary outcomes separately:
>
> - H1 supported, H2 supported: replication of the early-BC benefit and evidence of checkpoint dependence.
> - H1 supported, H2 unsupported: replication of the early-BC benefit; checkpoint dependence remains unresolved.
> - H1 unsupported, H2 supported: relative checkpoint dependence alone does not establish benefit in early BC.
> - Neither supported: assess interval width and effect sizes. Distinguish an informative failure to replicate from an inconclusive result.
>
> Keep the original M4 aggregate equivalence result intact regardless of R1.
>
> Do not expand the seed count, change lambda, alter evaluation panels, or extend training in response to interim results. Stop only for execution, correctness, resource or budget problems.
>
> Maintain deterministic monitoring and two-hour research reviews. Reviews may identify defects and improve execution; they may not adapt the frozen scientific design based on emerging effects.
>
> ## 7. Deliver the replication decision
>
> Update the consolidated report with:
>
> - Frozen protocol and provenance.
> - All eight paired seed results.
> - Both primary estimates, intervals and Holm-adjusted tests.
> - Layout sensitivity and secondary stage measurements.
> - Comparison with the original post hoc estimate, clearly separated.
> - Exact and estimated costs, failures and exclusions.
> - A decisive interpretation and one justified next research question.
>
> Preserve local harness changes needed for reproduction and record their hashes. Respect existing publication permissions.
>
> Once R1 is complete, stop scientific execution and report. Do not automatically proceed to RQ2, another task family, larger doses or further training.

---

**Owner instruction, 2026-11-01 (after R1): final replication R2 (20 seeds) plus cross-panel and anchor-component studies.** Recorded verbatim.

Superseded limits (agent note, not owner text): this is a new incremental authorization of 50M environment actions from the ledger total 118,670,302 recorded before any work under it. It replaces the R1 28.4M budget (closed; its unused 2.93M is not carried over) and the old 109M M4 submission stop line, which no longer applies. There is no wall-time or overnight limit; earlier batch-hour and campaign-hour limits do not stop this programme, while the resource limits (4 cores, 6 GiB, one job) stay.

> Proceed autonomously with the research programme below. Continue across sessions until the authorised work is complete, even if it extends beyond tonight or into the following days. There is no overnight deadline or fixed wall-time limit.
>
> Think like a senior research scientist and engineer: resolve the important uncertainties, preserve valid comparisons, and distinguish evidence from interpretation.
>
> This authorizes one final, fixed-size replication and two smaller exploratory studies. It does not authorize repeated testing until a preferred result appears.
>
> Read `agent.md`, `project.md`, the manuscript excluding Preliminary experiments, and the latest protocol, report, findings and decisions. Preserve the M4 and R1 results and their frozen verdicts.
>
> ## 1. Authority, priorities and resource limits
>
> Use these priorities:
>
> 1. Targeted R1 audit and protocol freeze.
> 2. Complete the new 20-seed replication.
> 3. Cross-panel evaluation of existing policies.
> 4. A small anchor-component experiment.
> 5. Independent audit and consolidated reporting.
>
> Resource limits:
>
> - Four CPU cores, 6 GiB, one experiment job at a time.
> - Native MPS under the existing monitored resource controls.
> - Maximum **50M additional environment actions**, including generation, tests, training, diagnostics, evaluation, failures and retries.
> - No paid or remote compute.
>
> Suggested allocation:
>
> - Up to 38M for replication, including its preparation and evaluation.
> - Up to 4M for cross-panel evaluation.
> - Up to 4M for the anchor-component experiment.
> - Keep 4M available for validation, failures and completion costs.
>
> These are ceilings, not spending targets. Protect completion of the replication before admitting exploratory work.
>
> Record the current ledger as the starting point. This is a new incremental authorization; do not add unused R1 allowance to it. Replace obsolete submission stop lines accordingly.
>
> Before each submission, account for unfinished commitments, the new job’s conservative cost, and remaining mandatory evaluation and audit. A submission threshold alone is not budget enforcement.
>
> If conservative replication costs exceed the suggested allocation, drop exploratory work first. Do not reduce the fixed sample size after observing results.
>
> Continue valid work without stopping because a night or calendar day has ended. If execution is interrupted, resume from complete checkpoints under the same frozen design. An operational interruption does not change the planned sample size or permit analysis of a convenient subset.
>
> ## 2. Complete a targeted audit before new training
>
> Keep this focused. Do not repeat the entire M0–M4 audit.
>
> Verify the R1 primary estimates, Holm procedure, seed grouping, action counts, failure record and evaluation roles from raw artifacts.
>
> Reconcile the report’s “48 branch summaries” with:
>
> 8 seeds × 2 checkpoints × 2 arms × 2 endpoints = 64 endpoint records.
>
> Identify the exact inventory. If it is a documentation error, correct it and proceed. If records are missing or mismatched, resolve the scientific impact before launching replication.
>
> Correct these interpretations:
>
> - Retain R1’s failure to meet its frozen Holm-2 criterion.
> - Describe the estimates as compatible with a positive effect similar to M4. Do not use interval overlap as proof of replication.
> - Do not say eight seeds “cannot confirm” the effect. Their power was limited, not zero.
> - Do not attribute the larger SD entirely to subgroup selection. Panel differences, training variability and small-sample variance estimation also require consideration.
> - Do not infer that access dominates because q is significant while bank competence is not.
>
> For every R1 seed, compute the exact descriptive decomposition:
>
> Δp = Δq × (r1+r0)/2 + Δr × (q1+q0)/2,
>
> where r is completion conditional on actual arrival.
>
> Report both contributions, their seed variation, and their sum. Do not substitute fixed-bank c for r. If q=0, report the undefined component rather than imputing it.
>
> This decomposition is arithmetic, not causal mediation: each policy reaches a different arrival-state distribution.
>
> Correct “mainly access” if the decomposition does not support it. Do not force the existing story to survive.
>
> ## 3. Freeze replication R2 before generating its data
>
> R2 addresses one question:
>
> Does preservation with lambda=0.01 improve normal-start P1 at K=3 with early BC after 501,760 continuation actions?
>
> This is an RQ1 intervention study. It is not RQ2 intervention selection.
>
> Design:
>
> - **20 fresh training seeds: 23–42.**
> - K=3 only.
> - Early BC checkpoint at 4,000 updates.
> - Ordinary PPO versus preservation.
> - Alpha=0 in both arms.
> - Lambda=0 versus 0.01.
> - Primary endpoint: 501,760 post-probe actions.
> - Save 251,904 as a descriptive checkpoint.
>
> Use the unchanged joint BC dataset, sampler, architecture and training procedure. BC can stop after the early checkpoint because the extended checkpoint is unused.
>
> Keep the task, reward, episode horizon, observation, critic preparation, PPO probe, optimization settings and anchor distribution unchanged.
>
> Generate fresh diagnostic, competence-bank and final-evaluation roles. Append them without altering previous roles. Verify training-data identity and disjointness from all prior evaluation roles.
>
> Final evaluation:
>
> - 128 fresh layouts × 4 independent stochastic attempts per policy.
> - One common panel and attempt-seed schedule across arms and training seeds.
> - Fixed competence bank with 64 states × 4 attempts.
> - Report entry, retrieval and carrying competence separately.
>
> Do not select seeds, layouts or checkpoints according to policy performance.
>
> ## 4. Prespecify R2 inference and decision rules
>
> The sole primary estimand is the mean paired difference across the 20 training replicates:
>
> d_i = P1(preservation_i) − P1(ordinary_i).
>
> Use one two-sided paired test at alpha=0.05 and its 95% interval. Report a crossed seed/layout bootstrap and a sign-flip sensitivity analysis with their assumptions.
>
> Training seed is the independent replicate. Layouts, episodes, attempts and checkpoints are not extra training replicates.
>
> The primary test uses **R2 data only**. Do not pool M4 or R1 into it. Do not reinterpret dropping the checkpoint-interaction hypothesis as a retroactive R1 success.
>
> Any cumulative synthesis must remain separate, disclose adaptive study selection, and not present an ordinary pooled p-value as the new confirmatory test.
>
> Use 0.03 as the planning effect for the 20-seed design. It does not silently replace the original M4 ±0.05 equivalence margin or prove practical importance.
>
> Report uncertainty relative to zero, 0.03 and 0.05. Distinguish a positive effect from evidence that an effect exceeds either magnitude.
>
> Verify the power calculation in an executable script. Include SD scenarios around 0.035, 0.043, 0.05 and 0.06. Do not report power calculated from the final observed effect as evidence for the result.
>
> No interim significance stopping, sample-size extension, endpoint change or hypothesis substitution is allowed.
>
> Before execution, freeze the analysis, sample size, data roles, exclusions, failure policy, budgets and interpretation rules.
>
> If the result remains inconclusive, report that and stop this replication. Do not schedule another automatic replication.
>
> ## 5. Execute R2 with precision
>
> For each seed:
>
> 1. Train the fixed early BC policy.
> 2. Collect the unchanged critic-preparation data and run the common probe.
> 3. Copy the complete post-probe state into both arms.
> 4. Train both arms for the exact allowance.
> 5. Save complete states and immutable evaluation artifacts.
>
> Archive actor, critic, optimizers, RNGs, sampler/environment state, counters, teacher checkpoint, resolved configuration and software provenance.
>
> Use a single initial engineering canary from the planned sample. Verify hashes, configuration, counters, telemetry and output schemas. Do not use its performance to change the design.
>
> Keep every valid seed, including very poor performance. A valid zero-success trajectory is not an execution failure.
>
> Freeze scientific code before the campaign. Any correctness fix must identify affected runs and follow the recorded failure policy. Preserve failed runs and consumed actions.
>
> Do not inspect aggregate primary p-values until all 20 seeds are complete. Progress monitoring may check losses, numerical validity and execution health without changing the scientific design.
>
> ## 6. Cross-panel study: separate panel sensitivity from cohort differences
>
> Run this once the replication’s remaining execution and completion costs are protected.
>
> Use the existing K=3/early-BC ordinary and preservation policies from:
>
> - M4 seeds 10–14.
> - R1 seeds 15–22.
>
> Evaluate both policy cohorts on both original final panels.
>
> Use a new common diagnostic attempt-seed protocol across cohorts and arms. Prefer four attempts per layout if the conservative cost fits 4M actions. Otherwise freeze two attempts before collecting outcomes.
>
> Do not overwrite original evaluation records. Do not compute C4 or R4 when fewer than four attempts are available.
>
> Report the four cohort × panel cells:
>
> - M4 policies on the M4 panel.
> - M4 policies on the R1 panel.
> - R1 policies on the M4 panel.
> - R1 policies on the R1 panel.
>
> Show ordinary-PPO performance, preservation performance, paired effects and effect variability.
>
> This checks whether the baseline and SD differences depend on the evaluation panel or persist within a common panel. It cannot uniquely attribute residual differences to subgroup selection, hardware, or training seeds.
>
> Keep this exploratory. These are already observed policies and panels, not another independent replication.
>
> If all cells cannot fit the allowance, reduce attempts through the predeclared rule rather than choosing favorable models or layouts.
>
> ## 7. Anchor-component experiment: test which constraint contributes
>
> Run this if sufficient budget remains after protecting R2 and its audit.
>
> Question:
>
> Does the observed benefit depend on preservation at prefix states, suffix states, or their combination?
>
> Use three predetermined existing R1 early-BC forks: seeds 15, 16 and 17. Choose them by this fixed rule, not their outcomes. Reuse their complete post-probe states and original BC references.
>
> Run four fresh, contemporaneous branches per fork:
>
> - No preservation.
> - Prefix component only.
> - Suffix component only.
> - Both components, matching the original mixed preservation loss.
>
> All branches use normal starts, identical PPO settings and **251,904 continuation actions**.
>
> Use the original anchor bank and original stage labels. Retain the original component weights:
>
> L_preserve = 0.01 × [0.25 E_prefix(KL) + 0.75 E_suffix(KL)].
>
> Therefore:
>
> - Prefix-only coefficient: 0.0025.
> - Suffix-only coefficient: 0.0075.
> - Combined: both terms.
> - Baseline: neither term.
>
> Preserve the original sampling estimator. Do not renormalize a surviving component to lambda=0.01. That would change its strength and confound component deletion with a dose change.
>
> If sampling from a mixed anchor batch, zero the removed states’ contributions while retaining the original denominator. Test numerical equivalence between “both components” and the original loss and gradients.
>
> Use independent anchor-sampling RNGs so removing a component does not inadvertently change the environment-action random stream.
>
> Do not compare new component branches only against old R1 runs. Train all four controls contemporaneously because training-path variation is substantial.
>
> This is 12 branches and about 3.02M training actions before evaluation. Keep the entire experiment within 4M actions.
>
> Use a frozen, development-only evaluation allocation, initially 32 layouts × 4 normal attempts and 64 bank states × 2 attempts per branch. Confirm the conservative cost before launch.
>
> Report all seed-specific component contrasts and the factorial interaction. With three seeds, this is exploratory evidence.
>
> A component effect identifies the contribution of that penalty term under this implementation. It does not establish which skill, representation or causal pathway explains it. The actor shares parameters across stages.
>
> The endpoint is shorter than R2’s. Do not claim that this directly explains the 500k effect. Save complete states for a separately authorized extension if warranted.
>
> ## 8. Keep stage measurements precise
>
> For R2 and the component experiment, retain:
>
> - Normal-start p and q.
> - Arrival-conditioned r.
> - Fixed-bank entry, retrieval and carrying c.
> - Original mixed-bank c.
> - Changes from pi0 and the probe on the same fixed states.
> - Arrival timing, inventory and task-state summaries.
> - Anchor KL and intervention activity.
> - Training visitation and reward exposure.
>
> Report effect sizes and uncertainty. Do not compare p-values to decide which stage matters.
>
> Do not infer p=q×c for the fixed bank.
>
> Do not compare early normal-start measurements on diagnostic layouts with final measurements on another panel as though their difference measured learning.
>
> Keep original remaining time on every restoration. Training longer does not authorize changing episode deadlines.
>
> Do not introduce shaped rewards, demonstration resets, new architectures, larger lambda values or additional BC depths.
>
> ## 9. Maintain precise autonomy across sessions
>
> Use the resource-controlled runner for every heavy test, evaluation and training process. The unmanaged action counter is not a CPU/memory guard.
>
> Verify the heartbeat-race fix, concurrent atomic writes, graceful interruption and resume behavior before long execution.
>
> Use deterministic polling scripts. Keep them quiet until completion, failure, resource pressure or a genuine stall. Do not repeatedly invoke a model to inspect unchanged logs.
>
> Perform two-hour research reviews. Check correctness, provenance, resource use, completion cost and whether the frozen design remains executable. Do not adapt it to emerging treatment effects.
>
> Continue useful authorised work across context resets and session boundaries. Leave sufficient durable state for a fresh session to resume without reconstructing the reasoning from logs.
>
> If a correctness defect blocks scientific work, investigate it within budget and report the affected scope. Do not substitute a different research project.
>
> Do not launch RQ2 selection, another task family or an additional replication.
>
> ## 10. Deliver an integrated completion report
>
> Report:
>
> 1. Exactly what completed and what remains.
> 2. R2’s 20 paired seed results, primary estimate, interval and test.
> 3. Layout and statistical sensitivity checks.
> 4. Cross-panel results, if run.
> 5. Anchor-component results, if run.
> 6. Corrected access/completion interpretation.
> 7. Measured versus estimated cost, failures and deviations.
> 8. One decisive next recommendation.
>
> Preserve M4’s aggregate equivalence result and R1’s Holm-2 verdict. Present R2 as a new study.
>
> If R2 supports a positive effect, state the condition and magnitude precisely. Do not infer checkpoint dependence from an early-only study.
>
> If R2 is inconclusive or indicates a smaller effect than expected, do not automatically request more seeds. Explain what the programme has learned and whether further spending is justified.
>
> Generate reproducible figures showing paired effects, learning endpoints, panel sensitivity and component contrasts where informative. Keep the consolidated report coherent and distinguish confirmation from exploration.
>
> Commit the protocol, implementation, analysis and reports. Respect existing push permissions and preserve the harness version required for reproduction.
>
> When the authorised programme is complete, stop scientific execution and return the report. There is no requirement to finish tonight, and no automatic continuation beyond the programme.
>
> ## 11. Record these instructions, update the research state, and restart monitoring
>
> Before launching the programme, read these instructions deeply and reconcile them with the current evidence, research questions, existing protocol and repository state. Record the resulting decisions and concise scientific rationale; do not merely append an unchecked task list.
>
> Then:
>
> 1. Add this instruction as a dated owner amendment to the authoritative `project.md`, preserving earlier amendments and explicitly identifying any superseded time limits or stop lines.
> 2. Update `research/DECISIONS.md` with the scope, incremental budget, fixed experimental design, priorities and interpretation rules.
> 3. Update `research/STATE.md` with the current evidence, remaining uncertainties, active objective, resource limits and immediate next actions.
> 4. Update `research/CHECKLIST.md` with a dependency-aware plan covering the audit, freezes, implementation checks, experiments, evaluation, independent verification and reporting.
> 5. Record the next review time and monitoring state in the appropriate durable files.
> 6. Verify that these documents agree with each other and with the actual launch configurations.
> 7. Check for existing monitors by verified process identity so that restarting does not create duplicates.
> 8. Restart the battery-monitoring timers and the two-hour introspection loop using the existing approved safeguards.
> 9. Start execution autonomously without waiting for another routine approval.
>
> Each two-hour review must assess whether the work still addresses the research questions, whether comparisons and interpretations remain valid, whether resources and tracking are accurate, and what the next most informative authorised step is. Update state and checklists after meaningful findings or changes.
>
> Keep the monitors active while authorised work continues across sessions. Stop owned timers and watchers cleanly when the programme is complete.

**Owner instruction, 2026-11-01 (after the Amendment 4 programme): anchor-allocation study (A3), initialization calibration and four-branch pilot; 130M incremental.** Recorded verbatim.

> Proceed autonomously with the research programme below. Continue across sessions and into tomorrow if needed. There is no fixed wall-time deadline.
>
> Your role is to make and execute sound research decisions within this authorization. Do not stop after one experiment merely because its result is negative or inconclusive. Follow the full programme, including the condition-calibration pilot and scientific synthesis, unless a validity problem or budget constraint makes a phase unjustified.
>
> Equally, do not generate experiments simply to occupy time. Complete the authorised scientific objectives and then report.
>
> Read `agent.md`, `project.md`, the manuscript excluding Preliminary experiments, the latest protocol and amendments, STATE, DECISIONS, FINDINGS, and REPORT.
>
> Preserve all closed-study results. The original mixed-preservation replication is finished. This programme asks new questions about anchor-state allocation, penalty strength, and the experimental regimes needed to study access versus competence.
>
> ## 1. Research objectives
>
> Address these questions in order:
>
> 1. Does suffix-only preservation improve normal-start success on independent training seeds?
> 2. If it helps, does the advantage reflect anchor-state allocation, a weaker overall coefficient, or both?
> 3. Does adding the prefix component reduce the benefit of the suffix component?
> 4. Do any effects persist from approximately 250k to 500k training actions?
> 5. Does the current initialization procedure provide genuinely high boundary-entry competence with low stage access?
> 6. Under a deliberately calibrated but independently selected regime, do reset assistance, suffix preservation, or their combination help?
>
> These are RQ1 and measurement questions. RQ2 intervention selection remains conditional on evidence of useful, reproducible differences across conditions.
>
> Do not treat “close this tested configuration” as “close the entire research question.”
>
> ## 2. Authority, resources and budget
>
> This authorizes:
>
> - Source inspection and focused correctness checks.
> - Analysis and interpretation corrections.
> - A new fixed-size anchor-allocation study.
> - A finite initialization-calibration study.
> - A small four-branch pilot in the calibrated regime.
> - Reproducible reporting and research planning.
>
> Resource limits remain:
>
> - Four CPU cores.
> - 6 GiB memory.
> - One experiment job at a time.
> - Native CPU/MPS under the monitored runner.
> - No paid or remote compute.
>
> The new hard incremental budget is **130M environment actions**, including generation, tests, training, diagnostics, evaluation, failures and retries.
>
> Record the exact starting ledger. Do not add unused allowances from earlier programmes.
>
> Planning allocation:
>
> - Approximately 3M for diagnostics, validation and preparation.
> - Approximately 100M for the main five-arm study.
> - Up to 15M for condition calibration and its four-branch pilot.
> - Protect approximately 12M for audit, failures and completion costs.
>
> These are planning allocations. The 130M total is binding. Protect completion of admitted fixed experiments before spending on optional work.
>
> Before every batch, reserve conservative costs for unfinished commitments, required final evaluation and audit. Include active jobs and failures already incurred. A submission stop line alone is insufficient.
>
> If the complete plan cannot fit, reduce low-value diagnostic overhead or omit a development phase for a documented budget reason. Do not change the fixed sample size after viewing outcomes.
>
> No additional approval is required for routine implementation, debugging, profiling or choices explicitly delegated below.
>
> ## 3. Perform a focused scientific and implementation audit
>
> Do not repeat every historical audit. Check the issues relevant to the new programme.
>
> ### Interpretation corrections
>
> Preserve R2’s frozen verdict and uncertainty.
>
> Replace “not a power failure” with a precise statement about achieved uncertainty: the interval is sufficiently narrow to constrain effects of the originally motivating size under the tested protocol.
>
> Do not interpret the difference between R1’s original and repeated evaluations as an identified proportion of noise. Both evaluations have sampling error.
>
> Do not claim that the cross-panel study proves panels are irrelevant. Describe the cohort and panel contrasts with their uncertainty.
>
> Remove the claim that suffix-only benefit conflicts logically with a null mixed arm. Loss components add at a fixed parameter vector; learned outcomes need not add after nonlinear optimization.
>
> Review the literature already cited in the manuscript, especially forgetting mitigation and state-selective preservation. Explain what this study adds beyond established retention methods.
>
> ### Implementation checks
>
> For the component code, verify:
>
> - Stage labels and anchor membership.
> - Sampling probabilities and normalization.
> - Actual loss coefficients.
> - Teacher identity and detached teacher probabilities.
> - Forward categorical KL implementation.
> - Actor/critic parameter separation.
> - Independent anchor, action, permutation and start-sampler RNG streams.
> - Complete fork and checkpoint state.
> - No hidden change in PPO, reward or episode horizon.
>
> Test both scalar loss and gradients on fixed states and parameters.
>
> Verify that the full penalty equals the sum of its prefix and suffix terms before optimization.
>
> If a defect is found, identify which earlier results it affects. Do not silently repair the code and continue presenting incompatible results as one study.
>
> Do not delay new research for cosmetic historical corrections.
>
> ## 4. Main study: anchor allocation and coefficient controls
>
> Call this a new study, with its own protocol and provenance.
>
> Use:
>
> - K=3.
> - Early BC at 4,000 updates.
> - **24 fresh training seeds, 43–66.**
> - The unchanged joint BC dataset and sampler.
> - The existing architecture, critic preparation and PPO probe.
> - Normal starts in every arm.
> - No demonstration resets.
> - Original episode horizons and binary terminal reward.
> - Original BC checkpoint as the preservation reference.
>
> Train five branches from each complete post-probe fork:
>
> A. Ordinary PPO.
>
> B. Prefix component only.
>
> C. Suffix component only.
>
> D. Original full mixed penalty.
>
> E. Uniformly weakened mixed penalty.
>
> The expected losses must be:
>
> A: 0.
>
> B: 0.0025 × E_prefix[KL].
>
> C: 0.0075 × E_suffix[KL].
>
> D: 0.0025 × E_prefix[KL] + 0.0075 × E_suffix[KL].
>
> E: 0.001875 × E_prefix[KL] + 0.005625 × E_suffix[KL].
>
> E is 0.75 times the original full penalty. Its total scalar coefficient matches the suffix-only coefficient, but its actual gradient strength need not match. Label this limitation.
>
> ### Avoid double weighting
>
> If using the existing mixed anchor sampler with 25% prefix and 75% suffix:
>
> - B, C and D use the original base coefficient 0.01.
> - Mask removed rows and retain the original full-batch denominator.
> - E uses base coefficient 0.0075 with both components.
>
> Do not pass coefficient 0.0075 to an already 75%-weighted suffix-only estimator and accidentally obtain an effective coefficient of 0.005625.
>
> Record both configuration values and effective expected coefficients.
>
> Preserve the original estimator and sampling variability. Do not renormalize surviving rows.
>
> ## 5. Training endpoints and evaluation
>
> Run every main-study branch to **501,760 continuation actions**.
>
> Save complete states at:
>
> - 251,904 actions.
> - 501,760 actions.
>
> The confirmatory primary endpoint is **251,904**, because that is where the exploratory suffix-only signal arose.
>
> The 501,760 endpoint is a prespecified secondary assessment of persistence. Do not move the primary endpoint according to which result is favorable.
>
> The full training matrix contains:
>
> 24 seeds × 5 arms = 120 branches.
>
> Continuation training alone requires approximately 60.21M actions. Account separately for preparation and evaluation.
>
> Use fresh roles for:
>
> - Diagnostics.
> - Competence bank.
> - Final normal-start evaluation.
>
> Verify disjointness from all earlier evaluation roles and preserve unchanged training data.
>
> At both endpoints evaluate:
>
> - 128 layouts × 4 independent stochastic normal-start attempts.
> - A fixed 64-state competence bank × 4 attempts.
> - Separate entry, retrieval and carrying scores.
> - The original weighted mixed-bank score.
>
> Use common layouts and attempt schedules across arms and seeds. Keep the bank fixed across policies and time points.
>
> Avoid automatic extra evaluations at every saved checkpoint. Save states cheaply; execute evaluation only when specified.
>
> ## 6. Freeze inference before outcomes
>
> Primary hypothesis:
>
> Does suffix-only preservation improve mean normal-start P1 versus ordinary PPO at 251,904 actions?
>
> For each seed:
>
> d_suffix = P1(C) − P1(A).
>
> Use one two-sided paired test at alpha=0.05, a 95% interval, and the training seed as the independent replicate.
>
> Use a prespecified gatekeeping procedure:
>
> - First test C versus A.
> - Only if that primary hypothesis is supported, test the secondary comparison family C versus D and C versus E, using Holm over those two tests.
> - Otherwise, report those comparisons as descriptive.
>
> Freeze and test the implementation of this procedure before outcomes. Do not change the hierarchy after results.
>
> Other contrasts are secondary:
>
> - B−A.
> - D−A.
> - E−A.
> - D−C: adding the prefix term when suffix preservation is present.
> - B−A: adding the prefix term without suffix preservation.
> - Interaction: D−B−C+A.
> - Corresponding stage measurements and 500k effects.
>
> A positive C−D without positive C−A could mean the mixed penalty is harmful. It does not establish a useful suffix-only method.
>
> A suffix-only advantage over E would support a role for state allocation beyond the tested uniform coefficient reduction. It would not establish exactly matched gradient strength.
>
> Use paired seed-level inference and crossed seed/layout bootstrap sensitivity. Do not treat episodes, endpoints, states or checkpoints as training replicates.
>
> Plan precision using plausible SDs, including 0.03, 0.05, 0.07 and 0.08. Do not use the three-seed exploratory SD of about 0.008 as the main planning assumption.
>
> Keep all 24 seeds. No significance-driven early stopping, sample extension, seed replacement, or endpoint selection.
>
> Do not pool earlier exploratory studies into the primary analysis.
>
> ## 7. Execute and monitor the main study
>
> Run one planned seed as an engineering canary. Check:
>
> - Resolved losses and coefficients.
> - Fork hashes.
> - Counters and role identities.
> - Telemetry and resource safeguards.
> - Numerical validity.
> - Output schemas and resumability.
>
> Do not use its performance to change the design.
>
> Balance branch order across seeds. Preserve full actor, critic, optimizer, teacher, RNG, environment, sampler and counter state.
>
> Do not inspect aggregate confirmatory statistics until all 24 seeds are complete. Monitor execution health and numerical validity.
>
> Record per-stage anchor KL, applied penalty and actual policy-update size. If computing gradient diagnostics, use contemporaneous states and batches, preserve RNG state, and avoid changing optimization.
>
> Do not compute PPO gradients from stale rollouts and present them as the gradients that drove training.
>
> The main study should proceed to its fixed conclusion even if individual seeds look poor.
>
> ## 8. Interpret anchor interactions correctly
>
> The following are different findings:
>
> - Suffix-only improves P1.
> - Removing the prefix term improves P1.
> - Uniformly reducing the penalty improves P1.
> - The prefix and suffix terms interact.
> - A particular skill is retained.
> - Retention causes the performance gain.
>
> Do not substitute one for another.
>
> The prefix and suffix losses act through shared parameters. A prefix-state constraint can affect suffix behavior and vice versa.
>
> A weak change in average prefix KL does not prove the prefix term has no behavioral effect. Conversely, a gradient or KL change does not establish useful skill preservation.
>
> Report per-seed effects, uncertainty, stage behavior and optimizer activity. Use the full control set to narrow explanations.
>
> Keep any mechanism claim proportionate to the experimental manipulation.
>
> ## 9. Proceed to condition calibration without waiting for another instruction
>
> This phase addresses whether the initialization procedure supplies the regimes required by the manuscript.
>
> It remains useful whether or not suffix-only preservation succeeds in the main study. Do not stop the whole programme after the main p-value.
>
> Use the existing task family, model, reward, horizon and joint demonstration dataset. Do not redesign the environment to produce a preferred intervention winner.
>
> Use three new development seeds: **67–69**.
>
> Train BC with three prespecified prefix-sampling probabilities within each K:
>
> - 0.2.
> - 0.5.
> - 0.8.
>
> Keep K-balanced sampling. Within the selected stage, sample demonstrations consistently. Keep total batch size, optimizer and architecture fixed.
>
> Save checkpoints at 4,000 and 8,000 updates along each training path.
>
> This changes the supervised training procedure, representations and behavior. It is not a pure manipulation of initial competence.
>
> Evaluate initial normal-start p/q and **boundary-entry competence**, with separate later-progress scores.
>
> Use development roles and a fixed evaluation plan. Do not inspect intervention outcomes to choose a condition.
>
> ### Calibration target
>
> Prefer one sampler/checkpoint variant, shared across K, that produces:
>
> - K=1: access approximately 0.75 or higher.
> - K=3: access approximately 0.05–0.40.
> - Boundary-entry competence approximately 0.55 or higher in both.
> - Remaining room for full-task learning.
>
> Use these as development feasibility targets, not confirmation claims.
>
> Choose among qualifying variants by a rule fixed before training: prefer fewer BC updates, then the sampling probability closest to 0.5, with a fixed tie-break.
>
> Retain all three seeds. Do not drop a weak seed to make a candidate qualify.
>
> Do not choose a regime because ordinary PPO forgets or an intervention wins. Record competence decline if observed; do not require it.
>
> If no variant satisfies the targets, report that clearly. Do not silently relax them or start an unbounded grid search. Produce a concrete account of what prevents the desired regime.
>
> ## 10. Four-branch pilot in the calibrated regime
>
> If calibration produces a suitable shared initialization and the conservative cost fits the 15M development allocation, run this pilot autonomously.
>
> Use:
>
> - The selected BC sampler/checkpoint.
> - K=1 and K=3.
> - All three calibration seeds.
> - A common ordinary-PPO probe.
> - Four post-probe branches per condition.
>
> Branches:
>
> 1. Ordinary PPO.
> 2. Demonstration-state starts with alpha=0.25.
> 3. Suffix-only preservation with effective coefficient 0.0075.
> 4. Both interventions.
>
> Use original demonstration reset states and original remaining times. Keep the reward terminal-only.
>
> Copy complete post-probe state into branches. Use the same interaction allowance and PPO settings.
>
> Run 251,904 continuation actions per branch. The 24 branches require approximately 6.04M continuation actions before evaluation.
>
> Freeze the pilot configuration and evaluation before outcomes.
>
> Measure:
>
> - Normal-start P1 and access.
> - Fixed-bank entry competence and later-progress scores.
> - Change from pi0 and the probe.
> - Actual arrival-conditioned completion.
> - Arrival timing and inventory.
> - Normal versus assisted visitation and success.
> - Intervention activity and compute.
>
> Do not pool assisted training access with normal-start access.
>
> This pilot is exploratory. Three seeds and two conditions do not establish a general intervention-selection rule.
>
> Do not retune alpha or the preservation coefficient during it.
>
> ## 11. Connect all results to the original research questions
>
> For RQ1, distinguish:
>
> - The original mixed penalty’s small average effect.
> - Whether suffix targeting changes intervention value.
> - Whether coefficient reduction explains apparent targeting gains.
> - Whether intervention effects depend on initial access and genuine entry competence.
> - Whether resets and preservation substitute for or complement each other.
>
> For RQ2, do not train a selector merely because data are available.
>
> Assess:
>
> - Reproducible variation in intervention benefits.
> - Hindsight headroom above the best fixed method.
> - Performance of a simple condition-identity rule.
> - Additional value plausibly available from q, entry competence and delta-c.
> - Measurement and trial costs.
>
> New BC variants and repeated training seeds are not automatically held-out task conditions.
>
> If one fixed method works as well, state that. If the current data do not justify selection, preserve RQ2 as a future question.
>
> Read the relevant primary literature when assessing novelty. State-selective retention and reset assistance are established ideas. The contribution must be the controlled evidence or useful decision procedure.
>
> ## 12. Correct the measurement and cross-study narrative
>
> Retain R2’s actual effect estimate and uncertainty. Do not call the method universally ineffective.
>
> For cross-panel results:
>
> - Describe cohort and panel differences with intervals.
> - Treat repeated evaluation as another noisy measurement.
> - Do not claim that an exact fraction of the original estimate was noise.
> - Do not claim that panel effects are absent merely because a contrast is non-significant.
>
> For access and competence:
>
> - Keep p=q×r distinct from fixed-bank c.
> - Compare entry with entry before invoking state-distribution mismatch.
> - Preserve original clocks.
> - Keep different evaluation layout sets separate.
> - Report the arithmetic decomposition without calling it mediation.
> - Keep missing conditional statistics missing.
>
> A valid negative result can identify a poor regime for testing the motivating hypothesis. It does not automatically reject the research direction.
>
> ## 13. Maintain durable autonomous operation
>
> There is no overnight or calendar cutoff. Continue authorised work across sessions until the programme is complete or a genuine constraint binds.
>
> Use the resource-controlled runner for heavy tests, generation, analysis, training and evaluation.
>
> Maintain deterministic monitoring. Wake the agent for meaningful events, not unchanged logs.
>
> Perform two-hour research reviews. During a frozen study, reviews may address execution and validity; they must not change the design based on emerging effects.
>
> After each phase, update the scientific state and make the next authorised step concrete. Do not return to “nothing authorised” while a later phase remains feasible under this instruction.
>
> If a phase is blocked, identify the exact blocker and continue independent authorised work. Do not ask routine engineering questions that repository evidence can resolve.
>
> Do not increase the total budget, alter resource limits, start another task domain, or introduce paid compute.
>
> Do not spend actions merely to extend the duration of the programme.
>
> ## 14. Verification and reporting
>
> Independently recompute the main results from raw attempts. Verify:
>
> - Complete seed/arm/endpoint inventory.
> - Loss coefficients and sampling semantics.
> - Fork and checkpoint lineage.
> - Data-role separation.
> - Metric formulas, weighting and denominators.
> - Missing and failed records.
> - Action counts and conservative estimates.
> - Analysis provenance and deviations.
>
> Do not equate a passing test suite with scientific validation.
>
> Maintain one consolidated report with clearly separated:
>
> - Historical closed studies.
> - Main-study confirmatory findings.
> - Prespecified secondary findings.
> - Development calibration.
> - Exploratory pilot.
> - Remaining hypotheses.
>
> Generate reproducible figures for:
>
> - Paired arm effects at both endpoints.
> - Prefix/suffix component contrasts.
> - Penalty and policy-change diagnostics.
> - Initial access versus boundary-entry competence.
> - Four-branch pilot effects.
>
> Include every seed and uncertainty appropriate to its role. Avoid a plot for every logged quantity.
>
> Finish with a decisive research recommendation grounded in what was learned. Possible outcomes include retaining a simpler fixed intervention, pursuing state allocation, revising the task regime, or concluding that this setup does not support cost-effective selection.
>
> Do not automatically schedule another replication after a disappointing result.
>
> ## 15. Record the programme and restart sustained monitoring
>
> Before launching work:
>
> 1. Read and reconcile these instructions with the evidence and manuscript.
> 2. Add them as a dated owner amendment in the authoritative `project.md`.
> 3. Identify superseded stop instructions while preserving closed-study verdicts.
> 4. Record the incremental budget, phase rules and interpretation constraints in DECISIONS.
> 5. Update STATE with the active objectives and uncertainties.
> 6. Update CHECKLIST with the complete dependency-aware programme, including later phases and audits.
> 7. Write the scientific rationale and expected discrimination for each phase.
> 8. Commit the relevant protocol, code and configuration before execution.
> 9. Verify existing monitor identities and avoid duplicates.
> 10. Restart the battery safeguards, deterministic batch watchers and two-hour introspection loop.
>
> Persist progress, next-review times and recovery instructions so work can continue after a context reset.
>
> Proceed without another routine approval. Stop owned monitors cleanly only when the programme is complete, a safety/resource condition requires it, or I instruct you to stop.

*Agent note (2026-11-01):* this instruction supersedes the completion stop of the Amendment 4 programme ("Stop owned timers and watchers cleanly when the programme is complete") and the "no further scientific execution / close the RQ1 line" recommendation in REPORT P8 as a stop rule. All closed-study verdicts (M4 F10, R1 F12, R2 F14) and the E1/E2 records are preserved. The 50M Amendment 4 budget is closed; its unused 10.36M is not added.

## Owner instruction 2026-11-01c (verbatim): calibrated-initialization long-budget study; battery rule 31%

> Continue autonomously with the focused programme below. Read the latest report, findings, protocol, decisions, state, `agent.md`, `project.md`, and the manuscript excluding Preliminary experiments.
>
> Preserve all completed-study verdicts. This is a new study of the calibrated initialization and a longer training budget. Do not reopen earlier replications or repeat the five-arm allocation study.
>
> ## 1. Update battery protection before substantial work
>
> Replace the previous 20% battery rule with:
>
> **Stop scientific execution when reported battery charge reaches 31% or lower.**
>
> This applies even if the machine reports AC power. Do not interpret “31%” as remaining runtime or a percentage of the original charge.
>
> Implement and verify the following:
>
> - Read battery state before admitting any heavy job.
> - Poll battery approximately every 15 seconds while work is active.
> - At or below 31%, immediately stop new submissions and request a checkpoint-and-pause of active work.
> - Stop submitting new GPU work while checkpointing.
> - Allow only a short, bounded shutdown grace period, then stop remaining owned workers safely.
> - If the recent discharge rate indicates that the next safe checkpoint could cross 31%, begin pausing earlier.
> - If battery readings become unavailable, pause admission and retry a lightweight reading. Do not assume sufficient charge.
> - Do not shut down the computer or change global power settings.
>
> Persist a battery-pause flag that every driver, launcher and fallback wakeup respects. Charging or recovering above 31% must not restart experiments automatically. Wait for my explicit instruction to resume.
>
> At the battery stop:
>
> 1. Save complete recoverable state.
> 2. Record actual action consumption and any work lost since the last checkpoint.
> 3. Update STATE and CHECKLIST with the precise resume point.
> 4. Stop owned training, evaluation, drivers and review wakeups.
> 5. Report that work paused because of the battery threshold.
>
> A battery interruption must not be marked as successful completion. Completion requires the planned action allowance and required evaluation artifacts, not merely exit code zero or an intermediate summary file.
>
> Test the guard using simulated readings around the threshold, including 32%, 31%, 30%, missing readings and AC power. Do not drain the real battery to test it.
>
> Update every active configuration and instruction that still says “below 20%.” Preserve historical records as historical.
>
> ## 2. Scope and resources
>
> Research question:
>
> In the calibrated K=3 initialization, does suffix preservation improve normal-start success after a substantially longer training allowance, and does its benefit increase relative to the 250k checkpoint?
>
> Use:
>
> - K=3 only.
> - BC prefix-sampling probability rho=0.2.
> - BC checkpoint at 8,000 updates.
> - Twenty fresh training seeds: **70–89**.
> - Ordinary PPO versus suffix-only preservation.
> - Normal starts in both arms: alpha=0.
> - The existing suffix-preservation estimator, with effective coefficient 0.0075.
> - The original BC checkpoint as the reference.
> - The unchanged task, architecture, reward, episode horizon, PPO settings, critic preparation and probe.
>
> Keep BC training on the unchanged joint K=1/K=3 dataset. Restrict this study’s online training to K=3.
>
> Do not introduce resets, stronger penalties, new architectures, extra BC variants or reward shaping.
>
> Resource limits remain four CPU cores, 6 GiB, one experiment job, and monitored native CPU/MPS. No paid or remote compute.
>
> I authorize **up to 70M additional environment actions**, including preparation, tests, diagnostics, training, evaluation, failures and retries. Record the starting ledger; do not carry unused previous allowances into this authorization.
>
> Protect approximately 8M for failures, validation and completion costs. Recompute conservative admission costs before execution. If the fixed study cannot fit, report the specific problem rather than silently reducing seeds.
>
> There is no wall-time deadline. The battery rule overrides continued execution.
>
> ## 3. Correct the interpretation before the new study
>
> Make a focused pass through the latest conclusions.
>
> Retain A3’s prespecified supported result, while stating that its crossed seed/layout interval includes zero. Distinguish evidence conditional on the evaluated panel from broader layout uncertainty.
>
> Replace categorical wording such as “restricting the penalty adds nothing” with the supported statement: no superiority of suffix restriction was demonstrated at the tested strengths. The prefix-only manipulation was weak.
>
> Distinguish saturated K=1 access from saturated success. Access near one is a ceiling for q; P1 near 0.71 still leaves room for improvement.
>
> In the calibrated pilot, fixed-bank competence improved without a resolved normal-start effect. That does not establish that transfer will occur with more training. The new study tests that possibility.
>
> Do not attribute performance changes causally to a specific skill from the access/completion decomposition.
>
> Do not repeat broad historical audits unless a concrete discrepancy requires them.
>
> ## 4. Freeze the new protocol before new outcomes
>
> Train both branches to **1,001,472 continuation actions**, subject to confirming the exact rollout quantization.
>
> Save complete states and evaluate at:
>
> - 251,904 actions.
> - 501,760 actions.
> - 1,001,472 actions.
>
> The primary endpoint is 1,001,472. The earlier endpoints provide a prespecified trajectory assessment.
>
> Twenty seeds × two branches require approximately 40.06M continuation actions, before preparation and evaluation.
>
> For every seed:
>
> 1. Train the fixed BC initialization.
> 2. Run the unchanged critic preparation and PPO probe.
> 3. Copy complete post-probe state into both arms.
> 4. Train both branches under identical action allowances and optimization settings.
> 5. Preserve full lineage, counters and recoverable states.
>
> Do not filter seeds according to whether they meet the original calibration targets. The selected initialization qualified on three-seed means and was fragile.
>
> Report the new cohort’s initial q and boundary-entry competence distribution. If it does not reproduce the intended profile, describe the study as testing the fixed rho=0.2/8k procedure; do not claim that every replicate represents high competence with low access.
>
> ## 5. Use fresh, appropriately matched evaluation
>
> Generate new diagnostic, competence-bank and final roles. Preserve unchanged training data and verify separation from all prior evaluation roles.
>
> For normal-start evaluation, use **256 fresh layouts × 2 independent stochastic attempts** per policy at each endpoint.
>
> This retains 512 attempts while increasing layout coverage. Use common layouts and attempt schedules across arms, seeds and endpoints.
>
> P1 is primary. Do not compute C4 or R4 from two attempts using a plug-in shortcut.
>
> For fixed-state competence, prioritize boundary entry:
>
> - 128 valid planner-derived entry states × 2 attempts.
> - Original remaining time retained.
> - The same bank for pi0, the probe and all trained policies.
> - Separate labels for this bank and the historical mixed-progress bank.
>
> If retaining retrieval/carrying diagnostics, report them separately and budget them explicitly. Do not inflate boundary competence through progress mixing.
>
> Use diagnostic layouts for early normal-start measurements. Do not difference scores from different layout roles as a learning estimate.
>
> ## 6. Add a fixed actual-arrival diagnostic
>
> Use existing calibrated development policies as bank-generating policies, not newly selected winning policies.
>
> Create a modest common bank of genuine first-crossing states on fresh diagnostic donor layouts:
>
> - Fix the source-policy mixture and sampling rule before collection.
> - Do not select states according to eventual success.
> - Preserve original clocks and all simulator state.
> - Keep the bank separate from training anchors and final normal-start layouts.
> - Freeze the bank before examining the new study’s outcomes.
>
> Evaluate pi0, the probe and final policies on this common bank, within budget.
>
> This asks whether gains on planner entry states also appear on a fixed distribution of naturally reached states. It does not make that bank representative of every policy’s arrival distribution.
>
> Cap collection in advance. If arrivals are insufficient, report the sample limitation rather than collecting until a favorable result appears.
>
> ## 7. Prespecify statistical decisions
>
> For seed i and endpoint t:
>
> d_i(t) = P1(preservation_i,t) − P1(ordinary_i,t).
>
> Primary hypothesis:
>
> Is the mean d_i at 1,001,472 different from zero?
>
> Use a two-sided paired test at alpha=0.05 and its 95% interval. Training seed is the replicate, n=20.
>
> Use a fixed hierarchy:
>
> - First test the primary final-endpoint effect.
> - Only if supported, test whether d_i(1,001,472) − d_i(251,904) differs from zero, using a two-sided paired test at alpha=0.05.
> - Otherwise, the change across time is descriptive.
>
> Only describe an increasing treatment benefit as supported if the corresponding time comparison supports it. Significance at one endpoint and non-significance at another is insufficient.
>
> Report crossed seed/layout bootstrap and sign-flip sensitivity analyses, with their assumptions. Preserve all pairing.
>
> Provide planning scenarios over plausible effect SDs. Do not promise power from the three-seed pilot. Report uncertainty relative to zero, 0.03 and 0.05 without silently changing earlier studies’ margins.
>
> The formal analysis uses new-study data only. Do not pool previous studies into its primary test.
>
> Keep all twenty seeds. No interim significance stopping, sample-size extension, endpoint substitution or favorable-seed selection.
>
> ## 8. Keep the access/competence interpretation rigorous
>
> At each endpoint report:
>
> - Normal-start p and q.
> - Completion conditional on actual arrival, r.
> - Fixed planner-entry competence.
> - Fixed actual-arrival-bank competence.
> - Changes from pi0 and the probe on the same states.
> - Arrival timing and inventory.
> - Anchor KL and intervention activity.
> - Training visitation and successful-return exposure.
>
> Compute the per-seed descriptive decomposition:
>
> Δp = Δq × (r1+r0)/2 + Δr × (q1+q0)/2.
>
> Do not substitute bank competence for r or call this mediation. Keep undefined quantities missing.
>
> Distinguish these outcomes:
>
> - Bank competence improves and normal-start success improves.
> - Bank competence improves but normal-start success remains unresolved.
> - Only planner-bank competence improves.
> - Ordinary PPO catches up with preservation.
> - Preservation constrains later adaptation.
>
> Do not infer a unique explanation from any single pattern. In particular, a later P1 gain alone does not prove that improved fixed-bank competence caused it.
>
> ## 9. Ensure battery-safe execution and recovery
>
> Run relevant checks for:
>
> - The inclusive 31% guard.
> - Atomic heartbeat/checkpoint writes.
> - Complete state restoration.
> - Graceful interruption.
> - Correct paused-versus-complete status.
> - Accurate partial-run accounting.
>
> Use periodic recovery checkpoints, retaining the latest recoverable states and scientific endpoints without accumulating unnecessary copies.
>
> If exact resumption is unavailable, document the limitation and restart from a valid complete input under a new run ID. Count all consumed actions, retain the interrupted record, and keep the planned seed.
>
> Do not let a fallback driver, review timer or automatic retry restart a battery-paused campaign.
>
> Use deterministic monitoring and two-hour research reviews while work is active. Reviews may address validity, resources and execution; they may not alter the frozen design based on emerging effects.
>
> ## 10. Reporting and completion
>
> Independently recompute primary results and stage metrics from raw records.
>
> The final report must contain:
>
> - All twenty paired seed results.
> - Final-endpoint inference and layout sensitivity.
> - The prespecified treatment-by-time comparison.
> - Initial calibration stability across fresh seeds.
> - Planner-entry versus fixed actual-arrival competence.
> - Access/completion analysis and its limitations.
> - Actual and estimated costs, failures and interruptions.
> - A decisive recommendation.
>
> If the longer study still gives no useful normal-start benefit, do not automatically extend training or add seeds. Write up the controlled result.
>
> If it finds a benefit, state its magnitude, time dependence and scope. Do not jump to an RQ2 selector without evidence that condition-dependent selection can beat a fixed intervention after costs.
>
> Before starting:
>
> 1. Record this instruction as a dated project amendment.
> 2. Update the active battery rule to **31% or lower**.
> 3. Update DECISIONS, STATE and the dependency-aware CHECKLIST.
> 4. Freeze the protocol, configurations and analysis.
> 5. Verify that no duplicate monitors exist.
> 6. Restart battery protection and the two-hour review loop.
> 7. Execute without another routine approval.
>
> At 31% or lower, checkpoint, stop, record the resume point and wait. Do not restart automatically when power conditions improve.

*Agent note (2026-11-01c):* from this instruction on, the active battery rule is: stop scientific execution when the reported charge is 31% or lower, even on AC power. Every earlier "below 20%" battery rule in this file is superseded and kept only as a historical record. The verdicts of all completed studies are preserved.

## Owner instruction 2026-11-02 (verbatim; access-focused programme, RQ1)

> Continue with the access-focused programme below. Do not extend A4 or repeat preservation-only experiments.
>
> Read the latest report, findings, decisions, protocol, STATE, `agent.md`, `project.md`, and the manuscript excluding Preliminary experiments. Preserve all completed-study verdicts.
>
> The new question is:
>
> Can the placement and ordering of demonstration-state starts improve learning of the prerequisite sequence and normal-start success, while retaining useful later-stage competence?
>
> This is an RQ1 study. Do not build an RQ2 selector.
>
> ## 1. Authority, resources and battery protection
>
> You may perform the diagnostics, development pilot, conditional independent confirmation, verification and reporting specified below without another routine approval.
>
> Keep:
>
> - Four CPU cores.
> - 6 GiB memory.
> - One experiment job at a time.
> - Native CPU/MPS through the monitored runner.
> - No paid or remote compute.
> - No wall-time deadline.
>
> New hard incremental budget: **70M environment actions**.
>
> Planning allocation:
>
> - Up to 2M for diagnostics and preparation.
> - Up to 24M for the development pilot.
> - Up to 36M for conditional confirmation.
> - Protect 8M for failures, audit and completion costs.
>
> Record the starting ledger. Do not carry unused earlier allowances into this budget. Before every submission, reserve the conservative cost of unfinished work and mandatory evaluation.
>
> Keep the battery rule unchanged:
>
> **At 31% or lower, stop new admissions, checkpoint and stop active work, record the resume point, and wait. Do not restart automatically when charging resumes.**
>
> Start and verify the battery guard before heavy work. Keep the persistent battery-pause flag respected by every driver and fallback process. A paused run is not complete.
>
> Restart deterministic monitoring and two-hour research reviews. Do not create duplicate monitors.
>
> ## 2. Correct the remaining interpretation issues
>
> A4's primary comparison is valid as reported. Do not alter it.
>
> Check the longitudinal claims separately:
>
> - Do not compare the post-probe median on diagnostic layouts with the final mean on another panel as an exact learning gain.
> - Quantify learning from endpoints evaluated on the same layout panel, using consistent weighting and summary statistics.
> - Recompute the access/completion decomposition for that within-panel learning change.
>
> Distinguish failure accounting from causal attribution. The fraction of failures occurring before the boundary does not prove that a particular access intervention will recover them.
>
> Do not use the "3/20 met all calibration targets" statement as an excuse to dismiss A4. Most failures of the full profile concerned K=1, while A4 trained online only at K=3. Report the relevant K=3 targets separately.
>
> Retain the conclusion that preservation may offer a small early advantage, but its tested long-budget benefit is unresolved and bounded.
>
> ## 3. Diagnose the remaining failures before new training
>
> Use existing A4 raw records and a small, predetermined set of frozen ordinary-PPO checkpoints.
>
> Prefer seeds 70–73 at the probe and final checkpoint. Choose them by this fixed rule, not performance.
>
> Produce:
>
> - Failure before boundary.
> - Arrival followed by failure.
> - Success.
> - Arrival times and remaining-time distributions.
> - Progress through individual prerequisite rooms.
> - Inventory and door-state errors.
> - Repeated actions or navigation loops.
> - Deadline failures.
>
> Where existing records lack traces, collect a bounded diagnostic sample on separate layouts. Do not regenerate the whole evaluation suite.
>
> Add two assisted evaluation references on matched initial layouts:
>
> 1. Planner executes the prefix; the frozen learned policy executes the suffix.
> 2. Learned policy executes the prefix; a validated planner attempts the suffix using the actual arrival state and remaining time.
>
> Count every executed action. Do not refresh clocks or add rewards.
>
> These are diagnostic conditions, not normal-start policy performance. The first changes arrival state and timing; it is not a mathematical upper bound.
>
> For the second, distinguish verified feasible, verified impossible, and unresolved planner searches. A search timeout is not proof of impossibility.
>
> Keep manuscript access q unchanged. You may additionally report "verified finishable access": reaching the boundary with a planner-certified completion still possible within the remaining time.
>
> Use this to distinguish late, unusable arrivals from arrivals where learned continuation fails.
>
> If the diagnostics uncover a correctness defect, resolve its scope before training. If they show no meaningful opportunity for an access intervention, report that rather than spending the pilot budget automatically.
>
> ## 4. Development pilot: compare reset placement
>
> Use six fresh development seeds: **90–95**.
>
> Keep the fixed initialization procedure:
>
> - Joint BC dataset.
> - Prefix-sampling probability rho=0.2.
> - BC checkpoint at 8,000 updates.
> - K=3 online training.
> - Unchanged critic preparation and common PPO probe.
> - Unchanged architecture, reward, episode horizon and PPO settings.
> - No preservation penalty in any branch.
>
> Keep every seed. Do not filter on initial competence or access.
>
> Copy complete post-probe state into four branches:
>
> A. Ordinary PPO.
>
> B. Post-boundary demonstration resets.
>
> C. Static prefix-state demonstration resets.
>
> D. Backward prefix curriculum.
>
> Train each branch for **501,760 continuation actions**.
>
> Use a common assistance schedule for B, C and D:
>
> - Reset probability alpha=0.25 during the first 75% of the action allowance.
> - No new assisted starts during the final 25%.
> - Normal starts remain available throughout.
>
> Allow episodes already in progress to finish normally. Do not create artificial terminations at schedule boundaries.
>
> This shared withdrawal schedule is a new intervention specification. Do not present B as an exact reproduction of the earlier constant-reset arm.
>
> ## 5. Construct the reset banks precisely
>
> B uses the original post-boundary progress mixture and valid demonstration states.
>
> For C and D, construct banks at entry to each prerequisite module, before acquiring that module's required key.
>
> Use valid planner trajectories from training donor layouts. Preserve:
>
> - Full grid and object state.
> - Inventory.
> - Door states.
> - Agent pose.
> - Original elapsed time and remaining time.
> - Task flags and RNG state where relevant.
>
> Do not give the learner the required key artificially. Do not fabricate unreachable states.
>
> C samples uniformly across the three prerequisite-module entry banks.
>
> D follows this fixed schedule:
>
> - First quarter: last prerequisite module.
> - Second quarter: middle prerequisite module.
> - Third quarter: first prerequisite module.
> - Final quarter: normal starts only.
>
> Choose schedules using executed training actions, not success rates. Do not adapt them to outcomes.
>
> Keep bank donors separate from evaluation layouts and competence banks.
>
> Matched reset probability does not imply matched assisted-step fraction: episode lengths differ. Report the actual interaction allocation and stage visitation.
>
> Resets bypass prefix execution. Report generation and computation costs separately from executed training interactions.
>
> ## 6. Freeze pilot evaluation and analysis
>
> Before collecting pilot outcomes, freeze configuration, data roles, schedules, seed list, metrics and selection rule.
>
> Use a common development evaluation panel, initially 64 layouts × 4 normal-start attempts per branch at 251,904 and 501,760 actions.
>
> Use a fixed boundary-entry competence bank, shared across branches and endpoints. Retain original clocks.
>
> Report:
>
> - Normal-start P1.
> - Access q.
> - Verified finishable access, with unresolved cases separate.
> - Arrival-conditioned completion.
> - Fixed-bank entry competence.
> - Arrival timing and inventory.
> - Per-module visitation and completion.
> - Normal versus assisted training episodes and successes.
> - Actual assisted-step fractions.
> - Interaction and compute costs.
>
> Never pool assisted-start success or access with normal-start evaluation.
>
> This is a development comparison. Show every paired seed contrast and uncertainty. Do not call six seeds confirmation or select a best checkpoint per arm.
>
> ## 7. Prespecify the confirmation gate
>
> Choose at most one assistance method for independent confirmation.
>
> A method qualifies only if, at the fixed final pilot endpoint:
>
> - Its mean normal-start P1 advantage over ordinary PPO is at least **0.05**.
> - Its paired advantage is positive in at least **four of six seeds**.
> - Execution and evaluation checks pass.
> - The complete confirmation study fits the remaining budget.
>
> Choose the qualifying method with the highest mean final P1. Within a 0.02 tie, prefer the simpler method in this order: B, C, D.
>
> Record this rule before pilot outcomes.
>
> Access and competence measurements explain the result; they are not additional filters used to choose a favorable story. If performance improves without the expected access change, report that.
>
> If no method qualifies, do not add doses, schedules or seeds. Finish the diagnostic synthesis and propose the next discriminating question without launching it.
>
> ## 8. Conditional independent confirmation
>
> If the gate is met, proceed without another routine approval.
>
> Use:
>
> - Twenty fresh seeds, **96–115**.
> - The same fixed BC initialization.
> - K=3.
> - Ordinary PPO versus the selected assistance method.
> - The exact pilot schedule and reset-bank construction.
> - Primary endpoint: **501,760 continuation actions**.
> - A descriptive checkpoint at 251,904.
>
> Use fresh final layouts and diagnostic roles. Prefer 256 layouts × 2 stochastic attempts for primary P1, with common schedules across policies and seeds.
>
> Do not compute C4/R4 from two attempts.
>
> The sole primary estimand is the mean paired final P1 difference over twenty training seeds. Use one two-sided paired test at alpha=0.05 and its 95% interval.
>
> Report crossed seed/layout bootstrap and sign-flip sensitivity analyses with their assumptions.
>
> Use confirmation data only for the primary test. Do not pool the development pilot into it.
>
> Keep sample size fixed. No interim significance stopping, favorable-seed replacement, schedule changes or endpoint selection.
>
> The target is learning efficiency at a fixed budget. A benefit here would not establish superior converged performance.
>
> ## 9. Preserve rigorous interpretation
>
> Distinguish:
>
> - Improved access.
> - Earlier or more finishable arrivals.
> - Improved continuation from a fixed state distribution.
> - Changed arrival-state distribution.
> - Improved normal-start success.
>
> Do not infer p=q×c for a fixed bank.
>
> Do not describe start-state assistance as isolating exploration: it changes experience, reward exposure, timing and practice together.
>
> This curriculum is an adaptation of established approaches. Do not claim a new algorithm or inherit theoretical guarantees from reverse-curriculum or guide-policy papers.
>
> If one fixed assistance method works broadly, that may weaken the need for diagnostic selection. Do not train a selector without demonstrated headroom and held-out-condition validation.
>
> ## 10. Execution and recovery
>
> Use committed configurations and the resource-controlled runner for every heavy activity.
>
> Run one engineering canary from the planned sample. Inspect hashes, state restoration, schedules, counters and numerical validity. Do not use its performance to retune.
>
> Checkpoint complete training state regularly and on a battery pause. Retain interrupted records and count lost or repeated actions.
>
> Require the full action allowance and final artifacts before marking a branch complete. Exit code zero alone is insufficient.
>
> Respect the existing failure policy. Correctness fixes need affected-run accounting and new run IDs. Valid poor performance is not a failure.
>
> Use deterministic watchers. Two-hour reviews should assess validity, progress, resource use and the next authorised step, without adapting a frozen study to emerging effects.
>
> ## 11. Documentation and completion
>
> Before execution:
>
> 1. Record this as a dated owner amendment.
> 2. Update DECISIONS, STATE and the full dependency-aware CHECKLIST.
> 3. Preserve the closed A4 verdict.
> 4. Record budgets, pilot selection rule and conditional confirmation design.
> 5. Verify the inclusive 31% battery guard and restart monitoring.
>
> Maintain one consolidated report separating diagnostics, development and confirmation.
>
> At completion, provide:
>
> - Failure taxonomy and assisted evaluation references.
> - Pilot results and the exact gate decision.
> - Confirmation results, if run.
> - Access, timing and competence interpretation.
> - All costs, failures, interruptions and exclusions.
> - One decisive recommendation.
>
> Do not extend A4, restart preservation-only tuning, or launch another domain.
>
> At 31% battery or lower, pause safely and wait for my explicit resume instruction. Otherwise, continue through the authorised phases until completion or a genuine budget or validity constraint binds.

*Agent note (2026-11-02):* starting ledger 311,392,581; new hard budget 70M from that ledger; the battery rule (31% or lower) is unchanged.

## Owner instruction 2026-11-02b (verbatim; frozen-policy controller diagnostics, 2M actions)

> Continue as a senior research scientist. Your responsibility is to identify the next informative experiment, preserve the validity of completed studies, and distinguish explanations supported by evidence from plausible stories.
>
> You are authorized to implement and execute the diagnostic programme below autonomously. This is a new authorization, independent of unused previous allowances. Do not reopen the reset pilot or its confirmation.
>
> **1. Reconstruct the scientific position before acting**
>
> Read `mac-agentic-engineering/agent.md`, the applicable repository instructions, current protocol and amendments, FINDINGS, REPORT, DECISIONS, STATE, CHECKLIST, and the latest verification outputs.
>
> Verify the working tree, source versions, checkpoint identities, seed registry, ledger and absence of conflicting workers. Resolve discrepancies against raw records and document corrections before launching new evaluations.
>
> Preserve these conclusions:
>
> - The completed reset-placement pilot did not satisfy its frozen ≥0.05 selection rule. Seeds 96–115 were therefore correctly unused.
> - Backward curriculum’s +0.028 estimate is exploratory, selected from three comparisons, and uncertain. It does not establish either a useful benefit or equivalence.
> - Prior preservation and reset results remain scoped to their tested procedures, task family and training allowances.
> - No cost-effective intervention selector has been established.
>
> Audit the diagnostic interpretation specifically:
>
> - Separate percentages of all attempts from percentages conditional on arrival.
> - Distinguish an arrival that a planner can finish from one the learned policy actually finishes.
> - Report normal success, boundary reach, learned completion conditional on arrival, and planner-certified finishability with explicit denominators.
> - Recompute conditional completion from pooled counts or correctly weighted quantities. Do not multiply or divide unweighted across-seed averages as though they were exact identities.
> - Describe locked-door toggles, repeated poses and wrong-key possession as observed behaviors. They do not independently establish why learning failed. Picking up a nominally wrong key can sometimes serve a legitimate intermediate purpose.
> - Treat planner-prefix success as an assisted reference under changed trajectories and arrival times, not a mathematical upper bound on learner performance.
>
> Correct inconsistent wording throughout the current summaries and state files while preserving the historical record.
>
> **2. Research question and authorized scope**
>
> Investigate:
>
> “On frozen policies, how much normal-start failure can be relieved by correcting key acquisition, correcting navigation and passage through the appropriate door, or preventing physically ineffective actions?”
>
> This is a diagnostic study of augmented controllers. It is not a new demonstration of improved learning.
>
> Authorization:
>
> - Maximum **2,000,000 additional executed environment actions**, including development checks, planner replay, evaluation, failed runs and verification that executes actions.
> - Aim to spend less when the design permits.
> - No new BC or PPO training.
> - No reward changes, longer episode horizons, new reset curricula or additional training seeds.
> - No paid services or remote compute.
> - Retain the existing four-core, 6 GiB, one-job limits. Use native MPS where it benefits supported work and the established soft resource guards.
>
> Unused previous budgets do not carry forward. Do not use time remaining as a reason to invent experiments.
>
> **3. Freeze the design before inspecting outcomes**
>
> Use frozen ordinary-PPO policies from two cohorts:
>
> - A4 final checkpoints, seeds 70–73.
> - Reset-pilot ordinary-PPO final checkpoints, seeds 90–93.
>
> This selection is fixed by seed order, not performance. Analyze cohorts separately because their training histories and allowances differ. These are existing trained policies, not eight fresh training replications.
>
> Generate one fresh diagnostic K=3 layout panel, disjoint from all previously used training, selection and evaluation panels. Start with 64 layouts and two attempt seeds per layout. Use the same panel and attempt identifiers across every controller condition.
>
> Before running outcomes, calculate the conservative action cost using the actual episode horizon, all conditions, planner replay and verification. If necessary, reduce to 32 layouts before seeing results. Do not drop poorly performing policies or controller conditions to fit the budget.
>
> Freeze the panel hashes, controller definitions, analysis code, action accounting, fallback behavior and run manifest in a dated amendment. Commit the executable source before outcome-producing evaluations.
>
> **4. Controller conditions**
>
> Evaluate the following eight conditions:
>
> 1. Unmodified learned policy.
> 2. Key-acquisition assistance in the middle prerequisite module only.
> 3. Door-transition assistance in that module only.
> 4. Both forms of assistance in that module.
> 5. Key-acquisition assistance in every prerequisite module.
> 6. Door-transition assistance in every prerequisite module.
> 7. Both forms in every prerequisite module.
> 8. Physical-action masking during the prefix, followed by the original policy after the boundary.
>
> Define the middle module by its structural index, not by whichever module fails in an observed attempt.
>
> All conditions begin from normal episode starts.
>
> For planner assistance:
>
> - Execute legal environment actions. Do not teleport, replace inventory, unlock doors directly, restore time or omit helper actions from the episode clock.
> - Every helper action consumes the original remaining allowance and counts toward the campaign budget.
> - Key-acquisition assistance begins on first entry into an eligible module when the appropriate key is not held. It performs the required navigation and inventory operations, then returns control immediately after acquiring that key.
> - Door-transition assistance becomes eligible when the matching key is held. It navigates to, opens and passes through the appropriate prerequisite door, then returns control.
> - Limit each assistance type to one activation per eligible module. Record later key loss or backtracking rather than silently supplying repeated rescues.
> - Restrict assistance to the defined prefix subtask. Prevent accidental execution of the suffix or unrelated modules.
> - Define deterministic behavior for unavailable plans, exhausted time and unresolved searches before evaluation. Keep those episodes in the records and distinguish “not assisted,” “unresolved” and “certified impossible.”
> - Replay returned plans to verify validity. Search failure alone is not proof of impossibility.
>
> Key acquisition includes navigation and inventory management; door transition includes navigation and door operation. Do not describe these broad subroutines as pure interventions on key identity or door choice.
>
> Door-only assistance can remain ineligible if the learner never acquires the correct key. Consequently, a null door-only result cannot establish that door behavior is adequate. Report eligibility and actual exposure.
>
> For physical-action masking:
>
> - Use only current observable state and environment action semantics.
> - Mask actions with no permitted physical effect under those semantics, such as a blocked forward movement or an impossible inventory operation, where applicable.
> - Do not use planner distances, future outcomes, the correct target key, or other task-solution knowledge.
> - Keep physically legal wrong-key pickups available.
> - Preserve a nonempty action set and renormalize the frozen policy consistently.
> - Freeze the exact mask rules and test them on representative edge cases.
> - Record the probability mass removed and the actions actually executed.
>
> This masked controller is a new evaluation decision rule. It is not the original learned policy and should not be presented as an implementation correction unless you independently demonstrate an actual implementation bug.
>
> **5. Preserve comparability and auditability**
>
> Keep original episode clocks, observation processing, action semantics and termination rules unchanged.
>
> Use paired evaluation randomness where valid. If sharing random draws, index them by episode and absolute environment step so planner actions do not accidentally shift arbitrary random-number consumption. Document the coupling.
>
> Retain:
>
> - Policy, code, dataset and panel hashes.
> - Episode identifiers and original remaining time.
> - Assistance eligibility, activation, duration and return-to-policy state.
> - Module transitions, key possession, door operations and termination reason.
> - Mask eligibility, removed probability mass and selected action.
> - Boundary arrival state and remaining time.
> - Planner search status, plan verification and all executed-action counts.
>
> Use compact machine-readable records. Save enough state to reproduce representative trajectories without repeatedly dumping large observations.
>
> Add meaningful tests for the new semantics, especially zero remaining time, final-step arrivals, inventory changes, already-open doors, unavailable assistance and budget interruption.
>
> **6. Analysis and interpretation**
>
> Report every condition, not only the strongest one.
>
> For each cohort and policy, report:
>
> - Unassisted baseline success.
> - Assisted-controller normal-start success and its paired difference from baseline.
> - Boundary reach probability.
> - Learned completion conditional on actual arrival.
> - Certified finishable arrival fraction, with its denominator.
> - Assistance activation rate and helper-action fraction.
> - Arrival time and remaining-time distributions.
> - Locked-door toggles, ineffective actions and key-handling events.
>
> For each assistance scope, calculate the joint-versus-single-assistance contrasts and the interaction:
>
> `both − key-only − door-only + baseline`.
>
> Interpret this as interaction between the specified controller modifications, not a unique decomposition of the policy’s internal skills.
>
> Use paired analyses that retain matched layouts and conditions. Report per-policy results and uncertainty over evaluation layouts. If additionally resampling policy seeds, do so within cohorts and acknowledge the small number and fixed selection of policies.
>
> All comparisons are exploratory. Do not turn the largest of eight outcomes into a confirmatory finding. Show the uncertainty and multiplicity clearly.
>
> Inspect a small, predetermined sample of successful and failed trajectories from each relevant category. Use these to explain mechanisms suggested by the quantitative results, while checking for counterexamples.
>
> Ask specifically:
>
> - Does assistance mainly save time, change inventory, prevent a loop, or alter which states the learner encounters?
> - Does key assistance create the eligibility required for door assistance?
> - Does physical masking capture much of the apparent planner benefit?
> - Do the two policy cohorts exhibit the same failure pattern?
> - Do the observations suggest missing demonstration coverage, an ineffective action interface, inadequate exploration, or a combination?
> - Which explanations remain indistinguishable?
>
> A planner-assisted improvement demonstrates an opportunity under that assistance. It does not establish that a trainable intervention will realize the same improvement.
>
> **7. Decide what training would be justified next**
>
> Produce one ranked recommendation, including “close this line” if appropriate.
>
> Use these branches as reasoning guides:
>
> - If physical masking helps materially, propose a properly matched training-and-evaluation comparison with the same action rules for all arms. Any PPO implementation must use the corresponding masked action probabilities.
> - If key-acquisition assistance helps substantially beyond masking, consider targeted demonstration coverage or corrective imitation. Explicitly charge expert queries, new labels and environment interactions. Identify this as a new supervision method.
> - If door-transition assistance helps, identify whether the useful intervention concerns navigation, inventory context or door-operation behavior before proposing training.
> - If only combined assistance helps, investigate complementary errors rather than declaring one isolated bottleneck.
> - If results are inconsistent or small, recommend stopping or a narrowly justified diagnostic clarification.
>
> A ≥0.05 assisted gain may motivate a proposal; it does not automatically authorize training. Consider its uncertainty, helper privileges and implementation cost.
>
> Do not extend the old reset pilot, relax its gate, or run its reserved confirmation.
>
> For the single most defensible proposed training experiment, specify the hypothesis, intervention, matched baseline, information privileges, supervision cost, development/confirmation separation, seed count justification, endpoints, primary metric, multiplicity handling, conservative action cost and stopping rule.
>
> Do not launch that training experiment under this authorization.
>
> **8. Battery protection and introspection**
>
> Before executing substantial work, restart the project-owned battery guard and two-hour review loop after checking for duplicates.
>
> **Stop all project workloads when battery charge reaches 31% or lower, including while connected to AC.**
>
> Poll frequently enough to allow orderly checkpointing and shutdown before crossing the threshold. Do not start a batch whose conservative discharge estimate would consume the margin. If recent discharge estimates are unavailable, use a conservative fallback.
>
> The guard must set a persistent pause flag that every launcher checks. Charging must not clear it or restart experiments automatically. Resume requires my explicit instruction.
>
> Apply resource monitoring to the entire job process tree. Pause on sustained memory pressure or limit violations.
>
> Every two hours, reflect and record:
>
> - What changed in the evidence?
> - Which interpretation could be wrong?
> - Are denominators, clocks, assistance privileges and costs correct?
> - Is the next action likely to resolve an important uncertainty?
> - Are you drifting into tuning around an inconvenient result?
> - Should you continue, simplify or stop?
>
> Reviews may change prospective implementation details with documentation, but must not rewrite frozen outcome rules after observing results.
>
> **9. Completion**
>
> Independently recompute all reported metrics and action totals from raw records through a separate verification path. Distinguish shared upstream data from genuinely independent checks.
>
> Update the project with this instruction and your considered implementation plan. After deep reflection and reconciliation, update STATE, CHECKLIST, DECISIONS, FINDINGS and REPORT. Clearly separate completed evidence, unresolved explanations and proposed future training.
>
> Commit and push according to the established repository workflow. Stop only the monitors and workers you own when the authorized programme is complete or paused.
>
> Return a concise scientific assessment, the full diagnostic comparison table, any deviations, total spend, and one concrete next-study proposal or a reason to close the line.
>
> Begin by updating the project records and state, then restart the battery protection and two-hour introspection loop, freeze the diagnostic design, and execute the authorized work.

*Agent note (2026-11-02b):* starting ledger 328,228,453; new hard budget 2,000,000 executed actions from that ledger; no training; the battery rule (31% or lower) is unchanged.

## Owner instruction 2026-11-02c (verbatim; corrective prefix imitation study, 80M actions)

> Continue autonomously with a controlled study of corrective prefix imitation. Preserve the conclusions of completed studies. Your goal is to determine whether new expert corrections improve unassisted performance, and whether they add value beyond ordinary demonstration replay.
>
> Do not reopen completed preservation or reset studies.
>
> 1. Establish the current state and correct remaining interpretation problems.
>
> Read `mac-agentic-engineering/agent.md`, applicable repository instructions, the protocol and amendments, FINDINGS, REPORT, DECISIONS, STATE, CHECKLIST, and verification records.
>
> Verify source versions, checkpoint identities, seed and layout registries, the action ledger, available resources and absence of conflicting workers.
>
> Before training:
>
> - Compute direct paired key-assistance-versus-masking contrasts from the controller records. Do not infer this comparison by comparing two separate significance tests.
> - Retain both layout-conditional and crossed policy-and-layout intervals. State that the A4 key-only crossed interval includes zero.
> - Reclassify key drops by whether the associated door had already been passed. Dropping an obsolete key can be correct.
> - Keep planner finishability separate from learned completion.
> - Describe planner assistance as changing trajectories, inventory and time use together. It does not isolate one internal skill.
> - Preserve all historical verdicts and label corrections explicitly.
>
> This is a new supervision study. It cannot retroactively establish that the original preservation or reset interventions work.
>
> 2. Authorization and budget.
>
> You may implement, test, run development, apply the frozen selection rule, and automatically run confirmation if that rule passes.
>
> The new ceiling is **80M executed environment actions**. Prior unused allowances do not carry forward.
>
> Protect 8M for verification, interruptions and close-out. Do not submit scientific batches if their conservative cost would take scientific spending above 72M. Reserve spending must be itemized and must not fund additional hypotheses, doses or seeds.
>
> Count BC data generation, probes, training, evaluation, planner replay, smoke tests and failed attempts. Separately record expert queries, labeled states, label reuse, planner compute and wall time. Planner supervision is not free because it consumes no environment actions.
>
> Retain four CPU cores, 6 GiB, one concurrent experiment job and no paid or remote compute. Use native MPS where beneficial, with the established soft resource monitors.
>
> There is no required wall-clock duration. Continue through the authorized stages while useful and safe; do not fill time with extra experiments.
>
> 3. Freeze the experiment before producing development outcomes.
>
> Use K=3 and the fixed rho=0.2, 8,000-update BC procedure, followed by the established shared probe and matched forks.
>
> Allocate six fresh development seeds and twenty separate confirmation seeds from the registry. Do not filter seeds by achieved initialization characteristics.
>
> Use three arms:
>
> - **A: ordinary PPO.**
> - **R: PPO plus imitation replay from the original prefix demonstrations.**
> - **C: PPO plus expert corrections on learner-visited prefix states.**
>
> All arms receive the same environment-action allowance and unchanged PPO settings. R and C use the same auxiliary-loss coefficient, optimizer-step schedule and number of supervised examples per update. Document their sampling differences.
>
> Use 501,760 continuation actions as the primary endpoint. Evaluate at 251,904 descriptively. Do not extend training after seeing results.
>
> Use separate development and confirmation panels. The confirmation panel should contain 256 fresh layouts with two attempts each, shared across confirmation seeds and arms. Generate and freeze role assignments before outcomes.
>
> Calculate the complete conservative cost before launching. If the planned programme does not fit, reduce optional diagnostics before changing its scientific design. Do not silently reduce confirmation seeds or the primary evaluation panel.
>
> Commit the protocol, analysis and executable training source before outcome-producing runs.
>
> 4. Define corrective supervision precisely.
>
> For C, query a module-local planner on selected states from that arm’s own PPO rollouts. The learner continues to execute every training action. No planner takeover, assisted resets or inventory edits are permitted.
>
> The planner supplies a next-action label for completing the current prefix module, including necessary inventory exchange, key acquisition and door passage.
>
> Freeze these details:
>
> - How the current unfinished module is identified.
> - Recovery behavior after backtracking, wrong-key possession or premature key loss.
> - Handoff between key acquisition and door passage.
> - Handling of multiple valid actions and planner ties.
> - Search limits, impossible states and unresolved queries.
> - Label sampling and reuse.
>
> Do not train arbitrary fallback labels when planning fails. Record failures and their state categories.
>
> The label should be compatible with information available to the actor. Audit cases where identical actor observations receive conflicting labels because of hidden planner context.
>
> Use auxiliary cross-entropy with coefficient **0.1**, averaged over the selected labeled examples, added during the existing PPO optimization schedule. Apply the same coefficient and normalization to R. Do not add extra optimizer steps to only one arm.
>
> Sample at most every fourth eligible prefix transition, with a hard cap of **75,000 queried states per branch**. Enforce that cap in code: every-fourth sampling alone can exceed 75,000 over 501,760 actions.
>
> Use current-rollout labels for this study rather than adding an unspecified growing replay buffer. Freeze how labels are reused across PPO epochs. Match R’s supervised-example count and reuse schedule to C’s.
>
> Keep PPO behavior-action records intact. Expert labels are auxiliary targets; do not replace executed actions, old log probabilities, rewards or advantages with planner values.
>
> After the boundary, use the unchanged PPO objective without prefix supervision.
>
> 5. Validate the implementation before the seed study.
>
> Use a small, separately accounted smoke allowance to establish that:
>
> - Planner labels are valid on representative learner-error states.
> - The auxiliary loss has the intended sign and scale.
> - Gradients reach the actor.
> - A/R/C forks begin from identical state.
> - R and C have matched supervised-update schedules.
> - C executes learner actions throughout training.
> - Evaluation uses only the learned actor, with no planner, mask or auxiliary controller.
> - Counter accounting, checkpoint resume and interruption work correctly.
>
> Check raw PPO KL, clipping, entropy, gradient norms, auxiliary loss and label agreement. The PPO clipping rule does not itself constrain the auxiliary imitation update.
>
> Functional checks may repair implementation defects. They do not authorize tuning lambda against success outcomes. Freeze the tested implementation before the six-seed study.
>
> If a substantive bug is discovered later, stop admissions, preserve affected records and document the repair before deciding which runs must be repeated.
>
> 6. Development and automatic selection.
>
> Run all six development seeds for all three arms before applying the gate. Report every seed and comparison.
>
> An arm qualifies for further study only if:
>
> - Its mean success gain over A at 501,760 is at least 0.05.
> - At least four of six paired seed differences are positive.
> - Integrity checks pass and confirmation fits the remaining budget.
>
> Choose C only if it qualifies and its mean advantage over R is at least 0.02.
>
> Otherwise, choose R if it qualifies. This preference avoids new expert queries when their added value is not apparent.
>
> If neither selection rule passes, stop training and write up development. Do not add doses, schedules, seeds or a longer endpoint.
>
> These thresholds are prospective spending rules, not statistical evidence that rejected methods have zero effect.
>
> 7. Confirmation.
>
> If C is selected, run twenty fresh paired seeds with A, R and C. If R is selected, run twenty fresh paired seeds with A and R.
>
> Do not pool development and confirmation. Keep confirmation outcomes unavailable to scientific selection until all planned runs and integrity checks are complete. Operational monitoring may inspect execution health.
>
> Primary analysis:
>
> - For selected C, first test C−A using the prespecified two-sided paired seed-level test at 0.05. Only if that passes, test C−R at 0.05 as a fixed-sequence family.
> - For selected R, use one primary R−A test.
> - Report effect estimates and confidence intervals regardless of significance.
> - Also report crossed seed-and-layout bootstrap intervals and a paired sign-flip sensitivity analysis.
>
> Before running, calculate power across plausible paired seed SDs, including 0.03, 0.045 and 0.06. Treat earlier SDs as planning scenarios, not guarantees about this new intervention. Do not claim twenty seeds necessarily resolve a 0.03 effect.
>
> Distinguish evidence of a positive effect from evidence of a practically large effect. Do not claim a minimum five-point benefit unless the interval supports it.
>
> If the seed-level and crossed analyses disagree, state their different scopes. Do not silently promote a panel-conditional result into broad layout generalization.
>
> 8. Measure what changed without overstating mechanism.
>
> Besides unassisted success, report:
>
> - Boundary reach and completion conditional on actual arrival, with explicit counts.
> - Arrival time and remaining time.
> - Inventory exchanges and premature key drops.
> - Locked-door toggles and ineffective actions.
> - Planner query coverage, failures, labeled states and reuse.
> - Auxiliary-loss scale and policy-update diagnostics.
> - Expert-action agreement on a fixed held-out recovery-state bank.
>
> Keep recovery-bank labels out of training. Never query confirmation-layout labels for training.
>
> Evaluate all arms with the same unassisted protocol. A higher conditional completion rate can reflect changed arrival states; it is not automatically a causal improvement in suffix skill.
>
> Interpret the comparisons carefully:
>
> - C>A supports the tested corrective-supervision package.
> - C>R supports an advantage over this matched demonstration-replay control.
> - Similar C and R results do not prove equivalence.
> - Better recovery-state agreement without better normal success repeats the earlier transfer problem.
> - A negative result concerns this fixed procedure and strength, not every form of interactive imitation.
>
> Relate the method to existing interactive imitation and demonstration-augmented RL. Make no novelty claim based solely on combining a planner loss with PPO.
>
> 9. Battery, resources and two-hour reviews.
>
> Restart the project-owned battery guard and two-hour review loop before substantial work, after checking for duplicate monitors.
>
> **Stop project workloads at battery charge of 31% or lower, including on AC.**
>
> Poll often enough to allow orderly checkpointing. Do not launch a batch whose conservative discharge estimate would consume the safety margin.
>
> The guard must set a persistent pause flag checked by every launcher. Charging must not clear it. Resume requires my explicit instruction.
>
> Monitor the full process tree for CPU and memory pressure. Use compact logs and scripts rather than repeated large status dumps.
>
> Every two hours, record:
>
> - What evidence changed?
> - What remains uncertain?
> - Are the controls, supervision privileges and costs fair?
> - Does the implementation still match the frozen procedure?
> - Is the next batch justified?
> - Should work continue, pause or stop?
>
> Reviews must not inspect blinded confirmation effects or change outcome rules after results appear.
>
> 10. Verification and completion.
>
> Independently recompute reported metrics, selection decisions and costs from raw records through a separate analysis path. Explain any shared upstream dependencies.
>
> Retain failures, retries and deviations. Do not exclude difficult seeds or silently replace runs.
>
> Update the project with this instruction. After careful reconciliation, update the protocol, STATE, CHECKLIST, DECISIONS, FINDINGS and REPORT. Keep completed evidence separate from interpretations and future proposals.
>
> At completion, provide:
>
> - A/R/C development results and the selection decision.
> - Confirmation results, if authorized by the gate.
> - A direct answer about whether new corrections helped beyond demonstration replay.
> - Full environment and supervision costs.
> - Remaining uncertainty and a recommendation to adopt, investigate further or close the line.
>
> Commit and push under the established workflow. Stop your own workers and monitors when complete or paused.
>
> Begin with the record audit, restore battery protection and the two-hour review loop, freeze the design, validate the implementation and execute the authorized programme.

*Agent note (2026-11-02c):* starting ledger 329,624,666; new ceiling 80,000,000 executed actions from that ledger (scientific submissions capped at 72,000,000; 8,000,000 itemised reserve); the battery rule (31% or lower) is unchanged.

## Owner instruction 2026-11-02d (verbatim; consolidation and write-up, no new training)

> I recommend:
> 1. Stop new training. If the corrective-imitation programme has started, checkpoint it and preserve all records.
> 2. Consolidate the evidence. Produce one table linking each original hypothesis to its strongest evidence, uncertainty and conclusion. Keep exploratory diagnostics separate.
> 3. Finish the MiniGrid write-up. Include the negative results, small effects, failed replications and measurement lessons. Avoid adding experiments merely to obtain a positive ending.
> 4. Reassess the broader project before choosing another environment. Identify the unresolved scientific claim and the observation that could change our belief. Then choose the smallest experiment that tests it.

*Agent note (2026-11-02d):* received after the 2026-11-02c programme had already completed at its development gate (commit `9149d77`); no project processes were running and all records were already committed and pushed, so no checkpointing was needed. No new training under this instruction; the reassessment proposes an experiment but does not launch it.

## Owner instruction 2026-11-03 (verbatim; final actor capability audit, 500k actions, 6 h fitting)

> Run one final capability audit of the MiniGrid actor. Its purpose is to qualify the completed findings and guide future experimental setup. It does not reopen the MiniGrid research programme.
>
> You may perform offline supervised fitting and limited prefix evaluation. Do not run PPO, retest interventions, develop a selector or automatically begin an architecture-improvement programme.
>
> 1. Audit the premise before collecting data.
>
> Read the current project instructions, WRITEUP, REPORT, relevant findings, actor implementation, observation encoder and planner-label implementation.
>
> Establish exactly what the actor receives:
>
> - Grid contents, agent position and orientation.
> - Carried object and its color.
> - Door state.
> - Remaining time, if present.
> - Any information used by the planner that is absent from the actor’s observation.
>
> Inspect convolution stride, padding, pooling, flattening and dense layers. Document local receptive fields separately from the final actor’s access to the full grid.
>
> Do not describe the actor as seeing only 7×7 unless the implementation actually restricts its input that way.
>
> Audit identical actor observations with different planner targets. Where target sets conflict, distinguish missing observation information from planner inconsistency or history-dependent target definitions.
>
> For the previous corrective-imitation loss, calculate target entropy where records permit. Report cross-entropy above that floor, rather than interpreting raw cross-entropy alone as fitting error.
>
> Correct the write-up’s architecture and outcome claims before launching fits.
>
> 2. Fix the scope and budget.
>
> Maximum additional executed environment actions: **500,000**, including collection, planner replay, tests and rollout evaluation.
>
> Maximum active fitting compute: **six hours**. Track it separately from environment actions. Do not treat either allowance as a spending target.
>
> Reuse existing state and label records where they are complete and suitable. Do not recollect hundreds of thousands of states merely to match the proposed dataset size.
>
> Retain the existing four-core, 6 GiB, one-job limits. Use native MPS where beneficial. No paid or remote compute.
>
> There is no authorization for further experiments after this audit. If the budget is insufficient, report the unresolved question and stop.
>
> 3. Validate observations, labels and the expert controller.
>
> Before testing network capacity:
>
> - Check that labeled actions are legal and planner-valid from the saved state.
> - Check pickup, inventory exchange, door passage, backtracking and premature key-loss cases.
> - Distinguish unresolved planning from certified impossibility.
> - Verify that labels do not depend on unavailable actor information without explicitly documenting that privilege.
> - Execute the planner’s own prefix policy on a small predetermined panel using the original episode clock.
>
> If the expert controller cannot reliably reach the boundary, investigate the labels or controller semantics before fitting networks. Do not interpret a learner’s failure to imitate an unreliable target as a capacity result.
>
> All planner replay actions count toward the budget.
>
> 4. Freeze the dataset and test procedure.
>
> Use disjoint layout groups for training, validation and final testing. Split by layout identity, not individual state rows.
>
> Check duplicates and provenance across existing records. A warm-start actor may already have seen some layouts during BC; do not call those layouts unseen. Use genuinely fresh final-test layouts.
>
> Include both ordinary and recovery states. Report their proportions and separately identify wrong-key possession, backtracking and premature key loss.
>
> Prefer nested training subsets of 25k, 100k and 200k states, if available within budget. Freeze smaller sizes before fitting if necessary. Record unique states and layouts rather than counting repeated rows as new data.
>
> The final test remains untouched until model settings and checkpoint-selection rules are fixed.
>
> 5. Separate fitting failure from generalization failure.
>
> First perform a tiny-set overfitting check on approximately 512 audited states.
>
> Use a short, fixed optimizer sanity check with at most two learning rates. Inspect gradients, preprocessing, loss reduction and label consistency. Set a fixed update limit before running.
>
> Failure to overfit this tiny set blocks any claim that the full-data result identifies a representation limit.
>
> For the main audit, use three fixed fit seeds and these conditions:
>
> - Original actor, warm-started from existing BC weights.
> - Original actor, initialized from scratch.
> - One larger comparison actor, initialized from scratch.
>
> Choose the comparison architecture before inspecting outcomes. Prefer one simple change that increases global decision capacity while preserving the observation encoder—for example, a wider dense head if the original actor flattens the full feature map. Do not search across architectures.
>
> Run the data-size curve for the warm-started original actor. Run the scratch original and comparison actor at the largest frozen dataset size. Match data, supervised objective, minibatch sampling and update limits.
>
> Use a loss that rewards probability assigned to the valid planner-action set:
>
> `loss = -log(sum of policy probabilities over valid actions)`
>
> This avoids requiring equal probability on every tied action. Document that this differs from the previous uniform-target auxiliary loss. It does not revise that experiment’s result.
>
> Report:
>
> - Training and held-out argmax-in-valid-set agreement.
> - Probability mass on valid actions.
> - Loss relative to its appropriate floor.
> - Performance by state category and action type.
> - Training curves and actual compute.
>
> Use fixed validation-based checkpoint selection. Do not repeatedly inspect the final test or add training after seeing it.
>
> 6. Test execution as well as action agreement.
>
> Evaluate the fitted actors on a shared fresh panel of 64 K=3 layouts with two attempts each, provided the conservative action estimate fits the cap.
>
> Measure unassisted boundary reach, time to boundary and failure categories. Stop evaluation episodes at the first boundary crossing.
>
> Preserve the original episode allowance and observation processing. No planner assistance, action masking, resets or hidden-state inputs.
>
> Evaluate deterministic argmax behavior as the primary execution rule. If stochastic execution is also evaluated, freeze it beforehand and report it separately.
>
> Include the original warm-start actor and expert prefix controller as references.
>
> Use layout-level paired uncertainty and report variation across fit seeds. Do not treat hundreds of states from the same layout as independent evidence.
>
> This audit concerns prefix execution. It does not establish improved full-task success or preserved suffix behavior.
>
> 7. Interpret outcomes conservatively.
>
> Use the following distinctions:
>
> - Poor tiny-set fit: implementation, labels or optimization remain unresolved.
> - Strong training fit but weak fresh-layout fit: generalization or coverage is limiting; capacity is not uniquely identified.
> - Strong held-out fit but weak rollout access: investigate accumulated errors, rollout distribution shift, action sampling and target adequacy. Do not conclude automatically that the abstraction is wrong.
> - Original actor performs well under pure supervision: it can learn a useful prefix policy under this data and optimization procedure. This does not identify why PPO plus imitation failed.
> - Larger actor performs substantially better under matched conditions: evidence of model sensitivity, not proof that architecture caused the earlier intervention nulls.
> - Both actors fail: inconclusive between the remaining explanations.
>
> Do not use a single 80% or 90% agreement threshold as proof of representational adequacy or inadequacy. Long sequences require execution evidence, and aggregate accuracy can hide critical rare errors.
>
> 8. Close the audit.
>
> Independently recompute the final metrics and action totals. Save model, dataset, layout and code hashes.
>
> Update WRITEUP, REPORT, FINDINGS, DECISIONS, STATE and CHECKLIST. Preserve all completed intervention verdicts.
>
> The final report should answer:
>
> - Can the original actor fit the audited targets?
> - Does that fit generalize to fresh layouts?
> - Can the fitted actor execute the prefix?
> - Does the comparison actor materially change the answer?
> - Which limitations should qualify the existing MiniGrid conclusions?
>
> Recommend what to carry into future research. Do not automatically fix the architecture, rerun prior studies or collect another dataset.
>
> Before substantial work, restart the project-owned battery guard and two-hour review loop after checking for duplicates. Stop workloads at **31% battery or lower, including on AC**. Set the persistent pause flag; charging must not restart work without my explicit instruction.
>
> Maintain the resource guards. Stop your own monitors at completion or pause.
>
> Record this instruction, update the state and checklist after reviewing the evidence, freeze the audit design, and execute only this authorized audit.

*Agent note (2026-11-03):* starting ledger 342,196,148; cap 500,000 additional executed actions (all collection, planner replay, tests and rollouts); fitting compute cap 6 h, tracked separately; no PPO; battery rule (31% or lower) unchanged.
