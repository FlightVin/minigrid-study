"""Role-separated layout seeds and a machine-checkable split registry.

Every role draws layout seeds from its own SeedSequence namespace. One layout seed gives the
same suffix for every K, so each role holds matched K=1/K=3 layouts. Disjointness is checked on
canonical layout structure hashes, not on seeds or filenames. A layout whose structure already
belongs to an earlier role (in ROLE_ORDER) is rejected by this prespecified rule and recorded.
Evaluation and bank roles are also suffix-disjoint from every training role and from each other,
so no evaluated suffix was seen in fitting and dev tuning never sees a confirmation suffix.
"""
import hashlib
import json

import numpy as np

from bc2rl import task as T

# Fixed namespaces. Never renumber: the integers define the splits.
ROLE_NAMESPACE = {
    "bc_train": 101, "bc_val": 102, "rl_train": 103, "reset_donor": 104, "anchor_donor": 105,
    "dev_eval": 106, "dev_bank": 107, "conf_select": 108, "conf_bank": 109, "conf_final": 110,
    "k2_reserved": 111, "r1_select": 112, "r1_bank": 113, "r1_final": 114,
    "r2_select": 115, "r2_bank": 116, "r2_final": 117,
    "a3_select": 118, "a3_bank": 119, "a3_final": 120, "pl_select": 121, "pl_bank": 122, "pl_final": 123,
    "a4_select": 124, "a4_bank": 125, "a4_final": 126, "a4_donor": 127,
    "d5_trace": 128, "p5_select": 129, "p5_eval": 135, "p5_bank": 131, "c5_select": 132, "c5_bank": 133, "c5_final": 134,
    "d6_ctrl": 136, "r7_select": 137, "r7_dev": 138, "r7_conf": 139, "r7_recov": 140,
}
TRAIN_ROLES = ("bc_train", "bc_val", "rl_train", "reset_donor", "anchor_donor")
EVAL_ROLES = ("dev_eval", "dev_bank", "conf_select", "conf_bank", "conf_final", "r1_select", "r1_bank", "r1_final",
              "r2_select", "r2_bank", "r2_final", "a3_select", "a3_bank", "a3_final", "pl_select", "pl_bank", "pl_final",
              "a4_select", "a4_bank", "a4_final", "a4_donor",
              "d5_trace", "p5_select", "p5_eval", "p5_bank", "c5_select", "c5_bank", "c5_final", "d6_ctrl",
              "r7_select", "r7_dev", "r7_conf", "r7_recov")
# Earlier roles win a structural collision; evaluation roles come last so they stay untouched.
ROLE_ORDER = ["bc_train", "bc_val", "rl_train", "reset_donor", "anchor_donor", "dev_eval", "dev_bank",
              "conf_select", "conf_bank", "conf_final", "r1_select", "r1_bank", "r1_final", "r2_select", "r2_bank",
              "r2_final", "a3_select", "a3_bank", "a3_final", "pl_select", "pl_bank", "pl_final",
              "a4_select", "a4_bank", "a4_final", "a4_donor",
              "d5_trace", "p5_select", "p5_eval", "p5_bank", "c5_select", "c5_bank", "c5_final", "d6_ctrl",
              "r7_select", "r7_dev", "r7_conf", "r7_recov"]
