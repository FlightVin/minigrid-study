# Reading guide for a new agent

This guide tells you which files to read to understand the MiniGrid study: what was run, what was found, and why.
Read the files in tier order. Tier 1 is enough for most purposes.

## How to read the record

- Read `reports/WRITEUP.md` and `research/STATE.md` first.
- Treat `research/FINDINGS.md`, `research/DECISIONS.md` and `research/PROTOCOL_FREEZE.md` as the detailed record.
- Where text is marked "Corrected" (with a date), use the corrected version. The original text is kept for history.
- Exploratory diagnostics are not confirmatory claims. Development results (no confirmation run) are not confirmed
  effects.
- No further experiments are authorized. Any new work needs an explicit instruction from the owner.

## Orientation (summary; the files are the authority)

- **Task.** A custom MiniGrid environment (`src/bc2rl/task.py`). The agent must pass a chain of K locked-door
  modules: pick up the key that matches each door, unlock it and go through, then cross a boundary (x ≥ 13) before
  the time limit. The part before the boundary is the "prefix" (access); the part after is the "suffix"
  (completion). The actor sees the full 21 × 9 grid, its carried item and the remaining time.
- **Question.** Does behaviour cloning (BC), followed by help aimed at the prefix (demonstration-state starts,
  reset curricula, BC preservation, demonstration replay, planner corrections), improve PPO on this task?
- **Main result.** Ordinary PPO improves with budget, mostly through access. Every training intervention that
  tried to deliver prefix knowledge gave at most about +0.03 or did harm. Privileged prefix help at evaluation
  time raises success by 0.27-0.34, so the opportunity exists. Learned suffix completion is a separate limit.
- **Final audit (2026-11-03).** Under supervised learning on planner labels alone, the original actor:
  - fits the labels (0.975-0.979 agreement on fresh layouts);
  - reaches the boundary on 0.71-0.73 of 64 fresh layouts, against 0.005 for its BC start and 1.00 for the planner
    expert.
  So representability does not explain the RL failures. A wider dense layer added +0.15 reach at equal
  agreement. That is model sensitivity, not proof of an architecture cause.
- **Visual.** `reports/p8/minigrid_k3_prefix.gif` shows one fresh layout under the BC start, the fitted actor and
  the expert.

## Tier 1: start here (about 350 lines)

1. **`reports/WRITEUP.md`.** The consolidated write-up and the best entry point. It has:
   - the task and every hypothesis with its evidence, uncertainty and verdict;
   - exploratory diagnostics, kept separate;
   - negative results, small effects, failed replications, measurement lessons, costs and limitations;
   - the reassessment (section 8) and the final actor capability audit (section 9).
   It uses the corrected wording throughout.
2. **`research/STATE.md`.** A short snapshot: current status, the owner's limits, and what is and is not authorized.

## Tier 2: the reasoning and intuitions

3. **`research/FINDINGS.md`** (about 1,500 lines). Every finding, F1-F34, with candidate explanations and marked
   corrections. Most of the intuitions are here. If space is limited, read F26 and F28-F34.
4. **`research/DECISIONS.md`** (about 800 lines). Why each design choice was made, plus every deviation, failure and
   rerun.
5. **`reports/p8/premise_audit.md`** and **`reports/p8/audit.md`**. The final audit's premise check (corrected
   architecture description; cross-entropy floor) and its full result tables.

## Tier 3: exact protocols and the full record (for checking details)

6. **`research/PROTOCOL_FREEZE.md`** (about 1,350 lines). What was pre-registered before each run (Amendments 1-10
   and their addenda). Use it to tell planned tests from post-hoc analyses.
7. **`reports/REPORT.md`** (about 1,370 lines). The layered historical report, sections C-W. It is detailed but
   repetitive; `reports/WRITEUP.md` supersedes it for reading.
8. **`research/REVIEWS.md`**. The periodic research reviews. Use them to see how the judgments developed.

## Owner instructions

9. **`mac-agentic-engineering/project.md`** (about 3,500 lines). Every owner instruction, recorded verbatim. It is
   long: read the last few instructions unless you need the history. This file is in a nested repository that is
   not pushed to GitHub, so it is supplied separately.

## Optional

- **`reports/p8/minigrid_k3_prefix.gif`.** A quick visual of the task.
- **`reports/p8/verification.json`.** The independent recomputation of the final audit, with hashes.
- **Code** (only if you will run anything):
  - `src/bc2rl/task.py`: the environment;
  - `src/bc2rl/model.py`: the actor;
  - `src/bc2rl/corrective.py`: the planner labels;
  - `src/bc2rl/capability.py` and `src/bc2rl/capfit.py`: the final audit.
