"""Scores. Balanced accuracy is the mean of the healthy hit rate and the damaged hit rate (HR-5)."""
import numpy as np
import pandas as pd


def balanced_accuracy(y, yhat) -> float | None:
    y, yhat = np.asarray(y), np.asarray(yhat)
    if len(np.unique(y)) < 2:
        return None                                   # "undefined" (HR-18)
    tpr = float(np.mean(yhat[y == 1] == 1))
    tnr = float(np.mean(yhat[y == 0] == 0))
    return (tpr + tnr) / 2


def rates(y, yhat) -> dict:
    y, yhat = np.asarray(y), np.asarray(yhat)
    healthy, damaged = y == 0, y == 1
    return {"false_alarm": float(np.mean(yhat[healthy] == 1)) if healthy.any() else None,
            "miss": float(np.mean(yhat[damaged] == 0)) if damaged.any() else None}


def bootstrap_ba(pred: pd.DataFrame, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% range from resampling whole bearings, because recordings of one bearing are not independent (HR-4)."""
    rng = np.random.default_rng(seed)
    groups = {b: (g.label.to_numpy(), g.forced.to_numpy()) for b, g in pred.groupby("bearing")}
    healthy = [b for b, (y, _) in groups.items() if y[0] == 0]
    damaged = [b for b, (y, _) in groups.items() if y[0] == 1]
    values = []
    for _ in range(n):
        pick = list(rng.choice(healthy, len(healthy))) + list(rng.choice(damaged, len(damaged)))
        y = np.concatenate([groups[b][0] for b in pick])
        f = np.concatenate([groups[b][1] for b in pick])
        values.append(balanced_accuracy(y, f))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def ece(p, y, bins: int = 10) -> float:
    """Calibration error: how far 'about 80% damaged' is from 80% really damaged, averaged over bins."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)
