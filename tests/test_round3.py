import numpy as np
import pandas as pd
import pytest

from bearing import config, prereg, round2, round3
from bearing.features import BAND_EDGES
from conftest import fake_features


@pytest.fixture(scope="module")
def rules3():
    return prereg.load(), round3.load_rules()


def test_round3_rules_point_at_the_frozen_rounds(rules3):
    _, r3 = rules3
    assert r3["round1_fingerprint"] == prereg.fingerprint()
    assert r3["round2_fingerprint"] == round2.fingerprint()
    assert r3["detector"] in {c["name"] for c in r3["candidates_reported_not_chosen"]}


def test_damage_levels_match_lessmeier_tables_4_and_5(rules3):
    _, r3 = rules3
    levels = r3["damage_levels"]
    damaged = [b for b in config.ALL_BEARINGS if config.label(b) == 1]
    assert sorted(levels) == sorted(damaged)
    counts = {lv: sum(v == lv for v in levels.values()) for lv in (1, 2, 3)}
    assert counts == {1: 15, 2: 9, 3: 2}


def test_low_bands_stop_at_1_khz():
    assert round3.LOW_BANDS
    assert all(BAND_EDGES[int(c.split("_")[1]) + 1] <= 1000 for c in round3.LOW_BANDS)


def test_fleet_normal_never_reads_labels():
    df = fake_features(n_rec=3)
    ref = ["K001", "KA01", "KI01"]
    a = round3.fleet_normal(df, ["band_00", "band_01"], ref)
    b = round3.fleet_normal(df.assign(label=1 - df.label), ["band_00", "band_01"], ref)
    pd.testing.assert_frame_equal(a[["band_00", "band_01"]], b[["band_00", "band_01"]])


def test_fleet_normal_uses_only_the_reference_bearings():
    df = fake_features(n_rec=3)
    ref = ["K001", "KA01", "KI01"]
    changed = df.copy()
    changed.loc[changed.bearing == "K006", "band_00"] += 100.0      # a non-reference bearing
    a = round3.fleet_normal(df, ["band_00"], ref)
    b = round3.fleet_normal(changed, ["band_00"], ref)
    other = df.bearing != "K006"
    np.testing.assert_allclose(a.loc[other, "band_00"], b.loc[other, "band_00"])


def test_fleet_normal_is_per_condition():
    df = fake_features(n_rec=4)
    shifted = df.copy()
    shifted.loc[shifted.condition == config.LOW_LOAD_CONDITION, "band_00"] += 50.0   # a load shifts every motor
    ref = [b for b in config.ALL_BEARINGS]
    a = round3.fleet_normal(df, ["band_00"], ref)
    b = round3.fleet_normal(shifted, ["band_00"], ref)
    np.testing.assert_allclose(a.band_00, b.band_00, atol=1e-6)


def test_fleet_normal_refuses_a_condition_without_reference():
    df = fake_features(n_rec=2)
    ref_only_one = df[df.condition == config.PLANT_CONDITION].bearing.unique()[:3]
    df2 = df[(df.condition == config.PLANT_CONDITION) | ~df.bearing.isin(ref_only_one)]
    with pytest.raises(ValueError):
        round3.fleet_normal(df2, ["band_00"], [b for b in ref_only_one])


def test_new_load_test_never_uses_labels_at_the_new_load(rules3):
    rules, r3 = rules3
    df = fake_features(n_rec=3)
    cand = {"features": ["band_"], "normal": "fleet"}
    train_c, test_c = rules["load_shift"][0]
    train_b = [b for f, bs in rules["folds"].items() if f != "1" for b in bs]
    a = round3.score_fold(df, cand, train_b, rules["folds"]["1"], rules, [train_c], [test_c])
    flipped = df.copy()
    at_new = flipped.condition == test_c
    flipped.loc[at_new, "label"] = 1 - flipped.loc[at_new, "label"]       # labels at the new load are never read
    flipped.loc[at_new & flipped.bearing.isin(rules["folds"]["1"]), "label"] = \
        df.loc[at_new & df.bearing.isin(rules["folds"]["1"]), "label"]    # keep the test labels for scoring only
    b = round3.score_fold(flipped, cand, train_b, rules["folds"]["1"], rules, [train_c], [test_c])
    np.testing.assert_allclose(a["p"], b["p"])


def test_test_bearings_never_train_or_shape_the_fleet(rules3, monkeypatch):
    rules, _ = rules3
    df = fake_features(n_rec=2)
    seen_ref, seen_fit = [], []
    orig_norm, orig_fit = round3.fleet_normal, round2._fit
    monkeypatch.setattr(round3, "fleet_normal", lambda d, c, ref: (seen_ref.append(set(ref)), orig_norm(d, c, ref))[1])
    monkeypatch.setattr(round2, "_fit", lambda t, c, m: (seen_fit.append(set(t.bearing)), orig_fit(t, c, m))[1])
    test_b = rules["folds"]["2"]
    train_b = [b for f, bs in rules["folds"].items() if f != "2" for b in bs]
    round3.score_fold(df, {"features": ["band_"], "normal": "fleet"}, train_b, test_b, rules)
    assert seen_ref and seen_fit
    assert all(not s & set(test_b) for s in seen_ref + seen_fit)


def test_ring_labels_skip_both_ring_bearings():
    assert round3.ring_label("KA04") == 1 and round3.ring_label("KI14") == 0
    assert round3.ring_label("KB23") is None and round3.ring_label("K001") is None


def test_ring_word_follows_the_sealed_rule():
    assert round3.ring_word(0.8, True) == "outer ring likely"
    assert round3.ring_word(0.2, True) == "inner ring likely"
    assert round3.ring_word(0.5, True) == "cannot tell"
    assert round3.ring_word(0.9, False) == "cannot tell"


def test_plant_switch_needs_every_range_above_chance():
    ok, bad = {"ci": [0.6, 0.9]}, {"ci": [0.45, 0.8]}
    assert round3.use_round3_for_plant(ok, {"a": ok, "b": ok})
    assert not round3.use_round3_for_plant(ok, {"a": ok, "b": bad})
    assert not round3.use_round3_for_plant(bad, {"a": ok, "b": ok})


def test_by_level_counts_bearings(rules3):
    _, r3 = rules3
    pred = pd.DataFrame({"bearing": ["KB24", "KB24", "KA01", "K001"], "label": [1, 1, 1, 0],
                         "forced": [1, 0, 1, 1]})
    out = round3.by_level(pred, r3["damage_levels"])
    assert out == {"1": {"share_flagged": 1.0, "n_bearings": 1}, "3": {"share_flagged": 0.5, "n_bearings": 1}}