ALLOWED_USE = {
    "bc_train": "supervised fitting only",
    "bc_val": "BC checkpoint/fitting development; no PPO branch outcomes",
    "rl_train": "normal-start PPO rollouts, shared by all branches",
    "reset_donor": "demonstration-state starts in assistance branches",
    "anchor_donor": "preservation-loss anchor states (cached pi0 distributions)",
    "dev_eval": "development diagnostics and tuning",
    "dev_bank": "development competence bank donors",
    "conf_select": "confirmation selection/diagnostic normal starts; no fitting",
    "conf_bank": "confirmation competence bank donors; no fitting",
    "conf_final": "confirmation final evaluation only; never tuning or selection",
    "r1_select": "R1 replication pi0/post-probe diagnostics and curve points; no fitting",
    "r1_bank": "R1 replication competence bank donors; no fitting",
    "r1_final": "R1 replication final evaluation only; never tuning or selection",
    "r2_select": "R2 replication pi0/post-probe diagnostics and curve points; no fitting",
    "r2_bank": "R2 replication competence bank donors; no fitting",
    "r2_final": "R2 replication final evaluation only; never tuning or selection",
    "a3_select": "A3 anchor-allocation study pi0/post-probe diagnostics; no fitting",
    "a3_bank": "A3 competence bank donors; no fitting",
    "a3_final": "A3 final normal-start evaluation only; never tuning or selection",
    "pl_select": "calibrated-regime pilot pi0/post-probe diagnostics; no fitting",
    "pl_bank": "calibrated-regime pilot competence bank donors; no fitting",
    "pl_final": "calibrated-regime pilot normal-start evaluation; exploratory; never calibration selection",
    "a4_select": "A4 long-budget study pi0/post-probe normal-start diagnostics; no fitting",
    "a4_bank": "A4 planner boundary-entry competence bank donors (entry states only); no fitting",
    "a4_final": "A4 final normal-start evaluation (256 K=3 layouts x 2) only; never tuning or selection",
    "a4_donor": "A4 actual-arrival bank donor layouts (calibration policies' first crossings); no fitting",
    "d5_trace": "2026-11-02 failure diagnostics: traced normal starts and assisted references of frozen A4 checkpoints",
    "p5_select": "2026-11-02 pilot pi0/post-probe normal-start diagnostics; no fitting",
    "p5_eval": "2026-11-02 pilot development evaluation panel (64 K=3 x 4); development only",
    "p5_bank": "2026-11-02 pilot planner boundary-entry competence bank (128 K=3 entry states); no fitting",
    "c5_select": "2026-11-02 confirmation pi0/post-probe diagnostics; no fitting; never development",
    "c5_bank": "2026-11-02 confirmation planner boundary-entry competence bank; no fitting; never development",
    "c5_final": "2026-11-02 confirmation final evaluation (256 K=3 x 2) only; never tuning or selection",
    "d6_ctrl": "2026-11-02b frozen-policy controller diagnostics panel (K=3 x 2 attempts); evaluation only; no fitting",
    "r7_select": "2026-11-02c corrective-imitation study pi0/post-probe normal-start diagnostics; no fitting",
    "r7_dev": "2026-11-02c development evaluation panel (64 K=3 x 4); development selection only; never confirmation",
    "r7_conf": "2026-11-02c confirmation evaluation panel (256 K=3 x 2) only; never development, tuning or labels",
    "r7_recov": "2026-11-02c held-out recovery-state bank donor layouts; agreement evaluation only; never training labels",
}


def role_seed(role, index):
    ss = np.random.SeedSequence([ROLE_NAMESPACE[role], index])
    return int(ss.generate_state(1, dtype=np.uint32)[0])


def suffix_hash(layout):
    d = {k: getattr(layout, k) for k in ("family", "gap_row", "target_pos", "distractor_pos", "delivery_pos")}
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=list).encode()).hexdigest()[:16]


def build_registry(counts, Ks=(1, 3)):
    """counts: {role: number of layout seeds}. Returns registry dict (unplanned layouts)."""
    taken, registry, rejected = {}, {}, []
    suffix_owner = {}
    for role in ROLE_ORDER:
        if role not in counts:
            continue
        entries, i = [], 0
        while len(entries) < counts[role]:
            seed = role_seed(role, i)
            i += 1
            layouts = {K: T.generate_layout(K, seed) for K in Ks}
            hashes = {K: layouts[K].structure_hash() for K in Ks}
            sh = suffix_hash(layouts[Ks[0]])
            clash = [taken[h] for h in hashes.values() if h in taken]
            if role in EVAL_ROLES and sh in suffix_owner and suffix_owner[sh] != role:
                clash.append("suffix:" + suffix_owner[sh])
            if clash:
                rejected.append({"role": role, "seed": seed, "clashes_with": clash})
                continue
            for h in hashes.values():
                taken[h] = role
            if role in TRAIN_ROLES or role in EVAL_ROLES:
                suffix_owner.setdefault(sh, role)
            entries.append({"seed": seed, "index": i - 1, "structure_hash": {str(K): hashes[K] for K in Ks},
                            "suffix_hash": sh})
        registry[role] = entries
    return {"roles": registry, "rejected": rejected, "Ks": list(Ks),
            "namespaces": {r: ROLE_NAMESPACE[r] for r in registry}, "allowed_use": ALLOWED_USE}


def check_registry(reg):
    """Raise if any two roles share a structure hash or a seed. Returns overlap statistics."""
    owner = {}
    seeds = {}
    for role, entries in reg["roles"].items():
        for e in entries:
            if e["seed"] in seeds and seeds[e["seed"]] != role:
                raise AssertionError(f"seed {e['seed']} in {seeds[e['seed']]} and {role}")
            seeds[e["seed"]] = role
            for h in e["structure_hash"].values():
                if h in owner and owner[h] != role:
                    raise AssertionError(f"layout {h} in {owner[h]} and {role}")
                owner[h] = role
    suffix_role = {}
    for role, entries in reg["roles"].items():
        for e in entries:
            other = suffix_role.setdefault(e["suffix_hash"], role)
            if other != role and (role in EVAL_ROLES or other in EVAL_ROLES):
                raise AssertionError(f"suffix {e['suffix_hash']} in {other} and {role}")
    n_train = len({e["suffix_hash"] for r in TRAIN_ROLES for e in reg["roles"].get(r, [])})
    return {"distinct_training_suffixes": n_train, "rejected": len(reg["rejected"])}


def registry_hash(reg):
    return hashlib.sha256(json.dumps(reg["roles"], sort_keys=True).encode()).hexdigest()
