# Premise audit before the actor capability audit (owner instruction 2026-11-03, section 1)

Code inspection plus zero-action computation. Sources: `src/bc2rl/task.py` (StageTask.gen_obs, snapshot),
`src/bc2rl/model.py` (Encoder, Actor), `src/bc2rl/corrective.py` (frontier, query, category),
`src/bc2rl/ppo.py` (auxiliary loss logging), C7 run records (`metrics.jsonl`, `summary.json`).

## 1. What the actor receives

| Item | In the observation? | Encoding |
|---|---|---|
| Grid contents (walls, floor, doors, keys, balls) | Yes, every cell of the 21 × 9 canvas | channels 0-2 of `grid`: object type, colour, state (MiniGrid encoding) |
| Door state | Yes | grid channel 2: 0 open, 1 closed, 2 locked |
| Agent position | Yes | grid channel 3 is non-zero at exactly the agent's cell; the flatten keeps position |
| Agent orientation | Yes, twice | grid channel 3 = 1 + direction; `aux[0]` = direction (one-hot) |
| Carried object and colour | Yes | `aux[1]` type, `aux[2]` colour + 1 (one-hot) |
| Remaining time | Yes | `time` = (limit − step_count) / 200, float32 (exact for integer counts) |
| Episode limit, step count separately | No | only their difference is observed |
| `accessed` (boundary already crossed) | No | prefix states always have accessed = False; labels apply only there |
| Original key positions (`layout.key_pos`) | No (only current positions) | used only by `category()` for the "key displaced" record field, never by labels |

The full grid is observed every step. The observation is not egocentric and has no partial view. The MiniGrid
`agent_view_size` setting is unused, because `gen_obs` is overridden.

## 2. Actor architecture (stride, padding, pooling, flatten, dense)

- Embeddings: 8 dimensions for each of the 4 grid channels → 32 input planes on the 21 × 9 grid.
- Convolutions: 3 × 3 kernels, **stride 1, padding 1, no pooling**: 32 → 16 → 32 → 32 planes, ReLU after each.
  Output: 32 × 21 × 9, the same spatial size as the input.
- **Local receptive field.** One feature of the last convolution depends on a 7 × 7 neighbourhood of its cell.
- **Full-grid access.** The full feature map is flattened (6,048 features, position kept), concatenated with 23 scalar
  inputs (direction one-hot 4, carried type one-hot 11, carried colour one-hot 7, time 1), and fed to **one dense
  layer of 128 ReLU units** (6,071 × 128 weights). A linear head gives 7 logits. So the dense layer receives every
  cell's features. Relations between distant cells are possible in principle; they must be formed by that single
  128-unit layer.
- Parameters: 796,831 in total, of which 777,216 + 128 are in the dense layer.
- **Correction.** WRITEUP section 8 said that the actor "sees the 21 × 9 grid through three 3 × 3 convolutions,
  a 7 × 7 receptive field". That is wrong as a description of the actor's input: 7 × 7 is the receptive field of each
  convolution feature, and the dense layer sees the whole grid.

## 3. What the planner uses, and whether the actor has it

`corrective.query` reads:
- the grid objects, door states, key and ball positions → observed;
- the agent position and direction, the carried object → observed;
- the remaining time → observed. Time affects only the status (`labelled` vs `time_exceeded`), never the label set;
- layout fields `active_slots()` (K = 3: all three slots), `door_rows`, `colors()` → each is visible in the grid as the
  door's cell and colour (the capability audit verifies this equality on every collected state);
- `env.accessed` → asserted False (eligibility only).

The label set is a deterministic function of the observation. It uses no history and no random numbers. The frontier
("first locked door") is computed from door states in the grid. `category()` also uses the original key position
(`layout.key_pos`), which is not observed. That privilege affects only the stratum record (key_lost), never a label.

**Identical observations with different targets.** Because the label is a function of the observation, a conflict
could come only from (a) a hash collision, (b) information outside the observation, or (c) a planner defect. In the
2026-11-02c C7 runs, `observation_conflicts` was 0 in all six seeds (418,957 queries; every repeated observation was
planned again and compared with its first status and label). The audit repeats the check on its whole collected dataset, rebuilding each
state from its observation alone.

## 4. Target entropy and the C7 cross-entropy (2026-11-02c)

C7 trained with a uniform target over the label set, so the cross-entropy floor is the target entropy: log k for a
k-action label set. From each branch's label-size counts (`reports/p8/c7_ce_floor.json`):

| Seed | Labelled | Floor (nats) | CE mean | CE excess (mean) | CE excess (last 20 updates) | argmax-in-set (mean, last 20) |
|---|---|---|---|---|---|---|
| 116 | 63,019 | 0.241 | 1.114 | 0.873 | 0.875 | 0.652, 0.679 |
| 117 | 65,005 | 0.248 | 1.142 | 0.894 | 0.807 | 0.619, 0.641 |
| 118 | 65,681 | 0.246 | 1.134 | 0.887 | 0.795 | 0.622, 0.655 |
| 119 | 64,539 | 0.233 | 1.063 | 0.830 | 0.733 | 0.686, 0.720 |
| 120 | 65,757 | 0.247 | 1.152 | 0.905 | 0.827 | 0.612, 0.643 |
| 121 | 63,947 | 0.249 | 1.088 | 0.838 | 0.706 | 0.653, 0.710 |
| mean | | 0.244 | 1.115 | 0.871 | 0.791 | 0.641, 0.675 |

- The floor uses the label-size distribution of all labelled examples. The per-minibatch distribution is the same in
  expectation.
- The logged CE is the auxiliary minibatch loss during PPO updates. Its examples came from the current rollout, so in
  the first epoch they were unseen states. The excess therefore mixes fitting error with generalisation to new
  states, and it was measured under the joint PPO objective with coefficient 0.1.
- The excess above the floor stayed large (about 0.8 nats) to the end. This shows that C7 did not fit its targets well
  under that procedure. It does not by itself show a representation limit.
- R7 (one-hot demonstration targets, floor 0) logged CE 0.23-0.37.

## 5. Consequences for the audit design

- The actor has full-grid access. The capacity question is whether one 128-unit dense layer on these features can
  represent the label rule and generalise it to new layouts. The comparison actor therefore widens that dense layer
  and keeps the encoder unchanged.
- Labels need no information that the actor lacks. The one hidden variable (`accessed`) only selects prefix states.
- Set-valued labels with ties make uniform-target CE an unsuitable fitting measure. The audit uses
  −log(probability mass on the valid set), whose floor is 0, and argmax-in-set agreement.
