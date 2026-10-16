"""Round 2: choose fairly among six listening-set and model combinations (prereg/round2.json).

Inside each outer fold the choice is made on the training groups only, with the same inner out-of-fold scores that set
the line and band. The outer test groups then judge the whole procedure once, so trying six combinations does not
leak into the honest score (HR-1, HR-10). Every candidate's own score is reported as well (HR-12).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from . import config, evaluate, metrics, prereg, verdicts
from .features import BAND_EDGES

ROUND2_PATH = Path(__file__).resolve().parent.parent / "prereg" / "round2.json"
KEYS = ["bearing", "condition", "rec", "setting"]


def load_rules(path: Path = ROUND2_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path: Path = ROUND2_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_model(kind: str):
    if kind == "lr":
        return evaluate.make_lr()
    if kind == "rf":
        return RandomForestClassifier(n_estimators=300, min_samples_leaf=10, max_features="sqrt",
                                      class_weight="balanced_subsample", random_state=0, n_jobs=2)
    raise ValueError(kind)


def columns(df: pd.DataFrame, prefixes: list[str], setting_cols: list[str]) -> list[str]:
    cols = sorted(c for c in df.columns if c.startswith(tuple(prefixes)) and df[c].notna().all())
    return cols + list(setting_cols)


def _fit(train: pd.DataFrame, cols: list[str], model: str):
    m = make_model(model)
    m.fit(train[cols].to_numpy(), train["label"].to_numpy())
    return m


def _raw(model, X) -> np.ndarray:
    if hasattr(model, "decision_function"):
        return model.decision_function(X)
    p = np.clip(model.predict_proba(X)[:, 1], 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _candidate(df, cand, train_bearings, test, rules, setting_cols):
    """One candidate inside one outer fold: inner out-of-fold scores, line and band, final model, test estimates."""
    cols = columns(df, cand["features"], setting_cols)
    raw, ys = [], []
    for inner_bearings in [bs for bs in rules["folds"].values() if set(bs) <= set(train_bearings)]:
        inner_train = df[df.bearing.isin([b for b in train_bearings if b not in inner_bearings])]
        inner_test = df[df.bearing.isin(inner_bearings)]
        raw.append(_raw(_fit(inner_train, cols, cand["model"]), inner_test[cols].to_numpy()))
        ys.append(inner_test["label"].to_numpy())
    raw, ys = np.concatenate(raw), np.concatenate(ys)
    calibrator = LogisticRegression().fit(raw.reshape(-1, 1), ys)
    p_oof = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
    th = verdicts.fit_thresholds(p_oof, ys, rules["handoff_share"], rules["medium_upto_share"])
    inner_ba = metrics.balanced_accuracy(ys, (p_oof > th.line).astype(int)) or 0.0
    final = _fit(df[df.bearing.isin(train_bearings)], cols, cand["model"])
    p = calibrator.predict_proba(_raw(final, test[cols].to_numpy()).reshape(-1, 1))[:, 1]
    return {"inner_ba": inner_ba, "p": p, "th": th, "model": final, "cols": cols}


def _block(test, p, th, fold):
    block = test[["bearing", "condition", "rec", "label", "origin"]].copy()
    block["fold"] = fold
    block["p"] = p
    block["line"], block["band"], block["medium"] = th.line, th.band, th.medium
    block["forced"] = (p > th.line).astype(int)
    block["verdict"] = [verdicts.verdict(x, th) for x in p]
    return block


def outer_predictions(df: pd.DataFrame, rules: dict, rules2: dict) -> dict:
    setting_cols = rules2.get("setting_columns_always_added", ["rpm", "torque"])
    selected, per_cand, chosen, models, inner = [], {c["name"]: [] for c in rules2["candidates"]}, {}, {}, {}
    for fold, test_bearings in rules["folds"].items():
        train_bearings = [b for f, bs in rules["folds"].items() if f != fold for b in bs]
        assert not set(train_bearings) & set(test_bearings)
        test = df[df.bearing.isin(test_bearings)]
        results = {c["name"]: _candidate(df, c, train_bearings, test, rules, setting_cols)
                   for c in rules2["candidates"]}
        for name, r in results.items():
            per_cand[name].append(_block(test, r["p"], r["th"], fold))
        best = max(rules2["candidates"], key=lambda c: (results[c["name"]]["inner_ba"],
                                                        -rules2["candidates"].index(c)))["name"]
        chosen[fold] = best
        inner[fold] = {n: round(r["inner_ba"], 4) for n, r in results.items()}
        r = results[best]
        selected.append(_block(test, r["p"], r["th"], fold))
        models[fold] = (r["model"], r["cols"], r["th"])
    return {"selected": pd.concat(selected, ignore_index=True), "chosen": chosen, "inner_ba": inner,
            "models": models, "candidates": {n: pd.concat(b, ignore_index=True) for n, b in per_cand.items()}}


def summarize_round(out: dict, rules: dict, n_boot=None, n_unusable: int = 0) -> dict:
    return {"selected": evaluate.summarize(out["selected"], n_unusable, None, rules, n_boot),
            "chosen_per_fold": out["chosen"], "inner_ba_per_fold": out["inner_ba"],
            "candidates": {n: evaluate.summarize(p, n_unusable, None, rules, n_boot)
                           for n, p in out["candidates"].items()}}


def plant_run(summary: dict) -> dict:
    """The run behind the plant view: round 2's selected detector after the sealed switch, else round 1's."""
    if summary.get("plant_round1") and summary.get("round2", {}).get("plant_switched"):
        return summary["round2"]["runs"][summary["plant_key"].split("|")[1]]["selected"]
    return summary["runs"][summary["plant_key"]]


def use_round2_for_plant(run: dict) -> bool:
    """Pre-registered switch: only if the whole 95% range of the honest score is above chance."""
    return run["ci"][0] is not None and run["ci"][0] > 0.5


RING = {"o": "outer-ring", "i": "inner-ring"}


def phrase(feature: str, pushes_damaged: bool) -> str:
    more = "more" if pushes_damaged else "less"
    if feature.startswith("contrast_"):
        tail = feature[len("contrast_"):]
        ring = RING[tail.replace("fe_minus_", "").replace("fe_plus_", "")[0]]
        if tail == "fe_minus_o1":
            ring = "outer- or inner-ring"
        sharp = "sharper" if pushes_damaged else "flatter"
        return f"a {sharp} peak at an {ring} bearing pitch than the average motor in training"
    if feature.startswith("click_"):
        return f"{more} clicks (a more spiky current) than the average motor in training"
    if feature.startswith("band_"):
        k = int(feature.split("_")[1])
        return (f"{more} electrical buzz between {BAND_EDGES[k]:,.0f} and {BAND_EDGES[k + 1]:,.0f} Hz "
                "than the average motor in training")
    return "the motor's speed and load setting"


def evidence(model, cols, X_motor, X_train, y_train, plant_word) -> list[str]:
    """The two signs that pushed this motor's verdict most. Logistic regression: coefficient times the motor's
    deviation from the training mean. Forest: feature importance times the deviation, signed by whether the deviation
    points toward the damaged training motors' side."""
    mean, std = X_train.mean(axis=0), X_train.std(axis=0) + 1e-12
    z = np.median((X_motor - mean) / std, axis=0)
    if hasattr(model, "named_steps"):
        push = z * model.named_steps["lr"].coef_[0]
    else:
        y_train = np.asarray(y_train)
        damaged_side = np.sign(X_train[y_train == 1].mean(axis=0) - X_train[y_train == 0].mean(axis=0))
        push = np.abs(z) * model.feature_importances_ * np.sign(z * damaged_side)
    if plant_word == "check bearing":
        order = np.argsort(-push)
    elif plant_word == "healthy":
        order = np.argsort(push)
    else:
        order = np.argsort(-np.abs(push))
    picked = [i for i in order if cols[i] not in evaluate.SETTING_COLS][:2]
    return [phrase(cols[i], bool(z[i] > 0)) for i in picked]


