"""From a damage estimate to a verdict. All cut-offs come from training bearings only (HR-10, HR-11, HR-19)."""
from dataclasses import dataclass

import numpy as np

from .metrics import balanced_accuracy

HEALTHY, DAMAGED, PERSON = "healthy", "damaged", "needs a person"
PLANT_WORD = {HEALTHY: "healthy", DAMAGED: "check bearing", PERSON: "ask a person"}


@dataclass(frozen=True)
class Thresholds:
    line: float      # damaged above, healthy below (HR-19)
    band: float      # half-width of the "ask a person" band around the line (HR-11)
    medium: float    # margins up to this are "medium" sure, beyond are "high"


def best_line(p, y) -> float:
    p, y = np.asarray(p, dtype=float), np.asarray(y)
    values = np.unique(p)
    candidates = np.concatenate([[0.5], (values[:-1] + values[1:]) / 2]) if len(values) > 1 else np.array([0.5])
    scored = [(balanced_accuracy(y, (p > t).astype(int)) or 0.0, -abs(t - 0.5), t) for t in candidates]
    return float(max(scored)[2])


def fit_thresholds(p_oof, y_oof, handoff_share: float, medium_upto_share: float) -> Thresholds:
    line = best_line(p_oof, y_oof)
    margin = np.abs(np.asarray(p_oof, dtype=float) - line)
    return Thresholds(line=line,
                      band=float(np.quantile(margin, handoff_share)),
                      medium=float(np.quantile(margin, medium_upto_share)))


def verdict(p: float, th: Thresholds) -> str:
    if abs(p - th.line) <= th.band:
        return PERSON
    return DAMAGED if p > th.line else HEALTHY


def sureness(p: float, th: Thresholds) -> str:
    margin = abs(p - th.line)
    if margin <= th.band:
        return "low"
    return "medium" if margin <= th.medium else "high"


def motor_verdict(ps, th: Thresholds, min_recordings: int) -> tuple[str, float | None]:
    if len(ps) < min_recordings:
        return PERSON, None
    p = float(np.median(ps))
    return verdict(p, th), p


def urgency(plant_word: str, how_sure: str, rules: dict) -> str | None:
    return rules["urgency"].get(f"{plant_word}|{how_sure}")
