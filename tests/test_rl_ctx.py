"""Ctx layout selection (no environment actions)."""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("MAE_PROJECT", ROOT))     # data are untracked; a runner job runs from a source snapshot
DS = PROJECT / "data/dev-v2"


@pytest.mark.skipif(not DS.exists(), reason="needs dev-v2 data")
def test_diag_role_selects_separate_layouts(tmp_path, monkeypatch):
    from bc2rl import rl
    monkeypatch.setenv("MAE_PROJECT", str(PROJECT))
    monkeypatch.setenv("MAE_RUN_DIR", str(tmp_path))
    cfg = json.loads((ROOT / "experiments/m3/dev-v1.json").read_text())
    same = rl.Ctx(cfg, 3, 0)
    assert same.diag_layouts == same.eval_layouts
    sep = rl.Ctx({**cfg, "diag_role": "dev_bank"}, 3, 0)
    assert len(sep.diag_layouts) == 64 and len(sep.eval_layouts) == 32
    assert not {L.structure_hash() for L in sep.diag_layouts} & {L.structure_hash() for L in sep.eval_layouts}
