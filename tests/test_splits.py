import pytest

from bc2rl import splits as S
from bc2rl import task as T


def test_role_seeds_are_disjoint_and_stable():
    seen = {}
    for role in S.ROLE_NAMESPACE:
        for i in range(500):
            s = S.role_seed(role, i)
            assert s not in seen, (role, seen.get(s))
            seen[s] = role
    assert S.role_seed("conf_final", 0) == S.role_seed("conf_final", 0)


def test_registry_is_disjoint_and_check_catches_overlap():
    reg = S.build_registry({r: 20 for r in S.ROLE_ORDER})
    stats = S.check_registry(reg)
    assert stats["distinct_training_suffixes"] > 0
    bad = {**reg, "roles": {**reg["roles"], "conf_final": reg["roles"]["conf_final"] + [reg["roles"]["bc_train"][0]]}}
    with pytest.raises(AssertionError):
        S.check_registry(bad)


def test_matched_K_layouts_share_suffix():
    seed = S.role_seed("dev_eval", 0)
    a, b = T.generate_layout(1, seed), T.generate_layout(3, seed)
    assert S.suffix_hash(a) == S.suffix_hash(b) and a.structure_hash() != b.structure_hash()


def test_check_catches_suffix_leak():
    reg = S.build_registry({r: 20 for r in S.ROLE_ORDER})
    leak = dict(reg["roles"]["conf_final"][0], suffix_hash=reg["roles"]["bc_train"][0]["suffix_hash"])
    bad = {**reg, "roles": {**reg["roles"], "conf_final": reg["roles"]["conf_final"][1:] + [leak]}}
    with pytest.raises(AssertionError):
        S.check_registry(bad)


def test_enlarging_last_role_keeps_every_earlier_entry():
    """conf_final is last in ROLE_ORDER: a larger count only appends conf_final layouts."""
    small = {"dev_eval": 4, "conf_select": 3, "conf_bank": 3, "conf_final": 2}
    big = dict(small, conf_final=5)
    a, b = S.build_registry(small), S.build_registry(big)
    for role in small:
        n = small[role]
        assert b["roles"][role][:n] == a["roles"][role]
    assert len(b["roles"]["conf_final"]) == 5
