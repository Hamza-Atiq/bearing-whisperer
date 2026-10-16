"""FR-019: an ILLUSTRATIVE yearly value. Rates are measured; costs and fault rate are labelled assumptions."""


def illustrative_value(n_motors, fault_rate, catch_rate, false_alarm_rate, handoff_rate_healthy,
                       breakdown_cost, check_cost, rounds_per_year) -> dict:
    faulty = n_motors * fault_rate
    healthy = n_motors - faulty
    caught = faulty * catch_rate
    saved = caught * (breakdown_cost - check_cost)
    wasted_visits = healthy * (false_alarm_rate + handoff_rate_healthy) * rounds_per_year
    # The plain alternative: a person checks every motor every round (assumption: a manual check finds every fault).
    visit_all_wasted = healthy * rounds_per_year
    visit_all_saved = faulty * (breakdown_cost - check_cost)
    return {"faulty": faulty, "caught": caught, "saved": saved, "wasted_visits": wasted_visits,
            "net": saved - wasted_visits * check_cost,
            "visit_all_caught": faulty, "visit_all_wasted_visits": visit_all_wasted,
            "visit_all_net": visit_all_saved - visit_all_wasted * check_cost}
