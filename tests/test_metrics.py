import numpy as np
import pandas as pd

from bearing import metrics


def test_balanced_accuracy_basic():
    assert metrics.balanced_accuracy([0, 0, 1, 1], [0, 1, 1, 1]) == 0.75


def test_balanced_accuracy_undefined_with_one_class():
    assert metrics.balanced_accuracy([1, 1, 1], [1, 0, 1]) is None


def test_rates():
    r = metrics.rates([0, 0, 0, 0, 1, 1], [1, 0, 0, 0, 0, 1])
    assert r == {"false_alarm": 0.25, "miss": 0.5}


def test_bootstrap_interval_contains_point_estimate():
    rng = np.random.default_rng(0)
    rows = []
    for b in range(10):
        label = int(b >= 3)
        for _ in range(20):
            rows.append({"bearing": f"B{b}", "label": label, "forced": int(rng.random() < (0.8 if label else 0.3))})
    pred = pd.DataFrame(rows)
    lo, hi = metrics.bootstrap_ba(pred, n=200, seed=0)
    point = metrics.balanced_accuracy(pred.label, pred.forced)
    assert lo <= point <= hi


def test_ece_perfect_and_bad():
    assert metrics.ece(np.array([0.0, 0.0, 1.0, 1.0]), np.array([0, 0, 1, 1])) == 0.0
    assert metrics.ece(np.array([0.9] * 10), np.array([0] * 10)) > 0.8
