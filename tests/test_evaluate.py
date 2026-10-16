import json

import numpy as np

from bearing import evaluate, prereg, verdicts


def test_no_test_bearing_is_ever_trained_on(fake_df, monkeypatch):
    rules = prereg.load()
    calls = []
    original = evaluate._fit
    monkeypatch.setattr(evaluate, "_fit", lambda train, cols: (calls.append(set(train.bearing)), original(train, cols))[1])
    pred, _ = evaluate.outer_fold_predictions(fake_df, "shape", rules["folds"], rules)
    folds = list(rules["folds"].values())
    assert len(calls) == len(folds) * len(folds)          # 5 inner + 1 final per outer fold
    for k, test_bearings in enumerate(folds):
        for seen in calls[k * len(folds):(k + 1) * len(folds)]:
            assert not seen & set(test_bearings)
    assert sorted(pred.bearing.unique()) == sorted(fake_df.bearing.unique())
    assert pred.groupby("bearing").fold.nunique().max() == 1


def test_signal_is_found_and_setting_only_is_chance(fake_df):
    rules = prereg.load()
    shape, _ = evaluate.outer_fold_predictions(fake_df, "shape", rules["folds"], rules)
    meta, _ = evaluate.outer_fold_predictions(fake_df, "setting_only", rules["folds"], rules)
    s = evaluate.summarize(shape, 0, None, rules)
    m = evaluate.summarize(meta, 0, None, rules)
    assert s["forced_ba"] > 0.8
    assert 0.35 < m["forced_ba"] < 0.65


def test_always_damaged_scores_one_half(fake_df):
    rules = prereg.load()
    pred, _ = evaluate.outer_fold_predictions(fake_df, "always_damaged", rules["folds"], rules)
    assert evaluate.summarize(pred, 0, None, rules, n_boot=50)["forced_ba"] == 0.5


def test_summary_marks_undefined():
    import pandas as pd
    rows = []
    for b, y in [("K001", 0), ("K002", 0), ("KA01", 1), ("KA03", 1)]:
        for r in range(5):
            rows.append({"bearing": b, "condition": "N15_M07_F10", "rec": r, "label": y,
                         "origin": "healthy" if y == 0 else "artificial", "fold": "1",
                         "p": 0.55 if y == 0 else 0.9, "line": 0.5, "band": 0.1, "medium": 0.2, "forced": 1,
                         "verdict": verdicts.PERSON if y == 0 else verdicts.DAMAGED})
    s = evaluate.summarize(pd.DataFrame(rows), 0, None, prereg.load(), n_boot=50)
    assert s["decided_ba"] == "undefined"        # only damaged recordings were decided (HR-18)
    assert s["forced_ba"] == 0.5
    assert s["decided_nothing"] is False


def test_feature_columns_never_include_force_or_lab_measurements(fake_df):
    for det in ("shape", "tones", "loudness", "setting_only"):
        cols = evaluate.feature_columns(fake_df, det)
        assert not any(c in cols for c in ("force", "speed", "torque_measured", "label", "bearing"))


def test_motor_table_and_files(fake_df, tmp_path):
    path = tmp_path / "features.parquet"
    df = fake_df.copy()
    df16 = df.copy()
    df16["setting"] = "16k_12b"
    import pandas as pd
    pd.concat([df, df16]).to_parquet(path)
    rules = prereg.load()
    rules["quality_settings"] = {"lab": [64000, None], "16k_12b": [16000, 12]}
    rules["detectors"] = ["shape", "setting_only", "always_damaged"]
    rules["plant_view"]["min_recordings"] = 5
    summary = evaluate.run_all(path, tmp_path / "results", rules=rules, n_boot=50)
    motors = json.loads((tmp_path / "results" / "motors.json").read_text())
    assert len(motors) == 32
    assert {m["plant_word"] for m in motors} <= {"healthy", "check bearing", "ask a person"}
    assert all(m["motor_name"].startswith("Motor ") for m in motors)
    assert summary["headline_key"] == "shape|lab"
    assert (tmp_path / "results" / "runs.jsonl").read_text().count("\n") == 6
    for m in motors:                                   # Gap 2: each motor carries its own group's cut-offs
        assert 0 <= m["band"] <= m["medium"] and 0 < m["line"] < 1
    th = summary["runs"]["shape|16k_12b"]["thresholds"]
    assert all(set(t) == {"line", "band", "medium"} for t in th.values())


def test_load_shift_runs(fake_df, tmp_path):
    path = tmp_path / "f.parquet"
    fake_df.to_parquet(path)
    rules = prereg.load()
    rules["quality_settings"] = {"lab": [64000, None]}
    rules["detectors"] = ["shape"]
    rules["plant_view"]["setting"] = "lab"
    rules["plant_view"]["min_recordings"] = 5
    s = evaluate.run_all(path, tmp_path / "r", rules=rules, n_boot=20)
    assert set(s["load_shift"]) == {"N15_M07_F10->N15_M01_F10", "N15_M01_F10->N15_M07_F10"}
    assert all(isinstance(v["forced_ba"], float) for v in s["load_shift"].values())


def test_evidence_compares_with_the_average_training_motor():
    """The model's pushes are measured from the mean of ALL training motors, not the healthy ones (FR-006)."""
    for feature in ("band_20", "tone_outer_minus", "tone_inner_plus"):
        for pushes in (True, False):
            text = evaluate._phrase(feature, pushes)
            assert "than the average motor in training" in text
            assert "healthy" not in text
