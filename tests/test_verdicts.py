import numpy as np

from bearing import prereg, verdicts as v


def test_best_line_maximises_balanced_accuracy():
    p = np.array([0.1, 0.2, 0.3, 0.6, 0.7, 0.9])
    y = np.array([0, 0, 0, 1, 1, 1])
    line = v.best_line(p, y)
    assert 0.3 <= line < 0.6


def test_thresholds_put_20_percent_in_band():
    rng = np.random.default_rng(0)
    p = rng.random(1000)
    y = (p + rng.normal(0, 0.2, 1000) > 0.5).astype(int)
    th = v.fit_thresholds(p, y, 0.20, 0.50)
    inside = np.mean(np.abs(p - th.line) <= th.band)
    assert 0.18 <= inside <= 0.22
    assert th.medium >= th.band


def test_band_edges_are_inclusive():
    th = v.Thresholds(line=0.6, band=0.1, medium=0.2)
    assert v.verdict(0.7, th) == v.PERSON
    assert v.verdict(0.5, th) == v.PERSON
    assert v.verdict(0.7001, th) == v.DAMAGED
    assert v.verdict(0.4999, th) == v.HEALTHY


def test_sureness_words():
    th = v.Thresholds(line=0.5, band=0.1, medium=0.2)
    assert v.sureness(0.55, th) == "low"
    assert v.sureness(0.68, th) == "medium"
    assert v.sureness(0.95, th) == "high"
    assert v.sureness(0.05, th) == "high"


def test_motor_uses_median():
    th = v.Thresholds(line=0.5, band=0.05, medium=0.2)
    word, p = v.motor_verdict([0.9] * 11 + [0.1] * 9, th, 10)
    assert word == v.DAMAGED and p == 0.9


def test_motor_with_too_few_recordings_needs_a_person():
    th = v.Thresholds(line=0.5, band=0.05, medium=0.2)
    assert v.motor_verdict([0.99] * 9, th, 10) == (v.PERSON, None)


def test_urgency_follows_preregistered_rule():
    rules = prereg.load()
    assert v.urgency("check bearing", "high", rules) == "this week"
    assert v.urgency("check bearing", "medium", rules) == "next routine visit, with a manual check"
    assert v.urgency("ask a person", "low", rules) == "next routine visit, with a manual check"
    assert v.urgency("healthy", "high", rules) is None
