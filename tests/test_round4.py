import numpy as np
import pandas as pd
import pytest

from bearing import config, prereg, round2, round3, round4
from conftest import fake_features

FORCE_LOW = "N15_M07_F04"     # same speed and torque as the plant condition N15_M07_F10; only the force differs


@pytest.fixture(scope="module")
def rules():
    return prereg.load()


def test_round4_rules_point_at_the_frozen_rounds():
    r4 = round4.load_rules()
    assert r4["round1_fingerprint"] == prereg.fingerprint()
    assert r4["round2_fingerprint"] == round2.fingerprint()
    assert r4["round3_fingerprint"] == round3.fingerprint()
    assert r4["detector"] in {c["name"] for c in r4["candidates_reported_not_chosen"]}


def test_fleet_normal_never_uses_the_force():
    """Two conditions that differ only in force must be normalised against the same fleet (FR-002)."""
    df = fake_features(n_rec=4)
    ref = [b for b in config.ALL_BEARINGS]
    a = round4.fleet_normal(df, ["band_00"], ref)
    moved = df.copy()
    moved.loc[moved.condition == FORCE_LOW, "condition"] = "N15_M07_F99"   # rename the force: nothing may change
    b = round4.fleet_normal(moved, ["band_00"], ref)
    np.testing.assert_allclose(a.band_00.to_numpy(), b.band_00.to_numpy())
    same_setting = df.condition.isin([FORCE_LOW, config.PLANT_CONDITION])
    keys = round4.drive_key(df[same_setting])
    assert keys.nunique() == 1


def test_round3_did_group_by_force():
    """The audit finding, pinned: round 3's sealed fleet normal splits two conditions that differ only in force."""
    df = fake_features(n_rec=4)
    df.loc[df.condition == FORCE_LOW, "band_00"] += 10.0
    ref = [b for b in config.ALL_BEARINGS]
    r3 = round3.fleet_normal(df, ["band_00"], ref)
    r4 = round4.fleet_normal(df, ["band_00"], ref)
    m = df.condition == FORCE_LOW
    assert abs(r3.loc[m, "band_00"].median()) < 0.5          # round 3 cancelled the force shift (it knew the force)
    assert r4.loc[m, "band_00"].median() > 0.5               # round 4 cannot, as a drive cannot


def test_fleet_normal_never_reads_labels():
    df = fake_features(n_rec=3)
    ref = ["K001", "KA01", "KI01"]
    a = round4.fleet_normal(df, ["band_00", "band_01"], ref)
    b = round4.fleet_normal(df.assign(label=1 - df.label), ["band_00", "band_01"], ref)
    pd.testing.assert_frame_equal(a[["band_00", "band_01"]], b[["band_00", "band_01"]])


def test_fleet_normal_uses_only_the_reference_bearings():
    df = fake_features(n_rec=3)
    ref = ["K001", "KA01", "KI01"]
    changed = df.copy()
    changed.loc[changed.bearing == "K006", "band_00"] += 100.0
    a = round4.fleet_normal(df, ["band_00"], ref)
    b = round4.fleet_normal(changed, ["band_00"], ref)
    other = df.bearing != "K006"
    np.testing.assert_allclose(a.loc[other, "band_00"], b.loc[other, "band_00"])


def test_leave_one_condition_out_never_reads_labels_at_the_held_out_condition(rules):
    df = fake_features(n_rec=3)
    cand = {"features": ["band_"], "normal": "fleet"}
    held = config.CONDITIONS[1]
    train_c = [c for c in config.CONDITIONS if c != held]
    train_b = [b for f, bs in rules["folds"].items() if f != "1" for b in bs]
    a = round4.score_fold(df, cand, train_b, rules["folds"]["1"], rules, train_c, [held])
    flipped = df.copy()
    flipped.loc[flipped.condition == held, "label"] = 1 - flipped.loc[flipped.condition == held, "label"]
    b = round4.score_fold(flipped, cand, train_b, rules["folds"]["1"], rules, train_c, [held])
    np.testing.assert_allclose(a["p"], b["p"])
    assert set(a["test"].condition) == {held}


def test_test_bearings_never_shape_the_fleet(rules):
    df = fake_features(n_rec=3)
    cand = {"features": ["band_"], "normal": "fleet"}
    test_b = rules["folds"]["1"]
    train_b = [b for f, bs in rules["folds"].items() if f != "1" for b in bs]
    a = round4.score_fold(df, cand, train_b, test_b, rules)
    moved = df.copy()
    moved.loc[moved.bearing.isin(test_b), "band_01"] += 5.0       # a noise band: only the test bearings move
    b = round4.score_fold(moved, cand, train_b, test_b, rules)
    other = ~a["normalized"].bearing.isin(test_b)
    np.testing.assert_allclose(a["normalized"].loc[other, "band_01"], b["normalized"].loc[other, "band_01"])


def test_loco_reports_every_condition_and_the_mean(rules):
    df = fake_features(n_rec=3, separation=3.0)
    out = round4.loco(df, {"features": ["band_"], "normal": "fleet"}, rules, n_boot=20)
    assert set(out["per_condition"]) == set(config.CONDITIONS)
    bas = [v["forced_ba"] for v in out["per_condition"].values()]
    assert out["mean_ba"] == pytest.approx(np.mean(bas), abs=1e-3)
    assert set(out["subsets"]) == {"real wear, one ring", "real wear, all", "lab-made damage", "all damage"}
    assert out["subsets"]["real wear, one ring"]["n_damaged_bearings"] == len(round4.REAL_ONE_RING)


def test_real_one_ring_list_is_real_wear_without_both_ring_bearings():
    real = {b for b in config.ALL_BEARINGS if config.damage_origin(b) == "real"}
    assert set(round4.REAL_ONE_RING) == real - set(round4.BOTH_RINGS)
