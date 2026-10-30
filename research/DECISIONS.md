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
