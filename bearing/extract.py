"""Colab job: download each bearing, read its recordings, write one features file per bearing.

Raw files are deleted after each bearing, so disk use stays small. Raw data never leaves Colab.
"""
import argparse
import shutil
import subprocess
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

from . import config, prereg
from .features import UnusableRecording, recording_features
from .quality import simulate

SECONDS = 4
SEVEN_ZIP = Path(r"C:/Program Files/7-Zip/7z.exe")


def parse_name(stem: str) -> tuple[str, str, int]:
    parts = stem.split("_")
    return "_".join(parts[:3]), parts[3], int(parts[4])


def read_currents(path: Path) -> tuple[np.ndarray, np.ndarray]:
    m = loadmat(str(path))
    key = next(k for k in m if not k.startswith("__"))
    channels = m[key]["Y"][0, 0][0]
    found = {}
    for ch in channels:
        name = str(np.asarray(ch["Name"]).ravel()[0])
        found[name] = np.asarray(ch["Data"], dtype=float).ravel()
    n = SECONDS * config.FS_LAB
    return found["phase_current_1"][:n], found["phase_current_2"][:n]


def rows_for_file(path: Path, rules: dict, features_fn=recording_features) -> list[dict]:
    condition, bearing, rec = parse_name(Path(path).stem)
    rpm, torque = config.drive_setting(condition)
    base = {"bearing": bearing, "condition": condition, "rec": rec, "rpm": rpm, "torque": torque,
            "label": config.label(bearing), "origin": config.damage_origin(bearing)}
    try:
        i1, i2 = read_currents(path)
    except Exception as exc:                       # corrupt or missing channel: counted, never guessed
        return [{**base, "setting": s, "usable": False, "error": f"read: {exc}"[:200], "n_clipped": 0}
                for s in rules["quality_settings"]]
    rows = []
    for setting, (fs, bits) in rules["quality_settings"].items():
        y1, c1 = simulate(i1, fs, bits, rules["full_scale_amps"])
        y2, c2 = simulate(i2, fs, bits, rules["full_scale_amps"])
        row = {**base, "setting": setting, "n_clipped": c1 + c2}
        try:
            row.update(features_fn(y1, y2, fs, rpm))
            row.update(usable=True, error="")
        except UnusableRecording as exc:
            row.update(usable=False, error=str(exc))
        rows.append(row)
    return rows


def unpack_command(rar: Path, folder: Path) -> list[str]:
    """unrar on Colab (Linux); 7-Zip on Windows, so the same job can also run on a laptop."""
    unrar = shutil.which("unrar")
    if unrar:
        return [unrar, "x", "-o+", "-inul", str(rar), str(folder) + "/"]
    seven = shutil.which("7z") or (str(SEVEN_ZIP) if Path(SEVEN_ZIP).exists() else None)
    if seven:
        return [seven, "x", "-y", f"-o{folder}", str(rar)]
    bsdtar = shutil.which("bsdtar")                  # libarchive also reads .rar
    if bsdtar:
        return [bsdtar, "-xf", str(rar), "-C", str(folder)]
    raise RuntimeError("no unrar, 7-Zip or bsdtar found to unpack the .rar files")


def run_bearing(bearing: str, work: Path, out: Path, rules: dict) -> Path:
    target = out / f"features_{bearing}.parquet"
    if target.exists():
        return target
    rar = work / f"{bearing}.rar"
    if not rar.exists():
        urllib.request.urlretrieve(config.DOWNLOAD_URL.format(bearing=bearing), rar)
    folder = work / bearing
    folder.mkdir(exist_ok=True)
    subprocess.run(unpack_command(rar, folder), check=True, stdout=subprocess.DEVNULL)
    rows = []
    for mat in sorted(folder.rglob("*.mat")):
        rows.extend(rows_for_file(mat, rules))
    pd.DataFrame(rows).to_parquet(target)
    shutil.rmtree(folder)
    rar.unlink()
    return target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--bearings", nargs="*", default=config.ALL_BEARINGS)
    args = ap.parse_args()
    rules = prereg.load()
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    for b in args.bearings:
        print(b, run_bearing(b, args.work, args.out, rules), flush=True)
    files = sorted(args.out.glob("features_*.parquet"))
    table = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    table.to_parquet(args.out / "features.parquet")
    print("rows", len(table), "usable", int(table.usable.sum()), "bearings", table.bearing.nunique())
    print("fingerprint", prereg.fingerprint())


if __name__ == "__main__":
    main()
