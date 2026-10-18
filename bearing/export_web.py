"""Build the one data file the web app reads (web/public/data/app.json) from saved results only (HR-7).

Nothing here is a new result: verdicts and scores are copied from results/; the "hiss picture" of each motor is the
median of its own feature rows (derived from the CC BY-NC data, like every published result); "where it listens" is
the average feature importance of the six fold models that made the plant view's verdicts, refit exactly as in their
round (same data, same settings, random_state 0).
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, features, prereg, round2, round3, round4

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "data" / "app.json"
API_COPY = ROOT / "web" / "api" / "_data" / "app.json"


def _j(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _run(r):
    return None if r is None else {"ba": r["forced_ba"], "ci": r["ci"], "false_alarm": r.get("false_alarm"),
                                   "miss": r.get("miss"), "decided_share": r.get("decided_share"),
                                   "decided_ba": r.get("decided_ba")}


# Published results we compare with, as their own papers state them (checked 18 Oct 2026). Never computed by us.
PUBLISHED = {
    "cekic_akan": {
        "cite": "Cekic and Akan, Energies 2026, doi 10.3390/en19163884 (abstract)",
        "protocol": "unseen bearings (bearing-level split) and each operating condition left out in turn; CNNs on time-frequency images",
        "target_a": {"ba": 0.736, "what": "real (aged) damage only; best of eight candidates (CWT + EfficientNetB0), all-split mean"},
        "target_d": {"ba": 0.503, "specificity": 0.146, "what": "lab-made plus aged damage, mixed faults included; motor current, one matched setup (FSST + ResNet-50, 24 runs)"},
        "target_d_note": "their best target-D candidates had about 0.89 sensitivity with about 0.90 false alarms",
    },
    "lessmeier": {"cite": "Lessmeier et al., PHME 2016, Tables 8 and 9", "mcs_low": 0.268, "mcs_high": 0.609,
                  "mcs_ensemble": 0.459, "guess": 0.333},
}


def plant_round(summary) -> int:
    if summary.get("round4", {}).get("plant_switched"):
        return 4
    if summary.get("round3", {}).get("plant_switched"):
        return 3
    if summary.get("round2", {}).get("plant_switched"):
        return 2
    return 1


def listening_weights(table, rules, rules3, which: int) -> list[float]:
    """Average band importance of the plant view's six fold models (round 2, 3 or 4), refit as in their round."""
    d = table[(table.setting == rules["plant_view"]["setting"]) & table.usable].dropna(axis=1, how="all")
    bands = sorted(c for c in d.columns if c.startswith("band_") and d[c].notna().all())
    total = np.zeros(len(bands))
    for fold, test_b in rules["folds"].items():
        train_b = [b for f, bs in rules["folds"].items() if f != fold for b in bs]
        if which == 4:
            r4 = round4.load_rules()
            cand = next(c for c in r4["candidates_reported_not_chosen"] if c["name"] == r4["detector"])
            dd, cols = round4.prepared(d, cand, train_b)
        elif which == 3:
            cand = next(c for c in rules3["candidates_reported_not_chosen"] if c["name"] == rules3["detector"])
            dd, cols = round3.prepared(d, cand, train_b)
        else:
            dd, cols = d, bands + ["rpm", "torque"]
        model = round2._fit(dd[dd.bearing.isin(train_b)], cols, "rf")
        imp = dict(zip(cols, model.feature_importances_))
        total += np.array([imp.get(b, 0.0) for b in bands])
    w = total / total.sum()
    return [round(float(x), 4) for x in w]


def hiss(table, rules) -> dict:
    pv = rules["plant_view"]
    d = table[(table.setting == pv["setting"]) & (table.condition == pv["condition"]) & table.usable]
    bands = sorted(c for c in d.columns if c.startswith("band_") and d[c].notna().all())
    per = d.groupby("bearing")[bands].median()
    healthy = d[d.bearing.isin(config.HEALTHY)][bands]
    rpm, _ = config.drive_setting(pv["condition"])
    fe = rpm / 60 * config.POLE_PAIRS
    tones = features.tone_lines(fe)
    return {
        "edges": [round(float(x), 1) for x in features.BAND_EDGES[: len(bands) + 1]],
        "per_bearing": {b: [round(float(v), 2) for v in per.loc[b]] for b in per.index},
        "healthy_median": [round(float(v), 2) for v in healthy.median()],
        "healthy_low": [round(float(v), 2) for v in healthy.quantile(0.1)],
        "healthy_high": [round(float(v), 2) for v in healthy.quantile(0.9)],
        "main_tone_hz": fe,
        "bearing_pitches": {"outer ring": round(tones["outer_ring"], 1), "inner ring": round(tones["inner_ring"], 1)},
        "bearing_traces": [round(tones[k], 1) for k in ("outer_minus", "outer_plus", "inner_plus")],
        "shaft_hz": fe / config.POLE_PAIRS,
        "unit": "dB below the main tone",
        "setting": pv["setting"], "condition": pv["condition"],
    }


