"""The pre-registration: everything fixed before any test result is seen (HR-9, HR-11, HR-19)."""
import hashlib
import json
from pathlib import Path

from . import config

PREREG_PATH = Path(__file__).resolve().parent.parent / "prereg" / "prereg.json"
KNOWN_DETECTORS = {"shape", "tones", "loudness", "setting_only", "always_damaged"}


def load(path: Path = PREREG_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path: Path = PREREG_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(rules: dict) -> list[str]:
    problems = []
    placed = [b for fold in rules["folds"].values() for b in fold]
    for b in config.ALL_BEARINGS:
        if placed.count(b) != 1:
            problems.append(f"{b} appears {placed.count(b)} times in the folds")
    for name, fold in rules["folds"].items():
        n_healthy = sum(b in config.HEALTHY for b in fold)
        if n_healthy != 1:
            problems.append(f"fold {name} has {n_healthy} healthy bearings, needs exactly 1")
        if n_healthy == len(fold):
            problems.append(f"fold {name} has no damaged bearing")
    for part in ("headline", "plant_view"):
        if rules[part]["setting"] not in rules["quality_settings"]:
            problems.append(f"{part} setting is not a quality setting")
        if rules[part]["detector"] not in KNOWN_DETECTORS:
            problems.append(f"{part} detector is unknown")
    for d in rules["detectors"]:
        if d not in KNOWN_DETECTORS:
            problems.append(f"unknown detector {d}")
    return problems
