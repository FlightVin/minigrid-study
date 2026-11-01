"""Frozen calibration selection rule (tools/analyze_cal.py; written before calibration data)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import analyze_cal as C    # noqa: E402


def v(q1, q3, e1, e3, p1=0.3, p3=0.05):
    return {1: {"q": q1, "entry": e1, "P1": p1}, 3: {"q": q3, "entry": e3, "P1": p3}}


def test_targets():
    assert C.qualifies(v(0.8, 0.2, 0.6, 0.6))[0]
    assert set(C.qualifies(v(0.7, 0.45, 0.5, 0.6, p1=0.7))[1]) == {"K1_access", "K3_access", "K1_entry", "K1_room"}
    assert C.qualifies(v(0.75, 0.05, 0.55, 0.55, p1=0.6))[0]          # boundaries are inclusive
    assert not C.qualifies(v(0.8, 0.04, 0.6, 0.6))[0]


def test_selection_order():
    ok, no = (True,), (False,)
    assert C.select({(0.2, 8000): ok, (0.8, 4000): ok, (0.2, 4000): ok}) == (0.2, 4000)   # fewer updates, then tie on |rho-0.5| -> smaller rho
    assert C.select({(0.2, 4000): ok, (0.5, 8000): ok}) == (0.2, 4000)
    assert C.select({(0.5, 4000): ok, (0.2, 4000): ok}) == (0.5, 4000)
    assert C.select({(0.5, 4000): no, (0.8, 8000): ok}) == (0.8, 8000)
    assert C.select({(0.5, 4000): no}) is None
