import json

import numpy as np
import pandas as pd
import pytest

from bearing import config, prereg, round2
from conftest import fake_features


def fake_round2(signal_in: str = "contrast", n_rec: int = 5, seed: int = 1) -> pd.DataFrame:
    """Round-1 style table plus round-2 columns. Only `signal_in` carries the label."""
    df = fake_features(n_rec=n_rec, separation=0.0, seed=seed)          # shape bands carry nothing here
    rng = np.random.default_rng(seed)
    y = df["label"].to_numpy()
    for k in range(4):
        sep = 2.0 if signal_in == "contrast" and k == 0 else 0.0
        df[f"contrast_o{k + 1}"] = rng.normal(sep * y, 1.0)
    for name in ("click_kurt", "click_crest"):
        sep = 2.0 if signal_in == "clicks" and name == "click_kurt" else 0.0
        df[name] = rng.normal(sep * y, 1.0)
    return df


@pytest.fixture(scope="module")
def rules2():
    r = prereg.load()
    r2 = round2.load_rules()
    return r, r2


def test_round2_rules_are_complete(rules2):
    _, r2 = rules2
    assert [c["name"] for c in r2["candidates"]] == [
        "shape+lr", "contrast+lr", "contrast_clicks+lr", "shape+rf", "contrast+rf", "contrast_clicks+rf"]
    assert r2["round1_fingerprint"] == prereg.fingerprint()


def test_no_test_bearing_is_used_even_while_choosing(rules2, monkeypatch):
    rules, r2 = rules2
    df = fake_round2()
    seen = []
    original = round2._fit
    monkeypatch.setattr(round2, "_fit", lambda train, cols, model: (seen.append(set(train.bearing)),
                                                                     original(train, cols, model))[1])
    small = {**r2, "candidates": r2["candidates"][:2]}
    out = round2.outer_predictions(df, rules, small)
    folds = list(rules["folds"].values())
    per_fold = len(seen) // len(folds)
    for k, test_bearings in enumerate(folds):
        for s in seen[k * per_fold:(k + 1) * per_fold]:
            assert not s & set(test_bearings)
    assert sorted(out["selected"].bearing.unique()) == sorted(config.ALL_BEARINGS)


def test_selector_finds_the_set_that_carries_the_signal(rules2):
    rules, r2 = rules2
    small = {**r2, "candidates": [c for c in r2["candidates"] if c["model"] == "lr"]}
    out = round2.outer_predictions(fake_round2("contrast"), rules, small)
    assert set(out["chosen"].values()) <= {"contrast+lr", "contrast_clicks+lr"}
    s = round2.summarize_round(out, rules, n_boot=30)
    assert s["selected"]["forced_ba"] > 0.75
    assert s["candidates"]["shape+lr"]["forced_ba"] < 0.65


def test_rf_candidate_runs_and_gives_evidence(rules2):
    rules, r2 = rules2
    small = {**r2, "candidates": [c for c in r2["candidates"] if c["name"] == "contrast_clicks+rf"]}
    df = fake_round2("clicks")
    out = round2.outer_predictions(df, rules, small)
    model, cols, th = out["models"]["1"]
    rest = df[df.bearing != "KA01"]
    ev = round2.evidence(model, cols, df[df.bearing == "KA01"][cols].to_numpy(),
                         rest[cols].to_numpy(), rest["label"].to_numpy(), "check bearing")
    assert 1 <= len(ev) <= 2 and all("than the average motor in training" in e for e in ev)


def test_plant_switch_rule():
    assert round2.use_round2_for_plant({"ci": [0.52, 0.7]}) is True
    assert round2.use_round2_for_plant({"ci": [0.5, 0.7]}) is False
    assert round2.use_round2_for_plant({"ci": [0.3, 0.9]}) is False


def test_phrases_for_new_features():
    assert "sharper peak" in round2.phrase("contrast_fe_minus_o1", True)
    assert "outer-ring" in round2.phrase("contrast_o2", True)
    assert "inner-ring" in round2.phrase("contrast_fe_plus_i2", False)
    assert "clicks" in round2.phrase("click_kurt_hf", True)
    assert "healthy" not in round2.phrase("click_crest", False)


def test_run_round2_writes_files(tmp_path, rules2):
    rules, r2 = rules2
    df = fake_round2("contrast", n_rec=10)
    df16 = df.copy()
    df16["setting"] = "16k_12b"
    f1, f2 = tmp_path / "f1.parquet", tmp_path / "f2.parquet"
    both = pd.concat([df, df16])
    round1_cols = [c for c in both.columns if not c.startswith(("contrast_", "click_"))]
    keys = ["bearing", "condition", "rec", "setting"]
    both[round1_cols].to_parquet(f1)
    both[keys + [c for c in both.columns if c.startswith(("contrast_", "click_"))] + ["usable"]].to_parquet(f2)
    rules = {**rules, "quality_settings": {"lab": [64000, None], "16k_12b": [16000, 12]},
             "plant_view": {**rules["plant_view"], "min_recordings": 5}}
    small = {**r2, "candidates": [c for c in r2["candidates"] if c["model"] == "lr"]}
    res = tmp_path / "results"
    res.mkdir()
    (res / "summary.json").write_text(json.dumps({"plant": {"catch_rate": 0.1}, "runs": {}}))
    (res / "motors.json").write_text("[]")
    out = round2.run_round2(f1, f2, res, rules=rules, rules2=small, n_boot=30)
    summary = json.loads((res / "summary.json").read_text())
    assert set(summary["round2"]["runs"]) == {"lab", "16k_12b"}
    assert summary["round2"]["plant_switched"] == out["plant_switched"]
    if out["plant_switched"]:
        motors = json.loads((res / "motors.json").read_text())
        assert len(motors) == 32 and motors[0]["detector"].startswith("round 2")


def test_plant_run_follows_the_sealed_switch():
    """The score quoted for the plant view must be the run the plant view really uses."""
    r1 = {"forced_ba": 0.44}
    summary = {"plant_key": "shape|16k_12b", "runs": {"shape|16k_12b": r1}, "plant_view_setting": "16k_12b"}
    assert round2.plant_run(summary) is r1
    sel = {"forced_ba": 0.80}
    summary.update(round2={"plant_switched": True, "runs": {"16k_12b": {"selected": sel}}},
                   plant_round1={"catch_rate": 0.65})
    assert round2.plant_run(summary) is sel