def hearing(pr, checks, checks3) -> dict | None:
    """The 'what is it really hearing?' checks for the round behind the plant view (exploratory, run after it)."""
    if pr >= 3 and checks3:
        c, s = checks3, "_fleet+rf"
        return {"round": 3, "tones": c["tones" + s], "low": c["low_bands_1k" + s], "mid": c["mid_bands_1k_4.5k" + s],
                "high": c["high_bands_4.5k" + s], "real": c["shape_fleet+rf_real"], "null_summary": c["null_summary"],
                "runin_flagged": c["runin_flagged"], "runin_hours": c["runin_hours"]}
    if checks:
        c = checks
        return {"round": 2, "tones": c["tones+rf"], "low": c["low_bands_1k+rf"], "mid": c["mid_bands_1k_4.5k+rf"],
                "high": c["high_bands_4.5k+rf"], "real": c["shape+rf_real"], "setting_only": c["setting_only+rf"],
                "null_summary": c["null_summary"], "runin_flagged": c["runin_flagged"], "runin_hours": c["runin_hours"]}
    return None


def proof(summary, r3, checks, questions, checks3=None, r4=None) -> dict:
    runs = summary["runs"]
    r2 = summary.get("round2", {}).get("runs", {})
    rounds = [{
        "round": 1, "name": "Round 1: hiss shape, straight line model", "sealed": summary["prereg_fingerprint"][:12],
        "same_load": _run(runs[summary["headline_key"]]), "seen_ba": runs[summary["headline_key"]]["seen_ba"],
        "new_load": {k: _run(v) for k, v in summary.get("load_shift", {}).items()},
        "quality": {k.split("|")[1]: _run(v) for k, v in runs.items() if k.startswith("shape|")},
    }]
    if r2:
        rounds.append({
            "round": 2, "name": "Round 2: hiss shape, forest model", "sealed": summary["round2"]["fingerprint_round2"][:12],
            "same_load": _run(r2["lab"]["selected"]), "seen_ba": (checks or {}).get("seen_ba"),
            "new_load": {k: {"ba": v[0], "ci": v[1]} for k, v in (checks or {}).get("load_shift", {}).items()},
            "new_load_control": {k: {"ba": v[0], "ci": v[1]}
                                 for k, v in (checks or {}).get("same_condition_control", {}).items()},
            "quality": {k: _run(v["selected"]) for k, v in r2.items()},
            "new_load_note": "computed after round 2 with round 1's sealed load test (exploratory)",
        })
    if r3:
        rounds.append({
            "round": 3, "name": "Round 3: hiss compared with the fleet at the same load",
            "sealed": r3["fingerprint_round3"][:12],
            "same_load": _run(r3["same_load"]["lab"]), "seen_ba": r3["seen_ba"].get("lab"),
            "new_load": {k: _run(v) for k, v in r3["new_load"].get("lab", {}).items()},
            "new_load_plant": {k: _run(v) for k, v in r3["new_load"].get(summary["plant_key"].split("|")[1], {}).items()},
            "quality": {k: _run(v) for k, v in r3["same_load"].items()},
            "candidates": r3["candidates"],
        })
    if r4:
        rounds.append({
            "round": 4, "name": "Round 4: as round 3, force removed; published test added",
            "sealed": r4["fingerprint_round4"][:12],
            "same_load": _run(r4["same_load"]["lab"]), "seen_ba": r4["seen_ba"].get("lab"),
            "new_load": {k: _run(v) for k, v in r4["new_load"].get("lab", {}).items()},
            "new_load_plant": {k: _run(v) for k, v in r4["new_load"].get(summary["plant_key"].split("|")[1], {}).items()},
            "quality": {k: _run(v) for k, v in r4["same_load"].items()},
            "candidates": r4["candidates"],
        })
    pr = plant_round(summary)
    plant_lab = {1: runs[summary["headline_key"]], 2: (r2.get("lab") or {}).get("selected"),
                 3: (r3 or {}).get("same_load", {}).get("lab"), 4: (r4 or {}).get("same_load", {}).get("lab")}[pr]
    newest = r4 or r3 or {}
    loco = {s: {"per_condition": {c: _run(v) for c, v in lo["per_condition"].items()}, "mean_ba": lo["mean_ba"],
                "pooled": _run(lo["pooled"]), "subsets": lo["subsets"]} for s, lo in (r4 or {}).get("loco", {}).items()}
    return {
        "rounds": rounds, "plant_round": pr, "plant": summary["plant"],
        "baselines": {k.split("|")[0]: _run(v) for k, v in runs.items()
                      if k.endswith("|lab") and k.split("|")[0] in ("always_damaged", "loudness", "setting_only", "tones")},
        "per_bearing": plant_lab["per_bearing"] if plant_lab else [],
        "per_condition": plant_lab["per_condition"] if plant_lab else {},
        "plant_lab": _run(plant_lab),
        "by_level": newest.get("by_level", {}), "damage_levels": round3.load_rules()["damage_levels"],
        "ring": newest.get("ring", {}), "ring_shown": newest.get("ring_shown", False),
        "authors_split": newest.get("authors_split", {}),
        "authors_reported": {k: PUBLISHED["lessmeier"][k] for k in ("mcs_low", "mcs_high", "mcs_ensemble", "guess")},
        "loco": loco, "loco_candidates": {s: {n: {"loco_mean": c.get("loco_mean"), "loco": c.get("loco"),
                                                   "subsets": c.get("loco_subsets")}
                                               for n, c in cands.items() if "loco_mean" in c}
                                           for s, cands in (r4 or {}).get("candidates", {}).items()},
        "published": PUBLISHED,
        "checks": {k: v for k, v in (checks or {}).items() if k not in ("null",)},
        "hearing": hearing(pr, checks, checks3),
        "cekic_akan": PUBLISHED["cekic_akan"]["target_a"]["ba"],
        "questions": {"n": len(questions or []), "auto_ok": sum(q["auto_ok"] for q in questions or []),
                      "must_decline": sum(q["must_decline"] for q in questions or []),
                      "declined": sum(q["must_decline"] and "don't know" in q["answer"].lower().replace("’", "'")
                                      for q in questions or []),
                      "claude_ok": sum(bool(q.get("claude_ok")) for q in questions or []),
                      "human_ok": [q.get("human_ok") for q in questions or []]},
    }


