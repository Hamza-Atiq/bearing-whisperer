from pytest import approx

from bearing import business


def test_illustrative_value_arithmetic():
    v = business.illustrative_value(n_motors=100, fault_rate=0.05, catch_rate=0.6, false_alarm_rate=0.2,
                                    handoff_rate_healthy=0.1, breakdown_cost=20_000, check_cost=150,
                                    rounds_per_year=4)
    assert v["caught"] == approx(3.0)
    assert v["saved"] == approx(3.0 * (20_000 - 150))
    assert v["wasted_visits"] == approx(95 * 0.3 * 4)
    assert v["net"] == approx(v["saved"] - v["wasted_visits"] * 150)


def test_compares_with_checking_every_motor():
    """FR-019 honesty: the detector must be compared with the plain alternative of visiting every motor each round,
    not only with doing nothing (assumption: a manual check finds every fault)."""
    v = business.illustrative_value(n_motors=100, fault_rate=0.05, catch_rate=0.6538, false_alarm_rate=0.8333,
                                    handoff_rate_healthy=0.1667, breakdown_cost=20_000, check_cost=150,
                                    rounds_per_year=4)
    assert v["visit_all_caught"] == approx(5.0)
    assert v["visit_all_wasted_visits"] == approx(95 * 4)
    assert v["visit_all_net"] == approx(5.0 * (20_000 - 150) - 95 * 4 * 150)
    assert v["visit_all_net"] > v["net"]