def motor_table(df, out, rules, setting_label) -> list[dict]:
    pv = rules["plant_view"]
    fold_of = {b: f for f, bs in rules["folds"].items() for b in bs}
    pred = out["selected"]
    rows = []
    for i, b in enumerate(evaluate.motor_order(), 1):
        rec = pred[(pred.bearing == b) & (pred.condition == pv["condition"])]
        model, cols, th = out["models"][fold_of[b]]
        word, p_med = verdicts.motor_verdict(rec.p.tolist(), th, pv["min_recordings"])
        plant_word = verdicts.PLANT_WORD[word]
        how_sure = "low" if p_med is None else verdicts.sureness(p_med, th)
        train = df[~df.bearing.isin(rules["folds"][fold_of[b]])]
        X = df[(df.bearing == b) & (df.condition == pv["condition"])][cols].to_numpy()
        rows.append({
            "motor_name": f"Motor {i:02d}", "bearing": b, "origin": config.damage_origin(b),
            "label": config.label(b), "fold": fold_of[b], "verdict": word, "plant_word": plant_word,
            "how_sure": how_sure, "line": evaluate._r(th.line), "band": evaluate._r(th.band),
            "medium": evaluate._r(th.medium), "p_median":evaluate._r(p_med), "n_recordings": int(len(rec)),
            "evidence": (evidence(model, cols, X, train[cols].to_numpy(), train["label"].to_numpy(), plant_word)
                         if len(X) else []),
            "urgency": verdicts.urgency(plant_word, how_sure, rules),
            "detector": f"round 2: {out['chosen'][fold_of[b]]}", "setting": setting_label,
        })
    return rows