def build(results=ROOT / "results", data=ROOT / "data") -> dict:
    rules, rules3 = prereg.load(), round3.load_rules()
    summary = _j(results / "summary.json")
    r3 = _j(results / "round3.json")
    r4 = _j(results / "round4.json")
    checks = _j(results / "round2_checks.json")
    checks3 = _j(results / "round3_checks.json")
    questions = _j(results / "assistant_questions.json")
    motors = _j(results / "motors.json")
    table = round2.merged_table(data / "features.parquet", data / "features2.parquet")
    pr = plant_round(summary)
    h = hiss(table, rules)
    h["listening"] = listening_weights(table, rules, rules3, pr if pr in (2, 3, 4) else 2)
    app = {"motors": motors, "hiss": h, "proof": proof(summary, r3, checks, questions, checks3, r4),
           "fingerprints": {"round1": summary["prereg_fingerprint"],
                            "round2": summary.get("round2", {}).get("fingerprint_round2"),
                            "round3": (r3 or {}).get("fingerprint_round3"),
                            "round4": (r4 or {}).get("fingerprint_round4")},
           "licence": "Derived from the Paderborn bearing data (Lessmeier et al., PHME 2016), CC BY-NC 4.0."}
    for path in (OUT, API_COPY):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(app, separators=(",", ":")), encoding="utf-8")
    return app


if __name__ == "__main__":
    a = build()
    print("motors", len(a["motors"]), "plant round", a["proof"]["plant_round"], "bytes", OUT.stat().st_size)
