"""Training-role gate for confirmation data (PROTOCOL_FREEZE section 1, Amendments 1 and 2).

Usage: .venv/bin/python tools/data_gate.py [--dev data/dev-v2] [--conf data/conf-v1]

Passes only if
  - traj_*.npz for bc_train, bc_val, reset_donor, anchor_donor, dev_bank and banks_index.npz are byte-identical
    (SHA-256, recomputed from the files, and equal to each manifest);
  - bank_competence_dev_bank.json is byte-identical;
  - layouts.json entries for every dev-v2 role are identical in conf-v1;
  - the confirmation roles exist with the planned counts and share no structure hash with any dev-v2 role.
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


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default=str(ROOT / "data/dev-v2"))
    ap.add_argument("--conf", default=str(ROOT / "data/conf-v1"))
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
    rep["registry_sha256"] = {"dev-v2": md["registry_sha256"], "conf-v1": mc["registry_sha256"]}
    rep["planner_failures_conf"] = len(mc["planner_failures"])
    rep["pass"] = bool(ok)
    print(json.dumps(rep, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
