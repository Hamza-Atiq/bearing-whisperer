"""Round 3: compare every recording with the fleet at the same condition, so a new load can cancel out (prereg/round3.json).

One detector is fixed in advance (no choosing). The fleet normal is learned from training bearings only and never
uses labels, so at a new load it may use the training bearings' unlabelled recordings at that load (HR-20). Rounds 1
and 2 stay reported. Every variant's own score is shown (HR-12).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from . import config, evaluate, metrics, prereg, round2, verdicts
from .features import BAND_EDGES

ROUND3_PATH = Path(__file__).resolve().parent.parent / "prereg" / "round3.json"
SETTING_COLS = ["rpm", "torque"]
LOW_BANDS = [f"band_{k:02d}" for k in range(len(BAND_EDGES) - 1) if BAND_EDGES[k + 1] <= 1000.0]


def load_rules(path: Path = ROUND3_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path: Path = ROUND3_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def base_columns(df: pd.DataFrame, features: list[str]) -> list[str]:
    cols = []
    for f in features:
        if f == "band_below_1k":
            cols += [c for c in LOW_BANDS if c in df.columns and df[c].notna().all()]
        else:
            cols += sorted(c for c in df.columns if c.startswith(f) and df[c].notna().all())
    return cols


def own_normal(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Each recording's band levels minus its own mean band level: keeps the shape, drops the overall level."""
    out = df.copy()
    bands = [c for c in cols if c.startswith("band_")]
    out[bands] = out[bands].sub(out[bands].mean(axis=1), axis=0)
    return out


def fleet_normal(df: pd.DataFrame, cols: list[str], reference: list[str]) -> pd.DataFrame:
    """Per condition: (x - fleet median) / (fleet spread), fleet = the reference bearings, labels never read."""
    out = df.copy()
    ref = df[df.bearing.isin(reference)]
    missing = set(df.condition) - set(ref.condition)
    if missing:
        raise ValueError(f"no reference recordings at {sorted(missing)}")
    for cond, g in ref.groupby("condition"):
        med = g[cols].median()
        iqr = g[cols].quantile(0.75) - g[cols].quantile(0.25)
        m = out.condition == cond
        out.loc[m, cols] = (out.loc[m, cols] - med) / (iqr + 1e-6)
    return out


def prepared(df, cand, reference):
    cols = base_columns(df, cand["features"])
    if cand["normal"] == "fleet":
        df = fleet_normal(df, cols, reference)
    elif cand["normal"] == "own":
        df = own_normal(df, cols)
    return df, cols + SETTING_COLS


def _rows(df, bearings, conditions):
    m = df.bearing.isin(bearings)
    if conditions is not None:
        m &= df.condition.isin(conditions)
    return df[m]


def score_fold(df, cand, train_bearings, test_bearings, rules, train_conditions=None, test_conditions=None):
    """Inner out-of-fold scores at the training conditions set calibration, line and band; then one test pass."""
    raw, ys = [], []
    for inner in [bs for bs in rules["folds"].values() if set(bs) <= set(train_bearings)]:
        inner_train = [b for b in train_bearings if b not in inner]
        d, cols = prepared(df, cand, inner_train)
        model = round2._fit(_rows(d, inner_train, train_conditions), cols, "rf")
        held = _rows(d, inner, train_conditions)
        raw.append(round2._raw(model, held[cols].to_numpy()))
        ys.append(held["label"].to_numpy())
    raw, ys = np.concatenate(raw), np.concatenate(ys)
    calibrator = LogisticRegression().fit(raw.reshape(-1, 1), ys)
    th = verdicts.fit_thresholds(calibrator.predict_proba(raw.reshape(-1, 1))[:, 1], ys,
                                 rules["handoff_share"], rules["medium_upto_share"])
    d, cols = prepared(df, cand, train_bearings)
    final = round2._fit(_rows(d, train_bearings, train_conditions), cols, "rf")
    test = _rows(d, test_bearings, test_conditions)
    p = calibrator.predict_proba(round2._raw(final, test[cols].to_numpy()).reshape(-1, 1))[:, 1]
    return {"test": test, "p": p, "th": th, "model": final, "cols": cols, "normalized": d}


