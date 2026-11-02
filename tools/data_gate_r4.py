"""Data gate for r4-v1 (owner instruction 2026-11-01c; PROTOCOL_FREEZE Amendment 6). Pure file checks; no actions.

Usage: .venv/bin/python tools/data_gate_r4.py [--base data/r3-v1] [--new data/r4-v1] [--out reports/a4/data_gate.json]

Passes only if
  - every r3-v1 file except registry.json, layouts.json and manifest.json is byte-identical in r4-v1 (SHA-256
    recomputed), so the BC, RL-training, reset and anchor data and every earlier bank are unchanged;
  - every r3-v1 layout role is identical in r4-v1, and every r3-v1 registry role is identical;
  - the A4 roles hold exactly the planned K=3 counts (a4_select 64, a4_bank 128, a4_final 256, a4_donor 512) and
    share no structure hash, generator seed or suffix hash with any earlier role or with each other;
  - bank_competence_a4_bank.json holds exactly 128 K=3 states, all labelled "entry", each the planner's first state
    after the crossing (step_count == tau, accessed), with the original remaining time (limit - tau > 0), one per donor
    layout, and the donors are the first 128 a4_bank K=3 layouts;
  - r4-v1's manifest records no planner failure.
Prints a JSON report; exit status 1 on any failure.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
NEW = {"a4_select": 64, "a4_bank": 128, "a4_final": 256, "a4_donor": 512}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "data/r3-v1"))
    ap.add_argument("--new", default=str(ROOT / "data/r4-v1"))
    ap.add_argument("--out", default=str(ROOT / "reports/a4/data_gate.json"))
    a = ap.parse_args(argv)
    base, new = Path(a.base), Path(a.new)
    fails, rep = [], {}
    for f in sorted(base.iterdir()):
        if f.name in ("registry.json", "layouts.json", "manifest.json"):
            continue
        if not (new / f.name).exists() or sha(f) != sha(new / f.name):
            fails.append(f"file changed or missing: {f.name}")
    rep["unchanged_files"] = sorted(f.name for f in base.iterdir() if f.name not in ("registry.json", "layouts.json", "manifest.json"))
    bl, nl = json.loads((base / "layouts.json").read_text()), json.loads((new / "layouts.json").read_text())
    for role, items in bl.items():
        if nl.get(role) != items:
            fails.append(f"layout role changed: {role}")
    br, nr = json.loads((base / "registry.json").read_text())["roles"], json.loads((new / "registry.json").read_text())["roles"]
    for role, e in br.items():
        if nr.get(role) != e:
            fails.append(f"registry role changed: {role}")
    struct, seeds, suff = {}, {}, {}
    for role, entries in nr.items():
        for e in entries:
            for h in e["structure_hash"].values():
                struct.setdefault(h, set()).add(role)
            seeds.setdefault(e["seed"], set()).add(role)
            suff.setdefault(e["suffix_hash"], set()).add(role)
    for role, n in NEW.items():
        k3 = [it for it in nl.get(role, []) if it["layout"]["K"] == 3]
        if len(k3) != n or len(nr.get(role, [])) != n:
            fails.append(f"{role}: {len(k3)} K=3 layouts, {len(nr.get(role, []))} registry entries (planned {n})")
        for e in nr.get(role, []):
            shared = set().union(*(struct[h] for h in e["structure_hash"].values()), seeds[e["seed"]], suff[e["suffix_hash"]]) - {role}
            if shared:
                fails.append(f"{role} seed {e['seed']} shares structure/seed/suffix with {sorted(shared)}")
                break
    bank = json.loads((new / "bank_competence_a4_bank.json").read_text())
    states = bank.get("3", [])
    donors = [it for it in nl["a4_bank"] if it["layout"]["K"] == 3][:128]
    ok_states = (list(bank) == ["3"] and len(states) == 128 and all(s["bin"] == "entry" for s in states)
                 and all(s["snapshot"]["step_count"] == d["tau"] and s["snapshot"]["accessed"] and s["snapshot"]["tau"] == d["tau"]
                         and s["remaining"] == d["layout"]["limit"] - d["tau"] > 0 and s["donor_seed"] == d["layout"]["gen_seed"]
                         and s["suffix_offset"] == 0 for s, d in zip(states, donors)))
    if not ok_states:
        fails.append("a4_bank entry bank: count, labels, entry timing, remaining time or donor order wrong")
    rep["entry_bank"] = {"states": len(states), "remaining_min": min((s["remaining"] for s in states), default=None),
                         "remaining_max": max((s["remaining"] for s in states), default=None)}
    man = json.loads((new / "manifest.json").read_text())
    if man["planner_failures"]:
        fails.append(f"planner failures: {len(man['planner_failures'])}")
    rep.update(counts={r: len([it for it in nl.get(r, []) if it["layout"]["K"] == 3]) for r in NEW},
               rejected_in_registry=len(json.loads((new / "registry.json").read_text())["rejected"]),
               failures=fails, passed=not fails)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
