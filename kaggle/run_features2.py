"""P-14 round-2 features on Kaggle ("contrast" and "clicks"). Same download and delete pattern as round 1;
recordings of one bearing are processed on 4 cores. Output: features2.parquet (derived from CC BY-NC 4.0 data)."""
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

FROZEN = "383402e7d27e20edc020ccb39160393b587bca00d18fd59b30eb2925d394173e"
FROZEN2 = "c3f518734dac9dd3832994e9f44764702d43107f11f3ecffd3d14598b3d70222"
src = next(Path("/kaggle/input").rglob("bearing/__init__.py")).parent.parent
code = Path("/kaggle/working/code")
for part in ("bearing", "prereg"):
    shutil.copytree(src / part, code / part, dirs_exist_ok=True)
sys.path.insert(0, str(code))
subprocess.run("apt-get -qq update >/dev/null 2>&1; apt-get -qq install -y unrar >/dev/null 2>&1", shell=True)

import pandas as pd  # noqa: E402
from bearing import config, extract, prereg, round2  # noqa: E402
from bearing.features2 import recording_features2  # noqa: E402

assert prereg.fingerprint() == FROZEN and round2.fingerprint() == FROZEN2, "rules files are not the sealed ones"
RULES = prereg.load()
OUT, WORK = Path("/kaggle/working/out2"), Path("/kaggle/temp/work")
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)


def rows(path):
    return extract.rows_for_file(path, RULES, features_fn=recording_features2)


def one(b):
    target = OUT / f"features2_{b}.parquet"
    for attempt in range(3):
        try:
            t = time.time()
            rar, folder = WORK / f"{b}.rar", WORK / b
            if not rar.exists():
                import urllib.request
                urllib.request.urlretrieve(config.DOWNLOAD_URL.format(bearing=b), rar)
            folder.mkdir(exist_ok=True)
            subprocess.run(extract.unpack_command(rar, folder), check=True, stdout=subprocess.DEVNULL)
            with Pool(4) as pool:
                parts = pool.map(rows, sorted(folder.rglob("*.mat")))
            d = pd.DataFrame([r for part in parts for r in part])
            d.to_parquet(target)
            shutil.rmtree(folder)
            rar.unlink()
            print(f"{b}: rows {len(d)} usable {d.usable.mean():.3f} in {time.time() - t:.0f}s", flush=True)
            return d
        except Exception as exc:
            print(f"{b}: attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:150]}", flush=True)
            (WORK / f"{b}.rar").unlink(missing_ok=True)
            shutil.rmtree(WORK / b, ignore_errors=True)
            time.sleep(10)
    return None


if __name__ == "__main__":
    smoke = one("K001")
    assert smoke is not None and len(smoke) == 400 and smoke.usable.mean() > 0.9, "smoke test failed, stopping"
    print(smoke[smoke.setting == "lab"].filter(like="contrast_o").describe().round(2), flush=True)
    failed = [b for b in config.ALL_BEARINGS if b != "K001" and one(b) is None]
    table = pd.concat([pd.read_parquet(p) for p in sorted(OUT.glob("features2_*.parquet"))], ignore_index=True)
    table.to_parquet("/kaggle/working/features2.parquet")
    print("FAILED BEARINGS", failed, flush=True)
    print("rows", len(table), "usable", int(table.usable.sum()), "bearings", table.bearing.nunique(), flush=True)
    print(table.groupby("setting").usable.agg(["size", "sum"]), flush=True)
    print("DONE", flush=True)