def outer_run(df, cand, rules, train_conditions=None, test_conditions=None):
    blocks, models = [], {}
    for fold, test_bearings in rules["folds"].items():
        train_bearings = [b for f, bs in rules["folds"].items() if f != fold for b in bs]
        assert not set(train_bearings) & set(test_bearings)
        r = score_fold(df, cand, train_bearings, test_bearings, rules, train_conditions, test_conditions)
        blocks.append(round2._block(r["test"], r["p"], r["th"], fold))
        models[fold] = r
    return pd.concat(blocks, ignore_index=True), models


def seen_bearings_ba(df, cand, rules) -> float:
    """The inflated number (HR-2): recordings split at random, so the same bearings are in training and test."""
    d, cols = prepared(df, cand, sorted(df.bearing.unique()))
    X, y = d[cols].to_numpy(), d["label"].to_numpy()
    yhat = np.zeros_like(y)
    split = StratifiedKFold(rules["seen_bearings"]["folds"], shuffle=True, random_state=rules["seen_bearings"]["seed"])
    for tr, te in split.split(X, y):
        yhat[te] = round2.make_model("rf").fit(X[tr], y[tr]).predict(X[te])
    return metrics.balanced_accuracy(y, yhat)


def by_level(pred: pd.DataFrame, levels: dict) -> dict:
    """FR-014: share of recordings flagged per damage level, with how many bearings stand behind it."""
    d = pred[pred.label == 1].assign(level=lambda x: x.bearing.map(levels))
    return {str(int(lv)): {"share_flagged": evaluate._r(g.forced.mean()), "n_bearings": int(g.bearing.nunique())}
            for lv, g in d.groupby("level")}


def ring_label(bearing: str):
    return 1 if bearing.startswith("KA") else 0 if bearing.startswith("KI") else None


def ring_run(df, rules, rules3):
    """FR-003: outer (1) vs inner (0) on damaged bearings; both-ring bearings (KB) never train or score."""
    cand = {"features": ["band_", "contrast_", "click_"], "normal": "fleet"}
    blocks, per_fold = [], {}
    for fold, test_bearings in rules["folds"].items():
        train_b = [b for f, bs in rules["folds"].items() if f != fold for b in bs]
        d, cols = prepared(df, cand, train_b)
        train = d[d.bearing.isin([b for b in train_b if ring_label(b) is not None])]
        model = round2.make_model("rf").fit(train[cols].to_numpy(), train.bearing.map(ring_label).to_numpy())
        test_all = d[d.bearing.isin(test_bearings) & (d.label == 1)]
        p_outer = model.predict_proba(test_all[cols].to_numpy())[:, list(model.classes_).index(1)]
        block = test_all[["bearing", "condition", "rec"]].copy()
        block["p_outer"] = p_outer
        block["fold"] = fold
        blocks.append(block)
    pred = pd.concat(blocks, ignore_index=True)
    scored = pred[pred.bearing.map(ring_label).notna()].copy()
    scored["label"] = scored.bearing.map(ring_label).astype(int)
    scored["forced"] = (scored.p_outer > 0.5).astype(int)
    lo, hi = metrics.bootstrap_ba(scored, n=rules["bootstrap"]["resamples"], seed=rules["bootstrap"]["seed"])
    return pred, {"ba": evaluate._r(metrics.balanced_accuracy(scored.label, scored.forced)),
                  "ci": [evaluate._r(lo), evaluate._r(hi)], "n_bearings": int(scored.bearing.nunique()),
                  "n_recordings": int(len(scored))}


def ring_word(p_outer_median, show: bool) -> str:
    if not show or p_outer_median is None:
        return "cannot tell"
    if p_outer_median >= 0.65:
        return "outer ring likely"
    if p_outer_median <= 0.35:
        return "inner ring likely"
    return "cannot tell"


