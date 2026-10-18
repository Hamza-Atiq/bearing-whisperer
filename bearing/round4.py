"""Round 4: round 3's detector with the force removed from the fleet normal (FR-002), plus the published protocol:
leave each operating condition out in turn (prereg/round4.json).

Round 3 grouped the fleet by the full condition name, which includes the radial force a drive cannot know. Here the
fleet is grouped by the drive setting only (speed and torque). Rounds 1 to 3 stay reported.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from . import config, evaluate, metrics, prereg, round2, round3, verdicts

ROUND4_PATH = Path(__file__).resolve().parent.parent / "prereg" / "round4.json"
SETTING_COLS = round3.SETTING_COLS
REAL_ONE_RING = ["KA04", "KA15", "KA16", "KA22", "KA30", "KI04", "KI14", "KI16", "KI17", "KI18", "KI21"]
BOTH_RINGS = ["KB23", "KB24", "KB27"]


def load_rules(path: Path = ROUND4_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path: Path = ROUND4_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def drive_key(df: pd.DataFrame) -> pd.Series:
    """What a drive knows about where it runs: speed and torque. Never the force (FR-002)."""
    return df["rpm"].astype(float).astype(str) + "_" + df["torque"].astype(float).astype(str)


def fleet_normal(df: pd.DataFrame, cols: list[str], reference: list[str]) -> pd.DataFrame:
    """Per drive setting: (x - fleet median) / (fleet spread), fleet = the reference bearings, labels never read."""
    out = df.copy()
    key = drive_key(df)
    ref = df.bearing.isin(reference)
    missing = set(key) - set(key[ref])
    if missing:
        raise ValueError(f"no reference recordings at {sorted(missing)}")
    for k in key.unique():
        g = df.loc[ref & (key == k), cols]
        med = g.median()
        iqr = g.quantile(0.75) - g.quantile(0.25)
        m = key == k
        out.loc[m, cols] = (out.loc[m, cols] - med) / (iqr + 1e-6)
    return out


def prepared(df, cand, reference):
    cols = round3.base_columns(df, cand["features"])
    if cand["normal"] == "fleet":
        df = fleet_normal(df, cols, reference)
    elif cand["normal"] != "none":
        raise ValueError(f"unknown normal {cand['normal']}")
    return df, cols + SETTING_COLS


def score_fold(df, cand, train_bearings, test_bearings, rules, train_conditions=None, test_conditions=None):
    """As round 3: inner out-of-fold scores at the training conditions set calibration, line and band; one test pass."""
    raw, ys = [], []
    for inner in [bs for bs in rules["folds"].values() if set(bs) <= set(train_bearings)]:
        inner_train = [b for b in train_bearings if b not in inner]
        d, cols = prepared(df, cand, inner_train)
        model = round2._fit(round3._rows(d, inner_train, train_conditions), cols, "rf")
        held = round3._rows(d, inner, train_conditions)
        raw.append(round2._raw(model, held[cols].to_numpy()))
        ys.append(held["label"].to_numpy())
    raw, ys = np.concatenate(raw), np.concatenate(ys)
    calibrator = LogisticRegression().fit(raw.reshape(-1, 1), ys)
    th = verdicts.fit_thresholds(calibrator.predict_proba(raw.reshape(-1, 1))[:, 1], ys,
                                 rules["handoff_share"], rules["medium_upto_share"])
    d, cols = prepared(df, cand, train_bearings)
    final = round2._fit(round3._rows(d, train_bearings, train_conditions), cols, "rf")
    test = round3._rows(d, test_bearings, test_conditions)
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


def subsets(pred: pd.DataFrame, rules, n_boot=None) -> dict:
    """Healthy against one kind of damage at a time, from the same predictions (closest to the published targets)."""
    n_boot = n_boot or rules["bootstrap"]["resamples"]
    healthy = pred.label == 0
    groups = {"real wear, one ring": pred.bearing.isin(REAL_ONE_RING),
              "real wear, all": pred.origin == "real",
              "lab-made damage": pred.origin == "artificial",
              "all damage": pred.label == 1}
    out = {}
    for name, m in groups.items():
        part = pred[healthy | m]
        lo, hi = metrics.bootstrap_ba(part, n=n_boot, seed=rules["bootstrap"]["seed"])
        out[name] = {"ba": evaluate._r(metrics.balanced_accuracy(part.label, part.forced)),
                     "ci": [evaluate._r(lo), evaluate._r(hi)], "n_damaged_bearings": int(part[part.label == 1].bearing.nunique())}
    return out


def loco(df, cand, rules, n_boot=None) -> dict:
    """Leave each condition out: train labels at the other three, score unseen bearings at the held-out one."""
    out, preds = {}, []
    for held in config.CONDITIONS:
        train_c = [c for c in config.CONDITIONS if c != held]
        pred, _ = outer_run(df, cand, rules, train_c, [held])
        out[held] = evaluate.summarize(pred, 0, None, rules, n_boot)
        preds.append(pred)
    bas = [v["forced_ba"] for v in out.values() if v["forced_ba"] is not None]
    allp = pd.concat(preds, ignore_index=True)
    return {"per_condition": out, "mean_ba": evaluate._r(float(np.mean(bas))) if bas else None,
            "pooled": evaluate.summarize(allp, 0, None, rules, n_boot), "subsets": subsets(allp, rules, n_boot)}


def seen_bearings_ba(df, cand, rules) -> float:
    from sklearn.model_selection import StratifiedKFold
    d, cols = prepared(df, cand, sorted(df.bearing.unique()))
    X, y = d[cols].to_numpy(), d["label"].to_numpy()
    yhat = np.zeros_like(y)
    split = StratifiedKFold(rules["seen_bearings"]["folds"], shuffle=True, random_state=rules["seen_bearings"]["seed"])
    for tr, te in split.split(X, y):
        yhat[te] = round2.make_model("rf").fit(X[tr], y[tr]).predict(X[te])
    return metrics.balanced_accuracy(y, yhat)


def ring_run(df, rules):
    """FR-003 as round 3, with this fleet normal."""
    cand = {"features": ["band_", "contrast_", "click_"], "normal": "fleet"}
    blocks = []
    for fold, test_bearings in rules["folds"].items():
        train_b = [b for f, bs in rules["folds"].items() if f != fold for b in bs]
        d, cols = prepared(df, cand, train_b)
        train = d[d.bearing.isin([b for b in train_b if round3.ring_label(b) is not None])]
        model = round2.make_model("rf").fit(train[cols].to_numpy(), train.bearing.map(round3.ring_label).to_numpy())
        test_all = d[d.bearing.isin(test_bearings) & (d.label == 1)]
        p_outer = model.predict_proba(test_all[cols].to_numpy())[:, list(model.classes_).index(1)]
        block = test_all[["bearing", "condition", "rec"]].copy()
        block["p_outer"] = p_outer
        block["fold"] = fold
        blocks.append(block)
    pred = pd.concat(blocks, ignore_index=True)
    scored = pred[pred.bearing.map(round3.ring_label).notna()].copy()
    scored["label"] = scored.bearing.map(round3.ring_label).astype(int)
    scored["forced"] = (scored.p_outer > 0.5).astype(int)
    lo, hi = metrics.bootstrap_ba(scored, n=rules["bootstrap"]["resamples"], seed=rules["bootstrap"]["seed"])
    return pred, {"ba": evaluate._r(metrics.balanced_accuracy(scored.label, scored.forced)),
                  "ci": [evaluate._r(lo), evaluate._r(hi)], "n_bearings": int(scored.bearing.nunique()),
                  "n_recordings": int(len(scored))}


def authors_split(df, rules3, feature_set: str) -> dict:
    """FR-020 as round 3 (their bearings, 3 classes, plain accuracy), with this fleet normal."""
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


def run_round4(features_path, features2_path, results_dir, rules=None, rules3=None, rules4=None, n_boot=None) -> dict:
    rules = rules or prereg.load()
    rules3 = rules3 or round3.load_rules()
    rules4 = rules4 or load_rules()
    if (rules4["round1_fingerprint"] != prereg.fingerprint() or rules4["round2_fingerprint"] != round2.fingerprint()
            or rules4["round3_fingerprint"] != round3.fingerprint()):
        raise SystemExit("round 4 rules do not point at the frozen rounds 1 to 3")
    results_dir = Path(results_dir)
    table = round2.merged_table(features_path, features2_path)
    cands = {c["name"]: c for c in rules4["candidates_reported_not_chosen"]}
    det = rules4["detector"]
    plant_setting = rules["plant_view"]["setting"]
    loco_settings = rules4["leave_one_condition_out"]["settings"]
    report = {"fingerprint_round4": fingerprint(), "detector": det, "same_load": {}, "new_load": {}, "loco": {},
              "candidates": {}, "seen_ba": {}, "by_level": {}, "ring": {}, "authors_split": {}}
    keep = {}
    for setting in rules3["settings_same_load"]:
        d = table[table.setting == setting]
        n_unusable = int((~d.usable).sum())
        d = d[d.usable].dropna(axis=1, how="all")
        report["candidates"][setting] = {}
        names = list(cands) if setting in loco_settings else [det]
        for name in names:
            cand = cands[name]
            pred, models = outer_run(d, cand, rules)
            run = evaluate.summarize(pred, n_unusable, None, rules, n_boot)
            entry = {"same_load": run["forced_ba"], "ci": run["ci"]}
            if name == det:
                report["same_load"][setting] = run
                report["by_level"][setting] = round3.by_level(pred, rules3["damage_levels"])
                if setting in loco_settings:
                    report["seen_ba"][setting] = evaluate._r(seen_bearings_ba(d, cand, rules))
                if setting == plant_setting:
                    keep = {"d": d, "models": models, "pred": pred}
            if setting in loco_settings:
                shifts = {}
                for train_c, test_c in rules["load_shift"]:
                    sp, _ = outer_run(d, cand, rules, [train_c], [test_c])
                    shifts[f"{train_c}->{test_c}"] = evaluate.summarize(sp, 0, None, rules, n_boot)
                entry["new_load"] = {k: v["forced_ba"] for k, v in shifts.items()}
                lo = loco(d, cand, rules, n_boot)
                entry["loco_mean"] = lo["mean_ba"]
                entry["loco"] = {k: v["forced_ba"] for k, v in lo["per_condition"].items()}
                entry["loco_subsets"] = lo["subsets"]
                if name == det:
                    report["new_load"][setting] = shifts
                    report["loco"][setting] = lo
            report["candidates"][setting][name] = entry
            print(setting, name, json.dumps(entry), flush=True)
        if setting in loco_settings:
            report["authors_split"][setting] = {fs: authors_split(d, rules3, fs)
                                                for fs in rules3["authors_split_fr020"]["feature_sets"]}
            ring_pred, ring = ring_run(d, rules)
            report["ring"][setting] = ring
            if setting == plant_setting:
                keep["ring_pred"] = ring_pred
    ring_show = report["ring"][plant_setting]["ci"][0] is not None and report["ring"][plant_setting]["ci"][0] > 0.5
    report["ring_shown"] = ring_show
    motors = round3.motor_table(keep["d"], keep["models"], keep["pred"], rules, rules3, plant_setting,
                                keep.get("ring_pred"), ring_show)
    for m in motors:
        m["detector"] = f"round 4: {det} (force removed)"
    run = report["same_load"][plant_setting]
    report["plant"] = evaluate._plant_rates(motors, run, rules)
    report["plant_switched"] = True                     # sealed: round 3 breaks FR-002, so the plant view moves
    (results_dir / "round4.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (results_dir / "motors_round4.json").write_text(json.dumps(motors, indent=1), encoding="utf-8")
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    summary["round4"] = {"fingerprint_round4": report["fingerprint_round4"], "plant_switched": True}
    summary["plant_round3"] = summary["plant"]
    summary["plant"] = report["plant"]
    (results_dir / "motors.json").write_text(json.dumps(motors, indent=1), encoding="utf-8")
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with (results_dir / "runs.jsonl").open("a", encoding="utf-8") as log:
        for setting, r in report["same_load"].items():
            log.write(json.dumps({"key": f"round4|{setting}", "fingerprint_round4": report["fingerprint_round4"],
                                  "forced_ba": r["forced_ba"],
                                  "loco_mean": report["loco"].get(setting, {}).get("mean_ba"),
                                  "new_load": {k: v["forced_ba"] for k, v in report["new_load"].get(setting, {}).items()}})
                      + "\n")
    return report


if __name__ == "__main__":
    run_round4(Path("data/features.parquet"), Path("data/features2.parquet"), Path("results"))
