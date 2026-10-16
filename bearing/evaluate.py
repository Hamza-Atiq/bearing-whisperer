"""Honest evaluation: every verdict comes from a model that never saw that bearing (HR-1, HR-10, HR-11)."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config, metrics, prereg, verdicts
from .features import BAND_EDGES

SETTING_COLS = ["rpm", "torque"]
ROUND = 4


def make_lr() -> Pipeline:
    return Pipeline([("scale", StandardScaler()),
                     ("lr", LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000))])


def feature_columns(df: pd.DataFrame, detector: str) -> list[str]:
    def present(prefix):
        return sorted(c for c in df.columns if c.startswith(prefix) and df[c].notna().all())
    if detector == "shape":
        return present("band_") + SETTING_COLS
    if detector == "tones":
        return present("tone_") + SETTING_COLS
    if detector == "loudness":
        return ["residual_db"]
    if detector == "setting_only":
        return SETTING_COLS
    raise ValueError(f"unknown detector {detector}")


def _fit(train: pd.DataFrame, cols: list[str]) -> Pipeline:
    model = make_lr()
    model.fit(train[cols].to_numpy(), train["label"].to_numpy())
    return model


def _rows(df, bearings, conditions):
    m = df["bearing"].isin(bearings)
    if conditions is not None:
        m &= df["condition"].isin(conditions)
    return df[m]


def outer_fold_predictions(df, detector, folds, rules, train_conditions=None, test_conditions=None):
    blocks, models = [], {}
    for name, test_bearings in folds.items():
        train_bearings = [b for f, bs in folds.items() if f != name for b in bs]
        assert not set(train_bearings) & set(test_bearings)
        test = _rows(df, test_bearings, test_conditions)
        if detector == "always_damaged":
            th = verdicts.Thresholds(line=0.5, band=0.0, medium=0.0)
            p = np.ones(len(test))
        else:
            cols = feature_columns(df, detector)
            raw_oof, y_oof = [], []
            for inner, inner_bearings in folds.items():
                if inner == name:
                    continue
                inner_train = _rows(df, [b for b in train_bearings if b not in inner_bearings], train_conditions)
                inner_test = _rows(df, inner_bearings, train_conditions)
                raw_oof.append(_fit(inner_train, cols).decision_function(inner_test[cols].to_numpy()))
                y_oof.append(inner_test["label"].to_numpy())
            raw_oof, y_oof = np.concatenate(raw_oof), np.concatenate(y_oof)
            calibrator = LogisticRegression().fit(raw_oof.reshape(-1, 1), y_oof)
            p_oof = calibrator.predict_proba(raw_oof.reshape(-1, 1))[:, 1]
            th = verdicts.fit_thresholds(p_oof, y_oof, rules["handoff_share"], rules["medium_upto_share"])
            final = _fit(_rows(df, train_bearings, train_conditions), cols)
            p = calibrator.predict_proba(final.decision_function(test[cols].to_numpy()).reshape(-1, 1))[:, 1]
            models[name] = (final, cols, th)
        block = test[["bearing", "condition", "rec", "label", "origin"]].copy()
        block["fold"] = name
        block["p"] = p
        block["line"], block["band"], block["medium"] = th.line, th.band, th.medium
        block["forced"] = (p > th.line).astype(int)
        block["verdict"] = [verdicts.verdict(x, th) for x in p]
        blocks.append(block)
    return pd.concat(blocks, ignore_index=True), models


def seen_bearings_ba(df, detector, rules) -> float:
    """The inflated number (HR-2): recordings mixed at random, so the same bearings are in training and test."""
    cols = feature_columns(df, detector)
    X, y = df[cols].to_numpy(), df["label"].to_numpy()
    yhat = np.zeros_like(y)
    split = StratifiedKFold(rules["seen_bearings"]["folds"], shuffle=True, random_state=rules["seen_bearings"]["seed"])
    for tr, te in split.split(X, y):
        yhat[te] = make_lr().fit(X[tr], y[tr]).predict(X[te])
    return metrics.balanced_accuracy(y, yhat)


def _r(x):
    return None if x is None else round(float(x), ROUND)


def summarize(pred, n_unusable, seen_ba, rules, n_boot=None) -> dict:
    n_boot = n_boot or rules["bootstrap"]["resamples"]
    rates = metrics.rates(pred.label, pred.forced)
    decided = pred[pred.verdict != verdicts.PERSON]
    decided_ba = metrics.balanced_accuracy(decided.label, (decided.verdict == verdicts.DAMAGED).astype(int))
    lo, hi = metrics.bootstrap_ba(pred, n=n_boot, seed=rules["bootstrap"]["seed"])
    per_bearing = (pred.groupby(["bearing", "origin"])
                   .agg(share_flagged=("forced", "mean"), n=("forced", "size")).reset_index())
    return {
        "forced_ba": _r(metrics.balanced_accuracy(pred.label, pred.forced)),
        "ci": [_r(lo), _r(hi)],
        "false_alarm": _r(rates["false_alarm"]), "miss": _r(rates["miss"]),
        "decided_share": _r(len(decided) / len(pred)),
        "decided_ba": "undefined" if decided_ba is None else _r(decided_ba),
        "decided_nothing": len(decided) == 0,         # SC-5: reported as a failure at this setting
        "seen_ba": _r(seen_ba),
        "per_condition": {c: _r(metrics.balanced_accuracy(g.label, g.forced)) for c, g in pred.groupby("condition")},
        "by_origin": {o: _r(g.forced.mean()) for o, g in pred.groupby("origin")},
        "fold_ba": {f: _r(metrics.balanced_accuracy(g.label, g.forced)) for f, g in pred.groupby("fold")},
        "thresholds": {f: {"line": _r(g.line.iloc[0]), "band": _r(g.band.iloc[0]), "medium": _r(g.medium.iloc[0])}
                       for f, g in pred.groupby("fold")},
        "per_bearing": [{"bearing": r["bearing"], "origin": r["origin"], "share_flagged": _r(r["share_flagged"]),
                         "n": int(r["n"])} for r in per_bearing.to_dict("records")],
        "ece": _r(metrics.ece(pred.p, pred.label)),
        "n_recordings": int(len(pred)), "n_unusable": int(n_unusable),
    }


def _phrase(feature: str, pushes_damaged: bool) -> str:
    more = "more" if pushes_damaged else "less"
    if feature.startswith("band_"):
        k = int(feature.split("_")[1])
        return f"{more} electrical buzz between {BAND_EDGES[k]:,.0f} and {BAND_EDGES[k + 1]:,.0f} Hz than the average motor in training"
    if feature.startswith("tone_"):
        part = "inner-ring" if "inner" in feature else "outer-ring"
        if feature == "tone_outer_minus":
            part = "outer- or inner-ring"
        return f"a {'stronger' if pushes_damaged else 'weaker'} trace at an {part} bearing pitch than the average motor in training"
    return "the motor's speed and load setting"


def _evidence(model, cols, X, plant_word) -> list[str]:
    scale, lr = model.named_steps["scale"], model.named_steps["lr"]
    contrib = np.median((X - scale.mean_) / scale.scale_ * lr.coef_[0], axis=0)
    order = np.argsort(-contrib) if plant_word == "check bearing" else (
        np.argsort(contrib) if plant_word == "healthy" else np.argsort(-np.abs(contrib)))
    picked = [i for i in order if cols[i] not in SETTING_COLS][:2]
    return [_phrase(cols[i], contrib[i] > 0) for i in picked]


def motor_order() -> list[str]:
    """A fixed order that does not reveal which motors are healthy."""
    return sorted(config.ALL_BEARINGS, key=lambda b: hashlib.sha256(b.encode()).hexdigest())


def motor_table(df, pred, models, rules) -> list[dict]:
    pv = rules["plant_view"]
    fold_of = {b: f for f, bs in rules["folds"].items() for b in bs}
    out = []
    for i, b in enumerate(motor_order(), 1):
        rec = pred[(pred.bearing == b) & (pred.condition == pv["condition"])]
        model, cols, th = models[fold_of[b]]
        word, p_med = verdicts.motor_verdict(rec.p.tolist(), th, pv["min_recordings"])
        plant_word = verdicts.PLANT_WORD[word]
        how_sure = "low" if p_med is None else verdicts.sureness(p_med, th)
        X = df[(df.bearing == b) & (df.condition == pv["condition"])][cols].to_numpy()
        out.append({
            "motor_name": f"Motor {i:02d}", "bearing": b, "origin": config.damage_origin(b),
            "label": config.label(b), "fold": fold_of[b], "verdict": word, "plant_word": plant_word,
            "how_sure": how_sure, "line": _r(th.line), "band": _r(th.band), "medium": _r(th.medium),
            "p_median": _r(p_med), "n_recordings": int(len(rec)),
            "evidence": _evidence(model, cols, X, plant_word) if len(X) else [],
            "urgency": verdicts.urgency(plant_word, how_sure, rules),
            "detector": pv["detector"], "setting": pv["setting"],
        })
    return out


def _plant_rates(motors, run, rules) -> dict:
    h = [m for m in motors if m["label"] == 0]
    d = [m for m in motors if m["label"] == 1]
    share = lambda ms, word: _r(sum(m["plant_word"] == word for m in ms) / len(ms))
    return {"catch_rate": share(d, "check bearing"), "false_alarm_rate": share(h, "check bearing"),
            "handoff_healthy": share(h, "ask a person"), "handoff_damaged": share(d, "ask a person"),
            "n_healthy": len(h), "n_damaged": len(d), "ece": run["ece"],
            "percent_ok": run["ece"] is not None and run["ece"] <= rules["percent_display_max_ece"]}


def run_all(features_path, results_dir, rules=None, n_boot=None) -> dict:
    rules = rules or prereg.load()
    problems = prereg.check(rules)
    if problems:
        raise SystemExit("pre-registration problems: " + "; ".join(problems))
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    table = pd.read_parquet(features_path)
    hk = f"{rules['headline']['detector']}|{rules['headline']['setting']}"
    pk = f"{rules['plant_view']['detector']}|{rules['plant_view']['setting']}"
    summary = {"prereg_fingerprint": prereg.fingerprint(), "headline_key": hk, "plant_key": pk,
               "runs": {}, "plant": {}, "load_shift": {}}
    motors = []
    with (results_dir / "runs.jsonl").open("a", encoding="utf-8") as log:
        for setting in rules["quality_settings"]:
            d = table[table.setting == setting]
            n_unusable = int((~d.usable.astype(bool)).sum())
            d = d[d.usable.astype(bool)].dropna(axis=1, how="all")
            for detector in rules["detectors"]:
                pred, models = outer_fold_predictions(d, detector, rules["folds"], rules)
                seen = None if detector == "always_damaged" else seen_bearings_ba(d, detector, rules)
                key = f"{detector}|{setting}"
                run = summarize(pred, n_unusable, seen, rules, n_boot)
                run["n_clipped_samples"] = int(table[table.setting == setting].n_clipped.sum())   # FR-004
                summary["runs"][key] = run
                if detector == rules["headline"]["detector"] and setting == rules["headline"]["setting"]:
                    for train_c, test_c in rules["load_shift"]:          # FR-011, HR-13
                        shift_pred, _ = outer_fold_predictions(d, detector, rules["folds"], rules,
                                                               train_conditions=[train_c], test_conditions=[test_c])
                        summary["load_shift"][f"{train_c}->{test_c}"] = summarize(shift_pred, 0, None, rules, n_boot)
                log.write(json.dumps({"key": key, "time": datetime.now(timezone.utc).isoformat(),
                                      "fingerprint": summary["prereg_fingerprint"],
                                      "forced_ba": run["forced_ba"]}) + "\n")
                if key == pk:
                    motors = motor_table(d, pred, models, rules)
                    summary["plant"] = _plant_rates(motors, run, rules)
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (results_dir / "motors.json").write_text(json.dumps(motors, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    run_all(Path("data/features.parquet"), Path("results"))
