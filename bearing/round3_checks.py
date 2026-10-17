"""Checks run AFTER round 3 to test its result (exploratory, NOT sealed), mirroring the checks done after round 2.

- physics check (HR-15): the same fleet-normal forest hearing only the classic bearing pitches;
- where it listens: one pitch range at a time;
- null test: in each test group a random bearing is called "healthy" instead of the real one;
- run-in: share of each healthy bearing's recordings flagged, against Lessmeier Table 7 run-in hours.
Lab quality, same groups, line and band rules as round 3. Numbers go to results/round3_checks.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

from . import config, evaluate, metrics, prereg, round2, round3
from .features import BAND_EDGES

RUNIN_HOURS = {"K001": ">50", "K002": "19", "K003": "1", "K004": "5", "K005": "10", "K006": "16"}


def bands_between(lo, hi):
    return [f"band_{k:02d}" for k in range(len(BAND_EDGES) - 1) if BAND_EDGES[k] >= lo and BAND_EDGES[k + 1] <= hi]


def score(d, cand, rules, n_boot):
    pred, _ = round3.outer_run(d, cand, rules)
    s = evaluate.summarize(pred, 0, None, rules, n_boot)
    return [s["forced_ba"], s["ci"]], pred


def run(features_path, features2_path, out_path, n_null=10, n_boot=None, seed=0):
    rules = prereg.load()
    table = round2.merged_table(features_path, features2_path)
    d = table[(table.setting == "lab") & table.usable].dropna(axis=1, how="all")
    out = {"note": "Exploratory checks run AFTER round 3, not sealed. Lab quality, same groups, line and band rules "
                   "as round 3. Derived from the Paderborn data (CC BY-NC 4.0)."}
    fleet = lambda feats: {"features": feats, "normal": "fleet"}
    out["tones_fleet+rf"], _ = score(d, fleet(["tone_"]), rules, n_boot)
    print("tones", out["tones_fleet+rf"], flush=True)
    for name, (lo, hi) in {"low_bands_1k": (0, 1000), "mid_bands_1k_4.5k": (1000, 4600),
                           "high_bands_4.5k": (4500, 1e9)}.items():
        cols = bands_between(lo, hi)
        dd = d.drop(columns=[c for c in d.columns if c.startswith("band_") and c not in cols])
        out[f"{name}_fleet+rf"], _ = score(dd, fleet(["band_"]), rules, n_boot)
        print(name, out[f"{name}_fleet+rf"], flush=True)
    real, pred = score(d, fleet(["band_"]), rules, n_boot)
    out["shape_fleet+rf_real"] = real
    flagged = pred[pred.label == 0].groupby("bearing").forced.mean()
    out["runin_flagged"] = {b: round(float(v), 4) for b, v in flagged.items()}
    out["runin_hours"] = RUNIN_HOURS
    rng = np.random.default_rng(seed)
    null = []
    for i in range(n_null):
        fake = {}
        for bs in rules["folds"].values():
            fake[rng.choice(bs)] = 0
        lab = d.bearing.map(lambda b: fake.get(b, 1))
        dn = d.assign(label=lab.astype(int))
        ba, _ = score(dn, fleet(["band_"]), rules, n_boot or 200)
        null.append({"fake_healthy": sorted(fake), "real_healthy_among_them": sum(b in config.HEALTHY for b in fake),
                     "ba": ba[0]})
        print("null", i, ba[0], flush=True)
    vals = [x["ba"] for x in null]
    out["null"] = null
    out["null_summary"] = {"n": len(vals), "mean": round(float(np.mean(vals)), 4), "max": round(float(np.max(vals)), 4),
                           "share_at_or_above_real": round(float(np.mean([v >= real[0] for v in vals])), 4)}
    Path(out_path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run(Path("data/features.parquet"), Path("data/features2.parquet"), Path("results/round3_checks.json"), n_null=n)