def merged_table(features_path, features2_path) -> pd.DataFrame:
    t1 = pd.read_parquet(features_path)
    t2 = pd.read_parquet(features2_path)
    t2 = t2[[c for c in t2.columns if c in KEYS or c.startswith(("contrast_", "click_"))] + ["usable"]]
    t = t1.merge(t2.rename(columns={"usable": "usable2"}), on=KEYS, how="left")
    t["usable"] = t["usable"].astype(bool) & t["usable2"].fillna(False).astype(bool)
    return t.drop(columns=["usable2"])


def run_round2(features_path, features2_path, results_dir, rules=None, rules2=None, n_boot=None) -> dict:
    rules = rules or prereg.load()
    rules2 = rules2 or load_rules()
    if rules2["round1_fingerprint"] != prereg.fingerprint():
        raise SystemExit("round 2 rules do not point at the frozen round-1 rules")
    results_dir = Path(results_dir)
    table = merged_table(features_path, features2_path)
    report = {"fingerprint_round2": fingerprint(), "runs": {}, "plant_switched": False}
    plant_setting = rules["plant_view"]["setting"]
    new_motors = None
    for setting in rules["quality_settings"]:
        d = table[table.setting == setting]
        n_unusable = int((~d.usable).sum())
        d = d[d.usable].dropna(axis=1, how="all")
        out = outer_predictions(d, rules, rules2)
        report["runs"][setting] = summarize_round(out, rules, n_boot, n_unusable)
        if setting == plant_setting and use_round2_for_plant(report["runs"][setting]["selected"]):
            report["plant_switched"] = True
            new_motors = motor_table(d, out, rules, setting)
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    summary["round2"] = report
    if new_motors is not None:
        summary["plant_round1"] = summary.get("plant")
        run = report["runs"][plant_setting]["selected"]
        summary["plant"] = evaluate._plant_rates(new_motors, run, rules)
        (results_dir / "motors.json").write_text(json.dumps(new_motors, indent=1), encoding="utf-8")
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with (results_dir / "runs.jsonl").open("a", encoding="utf-8") as log:
        for setting, r in report["runs"].items():
            log.write(json.dumps({"key": f"round2|{setting}", "fingerprint_round2": report["fingerprint_round2"],
                                  "forced_ba": r["selected"]["forced_ba"], "chosen": r["chosen_per_fold"]}) + "\n")
    return report


if __name__ == "__main__":
    run_round2(Path("data/features.parquet"), Path("data/features2.parquet"), Path("results"))