def authors_split(df, rules3, feature_set: str) -> dict:
    """FR-020 in the authors' own terms: 3 classes, plain accuracy, their bearings (Lessmeier 2016 Table 8)."""
    a = rules3["authors_split_fr020"]
    cls = {b: k for k, bs in a["train"].items() for b in bs} | {b: k for k, bs in a["test"].items() for b in bs}
    features = ["band_"] if feature_set == "shape_fleet" else ["band_", "contrast_", "click_"]
    train_b = [b for bs in a["train"].values() for b in bs]
    test_b = [b for bs in a["test"].values() for b in bs]
    d, cols = prepared(df[df.bearing.isin(train_b + test_b)], {"features": features, "normal": "fleet"}, train_b)
    train, test = d[d.bearing.isin(train_b)], d[d.bearing.isin(test_b)]
    model = round2.make_model("rf").fit(train[cols].to_numpy(), train.bearing.map(cls).to_numpy())
    y, yhat = test.bearing.map(cls).to_numpy(), model.predict(test[cols].to_numpy())
    recall = {k: float(np.mean(yhat[y == k] == k)) for k in sorted(set(y))}
    return {"accuracy": evaluate._r(np.mean(yhat == y)), "balanced_3class": evaluate._r(np.mean(list(recall.values()))),
            "recall_per_class": {k: evaluate._r(v) for k, v in recall.items()}, "n_test_recordings": int(len(y))}


def motor_table(df, models, pred, rules, rules3, setting, ring_pred=None, ring_show=False) -> list[dict]:
    pv = rules["plant_view"]
    fold_of = {b: f for f, bs in rules["folds"].items() for b in bs}
    rows = []
    for i, b in enumerate(evaluate.motor_order(), 1):
        r = models[fold_of[b]]
        th, cols, d = r["th"], r["cols"], r["normalized"]
        rec = pred[(pred.bearing == b) & (pred.condition == pv["condition"])]
        word, p_med = verdicts.motor_verdict(rec.p.tolist(), th, pv["min_recordings"])
        plant_word = verdicts.PLANT_WORD[word]
        how_sure = "low" if p_med is None else verdicts.sureness(p_med, th)
        train = d[~d.bearing.isin(rules["folds"][fold_of[b]])]
        X = d[(d.bearing == b) & (d.condition == pv["condition"])][cols].to_numpy()
        ring = None
        if ring_pred is not None and plant_word == "check bearing":
            pr = ring_pred[(ring_pred.bearing == b) & (ring_pred.condition == pv["condition"])]
            ring = ring_word(float(pr.p_outer.median()) if len(pr) else None, ring_show)
        rows.append({
            "motor_name": f"Motor {i:02d}", "bearing": b, "origin": config.damage_origin(b),
            "label": config.label(b), "fold": fold_of[b], "verdict": word, "plant_word": plant_word,
            "how_sure": how_sure, "line": evaluate._r(th.line), "band": evaluate._r(th.band),
            "medium": evaluate._r(th.medium), "p_median": evaluate._r(p_med), "n_recordings": int(len(rec)),
            "evidence": (round2.evidence(r["model"], cols, X, train[cols].to_numpy(), train["label"].to_numpy(),
                                         plant_word) if len(X) else []),
            "urgency": verdicts.urgency(plant_word, how_sure, rules),
            "ring": ring, "detector": f"round 3: {rules3['detector']}", "setting": setting,
        })
    return rows


def use_round3_for_plant(same_load: dict, new_load: dict) -> bool:
    return all(r["ci"][0] is not None and r["ci"][0] > 0.5 for r in [same_load, *new_load.values()])


