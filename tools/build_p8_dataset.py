"""Builds the frozen capability-audit dataset from the collection and validation records (PROTOCOL_FREEZE Amendment 10).
No environment actions.

Usage: .venv/bin/python tools/build_p8_dataset.py   -> data/cap-v1/dataset.npz, reports/p8/dataset_manifest.json

Rules (frozen in Amendment 10):
- Rows: labelled prefix states only (status "labelled"). Unique by configuration (grid, pose and inventory; time
  excluded, because the label set does not depend on time) within each group; the first labelled occurrence is kept
  with its own time input, and the multiplicity is recorded. Repeats of a configuration at later times (loops) are
  not new data. Groups are disjoint by layout: train and val are disjoint slices of a fixed rl_train
  permutation; test is r7_conf K=3 items 0-63. Observation keys shared across groups are counted (must be 0).
- Layout provenance: structure hashes of the train, val and test layouts are compared with every other role of
  r7-v1 (in particular bc_train, which the warm-start BC actors saw).
- Training sizes: N = unique labelled training states. S3 = min(N, 200,000); S1 = min(25,000, N // 4); S2 = 100,000 if
  S3 >= 150,000, else round(sqrt(S1 * S3), -3). Subsets are nested by layout: layouts in a fixed permutation
  (seed 20261104); subset k holds all states of the first m_k layouts, m_k the smallest count reaching S_k
  (S3 = N takes every layout).
- Tiny set: 512 rows drawn (seed 20261105) from the training rows that check_label verified without violation.
- Recovery bank: data/r7-v1/recovery_bank_v1.json (480 states; held-out agreement only).
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bc2rl.recovery_bank import STRATA    # noqa: E402

OUT = ROOT / "data/cap-v1"
GROUPS = ("train", "val", "test")


def key(g, a, t):
    """Unit of unique states: the configuration without time (bc2rl.capability.cfg_key); time is kept as an input."""
    return hashlib.sha1(g.tobytes() + a.astype(np.int64).tobytes()).hexdigest()


def latest(job):
    ds = sorted(d for d in (ROOT / ".mae/runs").glob(f"*/{job}") if (d / "summary.json").exists())
    assert ds, job
    return ds[-1]


def ltypes(mask):
    m = np.asarray(mask)
    turn = ((m & 1) | ((m >> 1) & 1)).astype(bool)
    return {"turn": turn, "forward": ((m >> 2) & 1).astype(bool), "pickup": ((m >> 3) & 1).astype(bool),
            "drop": ((m >> 4) & 1).astype(bool), "toggle": ((m >> 5) & 1).astype(bool)}


def main():
    global OUT
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/cap-v1")
    ap.add_argument("--validate-summary", default=None)
    ap.add_argument("--manifest", default="reports/p8/dataset_manifest.json")
    a = ap.parse_args()
    OUT = ROOT / a.data_dir
    vs = Path(a.validate_summary) if a.validate_summary else latest("p8-validate") / "summary.json"
    val_sum = json.loads(vs.read_text())
    audited = set(val_sum["check_label"]["audited_rows"])
    arrays, manifest = {}, {"groups": {}}
    keys, used_layouts = {}, {}
    for gname in GROUPS:
        z = np.load(OUT / f"collect_{gname}.npz")
        n_rows = len(z["status"])
        used_layouts[gname] = np.unique(z["layout"])
        lab = np.flatnonzero(z["status"] == 0)
        first, mult = {}, {}
        for i in lab:
            k = key(z["grid"][i], z["aux"][i], z["time"][i])
            if k not in first:
                first[k] = int(i)
            mult[k] = mult.get(k, 0) + 1
        rows = np.array(sorted(first.values()))
        ks = [key(z["grid"][i], z["aux"][i], z["time"][i]) for i in rows]
        keys[gname] = set(ks)
        arrays.update({f"{gname}_grid": z["grid"][rows], f"{gname}_aux": z["aux"][rows], f"{gname}_time": z["time"][rows],
                       f"{gname}_mask": z["mask"][rows].astype(np.uint8), f"{gname}_stratum": z["stratum"][rows].astype(np.int8),
                       f"{gname}_layout": z["layout"][rows], f"{gname}_row": rows,
                       f"{gname}_mult": np.array([mult[k] for k in ks], np.int32),
                       f"{gname}_category": z["category"][rows]})
        arrays[f"{gname}_categories"] = z["categories"]
        st = z["status"]
        cert_goal = (st != 0) & (z["lb_goal"] > z["remaining"])
        cert_cross = (st != 0) & (z["lb_cross"] > z["remaining"])
        sizes = np.array([bin(int(m)).count("1") for m in z["mask"][rows]])
        lt = ltypes(z["mask"][rows])
        manifest["groups"][gname] = {
            "rows": int(n_rows), "labelled_rows": int(len(lab)), "unique_labelled": int(len(rows)),
            "layouts": int(len(np.unique(z["layout"]))), "layouts_with_labelled": int(len(np.unique(z["layout"][rows]))),
            "status_rows": {s: int((st == i).sum()) for i, s in enumerate(("labelled", "time_exceeded", "unresolved", "at_goal"))},
            "unlabelled_certified_impossible_module": int(cert_goal.sum()),
            "unlabelled_certified_impossible_boundary": int(cert_cross.sum()),
            "unlabelled_not_certified": int(((st != 0) & ~cert_goal).sum()),
            "stratum_unique": {s: int((z["stratum"][rows] == i).sum()) for i, s in enumerate(STRATA)},
            "stratum_unique_share": {s: float((z["stratum"][rows] == i).mean()) for i, s in enumerate(STRATA)},
            "label_size": {str(k): int((sizes == k).sum()) for k in range(1, 7) if (sizes == k).any()},
            "label_type_share": {k: float(v.mean()) for k, v in lt.items()},
            "mean_multiplicity": float(np.mean([mult[k] for k in ks]))}
    manifest["cross_group_shared_observations"] = {f"{a}-{b}": len(keys[a] & keys[b])
                                                   for i, a in enumerate(GROUPS) for b in GROUPS[i + 1:]}
    # layout provenance by structure hash
    lay = json.loads((ROOT / "data/r7-v1/layouts.json").read_text())
    cfg = json.loads((ROOT / "experiments/p8/collect-v1.json").read_text())
    hashes = {}
    for g in cfg["groups"]:                       # the layouts actually present in each collection file
        role3 = [it for it in lay[g["role"]] if it["layout"]["K"] == 3]
        hashes[g["name"]] = {role3[int(i)]["structure_hash"] for i in used_layouts[g["name"]]}
    other = {r: {it["structure_hash"] for it in v} for r, v in lay.items()}
    manifest["layout_provenance"] = {
        g: {"overlap_with_roles": {r: len(h & other[r]) for r in other if len(h & other[r])}} for g, h in hashes.items()}
    manifest["layout_group_overlap"] = {f"{a}-{b}": len(hashes[a] & hashes[b]) for a in hashes for b in hashes if a < b}
    # nested training subsets
    N = len(arrays["train_mask"])
    S3 = min(N, 200_000)
    S1 = min(25_000, N // 4)
    S2 = 100_000 if S3 >= 150_000 else int(round(np.sqrt(S1 * S3), -3))
    tl = arrays["train_layout"]
    order = np.random.default_rng(20261104).permutation(np.unique(tl))
    counts = np.array([(tl == l).sum() for l in order])
    cum = np.cumsum(counts)
    subsets = {}
    for k, S in enumerate((S1, S2, S3)):
        m = len(order) if S >= N else int(np.searchsorted(cum, S) + 1)
        sel = set(order[:m].tolist())
        idx = np.flatnonzero(np.isin(tl, list(sel)))
        if S3 == N and k == 2:
            idx = np.arange(N)
        arrays[f"subset_{k}"] = idx
        subsets[k] = {"target": int(S), "states": int(len(idx)), "layouts": int(m)}
    manifest["subsets"] = subsets
    for k in (0, 1):
        assert set(arrays[f"subset_{k}"]) <= set(arrays[f"subset_{k + 1}"]), "subsets not nested"
    # tiny audited set
    zt = np.load(OUT / "collect_train.npz")
    trow = arrays["train_row"]
    pos = {int(r): i for i, r in enumerate(trow)}
    aud = sorted(pos[r] for r in audited if r in pos)
    pick = np.sort(np.random.default_rng(20261105).choice(len(aud), min(512, len(aud)), replace=False))
    tiny = np.array(aud)[pick]
    for f in ("grid", "aux", "time", "mask", "stratum"):
        arrays[f"tiny_{f}"] = arrays[f"train_{f}"][tiny]
    arrays["tiny_index"] = tiny
    manifest["tiny"] = {"states": int(len(tiny)), "audited_pool": len(aud),
                        "stratum": {s: int((arrays["tiny_stratum"] == i).sum()) for i, s in enumerate(STRATA)}}
    # recovery bank
    rb = json.loads((ROOT / "data/r7-v1/recovery_bank_v1.json").read_text())
    st = rb["states"]
    arrays["recov_grid"] = np.array([s["obs"]["grid"] for s in st], np.uint8)
    arrays["recov_aux"] = np.array([s["obs"]["aux"] for s in st], np.int8)
    arrays["recov_time"] = np.array([s["obs"]["time"][0] for s in st], np.float32)
    arrays["recov_mask"] = np.array([s["mask"] for s in st], np.uint8)
    arrays["recov_stratum"] = np.array([STRATA.index(s["stratum"]) for s in st], np.int8)
    arrays["recov_layout"] = np.array([s["item"] for s in st], np.int32)
    manifest["recov"] = {"states": len(st), "sha256": rb["sha256"]}
    path = OUT / "dataset.npz"
    np.savez_compressed(path, **arrays)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["dataset"] = {"path": str(path.relative_to(ROOT)), "sha256": h}
    manifest["collect_sha256"] = {g: hashlib.sha256((OUT / f"collect_{g}.npz").read_bytes()).hexdigest() for g in GROUPS}
    mp = ROOT / a.manifest
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps({k: manifest[k] for k in ("subsets", "tiny", "cross_group_shared_observations",
                                                "layout_group_overlap")}, indent=1))
    print(json.dumps({g: {k: v for k, v in manifest["groups"][g].items() if k in
                          ("rows", "labelled_rows", "unique_labelled", "layouts", "stratum_unique_share")}
                      for g in GROUPS}, indent=1))


if __name__ == "__main__":
    main()
