"""Training-role gate for confirmation data (PROTOCOL_FREEZE section 1, Amendments 1 and 2).

Usage: .venv/bin/python tools/data_gate.py [--dev data/dev-v2] [--conf data/conf-v1] [--r1 data/r1-v1]

Passes only if
  - traj_*.npz for bc_train, bc_val, reset_donor, anchor_donor, dev_bank and banks_index.npz are byte-identical
    (SHA-256, recomputed from the files, and equal to each manifest);
  - bank_competence_dev_bank.json is byte-identical;
  - layouts.json entries for every dev-v2 role are identical in conf-v1;
  - the confirmation roles exist with the planned counts and share no structure hash with any dev-v2 role;
  - the confirmation roles share no structure hash or generator seed with each other (added after M4).
With --r1 (PROTOCOL_FREEZE Amendment 3) it also requires
  - every conf-v1 file except registry/layouts/manifest byte-identical in r1-v1 (so the training data equal dev-v2),
    and every conf-v1 layout role identical;
  - the r1 roles with the planned counts, sharing no structure hash, generator seed or suffix hash with any earlier
    role (training, development or confirmation) or with each other.
With --r2 (PROTOCOL_FREEZE Amendment 4; requires --r1) the same rule one level up: every r1-v1 file
byte-identical in r2-v1, every r1-v1 role identical, and the r2 roles disjoint from all r1-v1 roles (which
include every earlier role) and from each other; r2_bank K3 bins equal conf_bank's.
Prints a JSON report; exit status 1 on any failure.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAME_FILES = ["traj_bc_train.npz", "traj_bc_val.npz", "traj_reset_donor.npz", "traj_anchor_donor.npz",
              "traj_dev_bank.npz", "banks_index.npz", "bank_competence_dev_bank.json"]
CONF_ROLES = ("conf_select", "conf_bank", "conf_final")
R1_ROLES = ("r1_select", "r1_bank", "r1_final")
R2_ROLES = ("r2_select", "r2_bank", "r2_final")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=str(ROOT / "data/dev-v2"))
    ap.add_argument("--conf", default=str(ROOT / "data/conf-v1"))
    ap.add_argument("--r1")
    ap.add_argument("--r2")
    a = ap.parse_args()
    dev, conf = Path(a.dev), Path(a.conf)
    md, mc = (json.loads((d / "manifest.json").read_text()) for d in (dev, conf))
    rep, ok = {"files": {}, "roles": {}, "conf_roles": {}}, True
    for f in SAME_FILES:
        h1, h2 = sha(dev / f), sha(conf / f)
        same = h1 == h2 == md["files"][f] == mc["files"][f]
        rep["files"][f] = {"sha256": h2, "identical": same}
        ok &= same
    ld, lc = (json.loads((d / "layouts.json").read_text()) for d in (dev, conf))
    for role in ld:
        same = json.dumps(ld[role], sort_keys=True) == json.dumps(lc.get(role), sort_keys=True)
        rep["roles"][role] = {"items": len(ld[role]), "identical": same}
        ok &= same
    dev_hashes = {it["structure_hash"] for v in ld.values() for it in v}
    planned = mc["config"]["registry_counts"]
    for role in CONF_ROLES:
        items = lc.get(role, [])
        perK = {K: sum(it["layout"]["K"] == K for it in items) for K in mc["config"]["Ks"]}
        overlap = len({it["structure_hash"] for it in items} & dev_hashes)
        rep["conf_roles"][role] = {"per_K": perK, "planned_registry_entries": planned[role], "overlap_with_dev": overlap}
        ok &= bool(items) and overlap == 0
    # pairwise separation among the confirmation roles themselves (structure hash and generator seed)
    rep["conf_pairwise"] = {}
    for i, r1 in enumerate(CONF_ROLES):
        for r2 in CONF_ROLES[i + 1:]:
            a_, b_ = lc.get(r1, []), lc.get(r2, [])
            n = len({x["structure_hash"] for x in a_} & {x["structure_hash"] for x in b_}) + \
                len({x["layout"]["gen_seed"] for x in a_} & {x["layout"]["gen_seed"] for x in b_})
            rep["conf_pairwise"][f"{r1}|{r2}"] = n
            ok &= n == 0
    rep["registry_sha256"] = {"dev-v2": md["registry_sha256"], "conf-v1": mc["registry_sha256"]}
    rep["planner_failures_conf"] = len(mc["planner_failures"])
    if a.r1:
        r1rep, r1ok = gate_r1(conf, Path(a.r1), mc, lc)
        rep["r1"] = r1rep
        ok &= r1ok
    if a.r2:
        assert a.r1, "--r2 needs --r1 (its base)"
        r1 = Path(a.r1)
        m1, l1 = json.loads((r1 / "manifest.json").read_text()), json.loads((r1 / "layouts.json").read_text())
        r2rep, r2ok = gate_r1(r1, Path(a.r2), m1, l1, roles=R2_ROLES, bank_ref=mc["bank_bin_counts"]["conf_bank/K3"])
        rep["r2"] = r2rep
        ok &= r2ok
    rep["pass"] = bool(ok)
    print(json.dumps(rep, indent=1))
    sys.exit(0 if ok else 1)


def gate_r1(conf, r1, mc, lc, roles=R1_ROLES, bank_ref=None):
    """New roles in dataset r1 over base dataset conf (manifest mc, layouts lc). Used for r1 over conf-v1 and
    for r2 over r1-v1."""
    mr = json.loads((r1 / "manifest.json").read_text())
    lr = json.loads((r1 / "layouts.json").read_text())
    rep, ok = {"files": {}, "conf_roles": {}, "new_roles": {}, "new_pairwise": {}}, True
    for f in sorted(mc["files"]):
        if f in ("registry.json", "layouts.json"):
            continue
        same = sha(conf / f) == sha(r1 / f) == mc["files"][f] == mr["files"][f]
        rep["files"][f] = same
        ok &= same
    for role in lc:
        same = json.dumps(lc[role], sort_keys=True) == json.dumps(lr.get(role), sort_keys=True)
        rep["conf_roles"][role] = same
        ok &= same
    reg = json.loads((r1 / "registry.json").read_text())["roles"]
    keys = lambda items, role: ({x["structure_hash"] for x in items}, {x["layout"]["gen_seed"] for x in items},
                                {e["suffix_hash"] for e in reg[role]})
    old = [keys(lr[r], r) for r in lc]
    old = [set().union(*(o[i] for o in old)) for i in range(3)]
    planned = mr["config"]["registry_counts"]
    for role in roles:
        items = lr.get(role, [])
        new = keys(items, role)
        overlap = {n: len(new[i] & old[i]) for i, n in enumerate(("structure", "gen_seed", "suffix"))}
        perK = {K: sum(it["layout"]["K"] == K for it in items) for K in mr["config"]["Ks"]}
        rep["new_roles"][role] = {"per_K": perK, "planned": planned[role], "overlap_with_all_earlier": overlap}
        ok &= perK[3] == planned[role] and not any(overlap.values())     # only K=3 items are evaluated
    for i, r1_ in enumerate(roles):
        for r2 in roles[i + 1:]:
            k1, k2 = keys(lr.get(r1_, []), r1_), keys(lr.get(r2, []), r2)
            n = sum(len(x & y) for x, y in zip(k1, k2))
            rep["new_pairwise"][f"{r1_}|{r2}"] = n
            ok &= n == 0
    bank_role = next(r for r in roles if r.endswith("_bank"))
    rep["bank_bins_K3"] = mr["bank_bin_counts"].get(f"{bank_role}/K3")
    ok &= rep["bank_bins_K3"] == (bank_ref or mc["bank_bin_counts"]["conf_bank/K3"])
    rep["planner_failures_new"] = len(mr["planner_failures"])
    rep["registry_sha256_new"] = mr["registry_sha256"]
    return rep, ok


if __name__ == "__main__":
    main()
