"""P-14 feature extraction on Kaggle. Raw Paderborn files are downloaded, turned into numbers, and deleted.
Only the feature table is kept as output (derived from CC BY-NC 4.0 data; this notebook is private)."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

FROZEN = "383402e7d27e20edc020ccb39160393b587bca00d18fd59b30eb2925d394173e"
src = next(Path("/kaggle/input").rglob("bearing/__init__.py")).parent.parent
code = Path("/kaggle/working/code")
for part in ("bearing", "prereg"):
    shutil.copytree(src / part, code / part, dirs_exist_ok=True)
sys.path.insert(0, str(code))

subprocess.run("apt-get -qq update >/dev/null 2>&1; apt-get -qq install -y unrar >/dev/null 2>&1 || "
               "apt-get -qq install -y libarchive-tools >/dev/null 2>&1", shell=True)
print("tools:", {t: shutil.which(t) for t in ("unrar", "7z", "bsdtar")}, flush=True)

import pandas as pd  # noqa: E402
from bearing import config, extract, prereg  # noqa: E402

fp = prereg.fingerprint()
print("prereg fingerprint", fp, flush=True)
assert fp == FROZEN, "the rules file is not the frozen one"
rules = prereg.load()
OUT, WORK = Path("/kaggle/working/out"), Path("/kaggle/temp/work")
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)


def one(b):
    for attempt in range(3):
        try:
            t = time.time()
            path = extract.run_bearing(b, WORK, OUT, rules)
            d = pd.read_parquet(path)
            print(f"{b}: rows {len(d)} usable {d.usable.mean():.3f} in {time.time() - t:.0f}s", flush=True)
            return d
        except Exception as exc:
            print(f"{b}: attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:150]}", flush=True)
            (WORK / f"{b}.rar").unlink(missing_ok=True)
            shutil.rmtree(WORK / b, ignore_errors=True)
            time.sleep(10)
    return None


smoke = one("K001")
assert smoke is not None and len(smoke) == 400 and smoke.usable.mean() > 0.9, "smoke test failed, stopping"
lab = smoke[smoke.setting == "lab"]
print(lab.groupby("condition")[["fe_hz", "residual_db"]].mean().round(2), flush=True)

failed = [b for b in config.ALL_BEARINGS if b != "K001" and one(b) is None]
table = pd.concat([pd.read_parquet(p) for p in sorted(OUT.glob("features_*.parquet"))], ignore_index=True)
table.to_parquet("/kaggle/working/features.parquet")
print("FAILED BEARINGS", failed, flush=True)
print("rows", len(table), "usable", int(table.usable.sum()), "bearings", table.bearing.nunique(),
      "clipped", int(table.n_clipped.sum()), flush=True)
print(table.groupby("setting").usable.agg(["size", "sum"]), flush=True)
print(table[~table.usable].groupby(["bearing", "error"]).size().head(20), flush=True)
print("DONE", flush=True)