def run_round3(features_path, features2_path, results_dir, rules=None, rules3=None, n_boot=None) -> dict:
    rules = rules or prereg.load()
    rules3 = rules3 or load_rules()
    if rules3["round1_fingerprint"] != prereg.fingerprint() or rules3["round2_fingerprint"] != round2.fingerprint():
        raise SystemExit("round 3 rules do not point at the frozen round-1 and round-2 rules")
    results_dir = Path(results_dir)
    table = round2.merged_table(features_path, features2_path)
    cands = {c["name"]: c for c in rules3["candidates_reported_not_chosen"]}
    det = rules3["detector"]
    plant_setting = rules["plant_view"]["setting"]
    report = {"fingerprint_round3": fingerprint(), "detector": det, "same_load": {}, "new_load": {},
              "candidates": {}, "seen_ba": {}, "by_level": {}, "ring": {}, "authors_split": {},
              "plant_switched": False}
    keep = {}
    for setting in rules3["settings_same_load"]:
        d = table[table.setting == setting]
        n_unusable = int((~d.usable).sum())
        d = d[d.usable].dropna(axis=1, how="all")
        report["candidates"][setting] = {}
        for name, cand in cands.items():
            pred, models = outer_run(d, cand, rules)
            run = evaluate.summarize(pred, n_unusable, None, rules, n_boot)
            report["candidates"][setting][name] = {"same_load": run["forced_ba"], "ci": run["ci"]}
            if name == det:
                report["same_load"][setting] = run
                report["by_level"][setting] = by_level(pred, rules3["damage_levels"])
                if setting in ("lab", plant_setting):
                    report["seen_ba"][setting] = evaluate._r(seen_bearings_ba(d, cand, rules))
                if setting == plant_setting:
                    keep = {"d": d, "models": models, "pred": pred}
            if setting in rules3["settings_new_load"]:
                shifts = {}
                for train_c, test_c in rules["load_shift"]:
                    sp, _ = outer_run(d, cand, rules, [train_c], [test_c])
                    shifts[f"{train_c}->{test_c}"] = evaluate.summarize(sp, 0, None, rules, n_boot)
                report["candidates"][setting][name]["new_load"] = {k: v["forced_ba"] for k, v in shifts.items()}
                if name == det:
                    report["new_load"][setting] = shifts
            print(setting, name, report["candidates"][setting][name], flush=True)
        if setting in rules3["authors_split_fr020"]["settings"]:
            report["authors_split"][setting] = {fs: authors_split(d, rules3, fs)
                                                for fs in rules3["authors_split_fr020"]["feature_sets"]}
        if setting in ("lab", plant_setting):
            ring_pred, ring = ring_run(d, rules, rules3)
            report["ring"][setting] = ring
            if setting == plant_setting:
                keep["ring_pred"] = ring_pred
    ring_show = report["ring"][plant_setting]["ci"][0] is not None and report["ring"][plant_setting]["ci"][0] > 0.5
    report["ring_shown"] = ring_show
    motors = motor_table(keep["d"], keep["models"], keep["pred"], rules, rules3, plant_setting,
                         keep.get("ring_pred"), ring_show)
    run = report["same_load"][plant_setting]
    report["plant"] = evaluate._plant_rates(motors, run, rules)
    report["plant_switched"] = use_round3_for_plant(run, report["new_load"][plant_setting])
    (results_dir / "round3.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (results_dir / "motors_round3.json").write_text(json.dumps(motors, indent=1), encoding="utf-8")
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    summary["round3"] = {"fingerprint_round3": report["fingerprint_round3"], "plant_switched": report["plant_switched"]}
    if report["plant_switched"]:
        summary["plant_round2"] = summary["plant"]
        summary["plant"] = report["plant"]
        (results_dir / "motors.json").write_text(json.dumps(motors, indent=1), encoding="utf-8")
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with (results_dir / "runs.jsonl").open("a", encoding="utf-8") as log:
        for setting, r in report["same_load"].items():
            log.write(json.dumps({"key": f"round3|{setting}", "fingerprint_round3": report["fingerprint_round3"],
                                  "forced_ba": r["forced_ba"],
                                  "new_load": {k: v["forced_ba"] for k, v in report["new_load"].get(setting, {}).items()}})
                      + "\n")
    return report


if __name__ == "__main__":
    run_round3(Path("data/features.parquet"), Path("data/features2.parquet"), Path("results"))
