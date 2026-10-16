import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")

RUN = {"forced_ba": 0.7, "ci": [0.6, 0.8], "false_alarm": 0.3, "miss": 0.3, "decided_share": 0.8,
       "decided_ba": "undefined", "seen_ba": 0.98, "per_condition": {"N15_M07_F10": 0.7},
       "by_origin": {"healthy": 0.3}, "fold_ba": {"1": 0.7}, "thresholds": {"1": {"line": 0.6, "band": 0.1}},
       "per_bearing": [{"bearing": "K001", "origin": "healthy", "share_flagged": 0.3, "n": 80}],
       "ece": 0.2, "n_recordings": 2560, "n_unusable": 0}


def write_results(d: Path):
    motors = [
        {"motor_name": "Motor 01", "bearing": "K001", "origin": "healthy", "label": 0, "fold": "1",
         "verdict": "healthy", "plant_word": "healthy", "how_sure": "high", "p_median": 0.1,
         "n_recordings": 20, "evidence": [], "urgency": None, "detector": "shape", "setting": "16k_12b"},
        {"motor_name": "Motor 02", "bearing": "KA04", "origin": "real", "label": 1, "fold": "1",
         "verdict": "damaged", "plant_word": "check bearing", "how_sure": "medium", "p_median": 0.8,
         "n_recordings": 20, "evidence": ["a stronger trace at a outer-ring bearing pitch than the average motor in training"],
         "urgency": "next routine visit, with a manual check", "detector": "shape", "setting": "16k_12b"},
    ]
    summary = {"prereg_fingerprint": "x" * 64, "headline_key": "shape|lab", "plant_key": "shape|16k_12b",
               "runs": {"shape|lab": RUN, "shape|16k_12b": RUN, "tones|lab": RUN, "loudness|lab": RUN,
                        "setting_only|lab": RUN, "always_damaged|lab": {**RUN, "seen_ba": None}},
               "plant": {"catch_rate": 0.6, "false_alarm_rate": 0.33, "handoff_healthy": 0.17,
                         "handoff_damaged": 0.1, "n_healthy": 6, "n_damaged": 26, "ece": 0.2, "percent_ok": False},
               "load_shift": {}}
    (d / "motors.json").write_text(json.dumps(motors))
    (d / "summary.json").write_text(json.dumps(summary))


def start(tmp_path, monkeypatch):
    write_results(tmp_path)
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("AMD_KEY", "")
    return AppTest.from_file(APP, default_timeout=30).run()


def test_banner_and_check_bearing_first(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    assert not at.exception
    assert "not a live plant" in at.info[0].value
    first = at.dataframe[0].value.iloc[0]
    assert first["Status"].endswith("check bearing")


def test_motor_page_without_key_shows_template_warning(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Motor").run()
    assert not at.exception
    assert any("offline" in w.value for w in at.warning)
    assert "not a live plant" in at.info[0].value


def test_results_and_value_pages_render(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    for page in ("Results", "Business value", "About"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        assert "not a live plant" in at.info[0].value


def test_plant_page_names_first_motor_and_its_reason(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    text = " ".join(m.value for m in at.markdown)
    assert "Check first: Motor 02" in text and "outer-ring" in text


def test_results_gap_sentence_follows_the_numbers(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert any("recognise each bearing" in m.value for m in at.markdown)      # 0.98 seen vs 0.70 honest
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["shape|lab"]["seen_ba"] = 0.72
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert not any("recognise each bearing" in m.value for m in at.markdown)
    assert any("close" in m.value for m in at.markdown)


def start_again(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("AMD_KEY", "")
    return AppTest.from_file(APP, default_timeout=30).run()


def test_results_page_applies_preregistered_flags(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["shape|8k_12b"] = {**RUN, "forced_ba": 0.55}       # drop of 0.15 from lab
    summary["runs"]["tones|8k_12b"] = {**RUN, "forced_ba": 0.68}       # drop of 0.02
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "'shape' lost 0.15" in text and "flag" in text
    assert "'tones' lost 0.02" in text
    assert "authors' split" in text and "not run" in text


def test_results_page_shows_round2_beside_round1(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    cand = {n: {**RUN, "forced_ba": v} for n, v in (("shape+lr", 0.51), ("contrast+rf", 0.58))}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": False,
                         "runs": {"lab": {"selected": {**RUN, "forced_ba": 0.57, "ci": [0.45, 0.69]},
                                          "chosen_per_fold": {"1": "contrast+rf"}, "candidates": cand}}}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Round 2" in " ".join(h.value for h in at.subheader)
    assert "0.57" in text and "0.45 to 0.69" in text
    assert "stays on round 1" in text


def test_percent_is_shown_with_its_zones_when_calibrated(tmp_path, monkeypatch):
    """Gap 2: a damage estimate is only readable next to the line, so the zones are shown as percentages too."""
    write_results(tmp_path)
    motors = json.loads((tmp_path / "motors.json").read_text())
    for m in motors:
        m.update(line=0.8, band=0.02, medium=0.05)
    motors[0]["p_median"] = 0.70
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["plant"].update(ece=0.07, percent_ok=True)
    (tmp_path / "motors.json").write_text(json.dumps(motors))
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("AMD_KEY", "")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    table = at.dataframe[0].value
    row = table[table["Motor"] == "Motor 01"].iloc[0]
    assert row["How sure"] == "high"
    assert row["Damage estimate"] == "70%"
    assert row["Ask a person"] == "78% to 82%"
    assert "compare it with the line" in " ".join(c.value for c in at.caption)


def test_no_percent_when_not_calibrated(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    assert "Damage estimate" not in at.dataframe[0].value.columns


def test_results_page_says_when_a_detector_is_below_chance_and_names_the_900rpm_limit(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["tones|lab"] = {**RUN, "forced_ba": 0.42, "ci": [0.35, 0.48]}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "'tones' scored below chance" in text and "0.35 to 0.48" in text
    assert "'shape' scored below chance" not in text
    assert "900 rpm" in text


def test_results_page_checks_whether_motor_percentages_rank(tmp_path, monkeypatch):
    """Gap 2 research: calibrated on average is not the same as ranking; say which way the estimates point."""
    write_results(tmp_path)
    motors = json.loads((tmp_path / "motors.json").read_text())
    extra = [{**motors[1], "motor_name": f"Motor {i:02d}", "label": lab, "p_median": p}
             for i, (lab, p) in enumerate([(1, 0.70), (1, 0.75), (0, 0.90), (1, 0.95)], start=3)]
    (tmp_path / "motors.json").write_text(json.dumps(motors + extra))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    # motors sorted by estimate: 0.1(h) 0.7(d) 0.75(d) | 0.8(d) 0.9(h) 0.95(d) -> lower half 67%, upper half 67%
    assert "lower half of damage estimates: 67% damaged" in text
    assert "upper half: 67% damaged" in text


def test_results_page_says_plainly_whether_it_beats_the_baselines(tmp_path, monkeypatch):
    """SC-2, with real-looking numbers: headline 0.51 (0.40 to 0.63), best baseline always_damaged 0.50."""
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["shape|lab"] = {**RUN, "forced_ba": 0.51, "ci": [0.40, 0.63]}
    summary["runs"]["always_damaged|lab"] = {**RUN, "forced_ba": 0.50, "seen_ba": None}
    summary["runs"]["loudness|lab"] = {**RUN, "forced_ba": 0.43}
    summary["runs"]["setting_only|lab"] = {**RUN, "forced_ba": 0.49}
    summary["runs"]["tones|8k_12b"] = {**RUN, "forced_ba": 0.71}        # tones|lab is 0.70: a gain
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "does not clearly beat the simple baselines" in text
    assert "always_damaged, 0.50" in text
    assert "'tones' gained 0.01" in text


def test_value_page_compares_with_checking_every_motor(tmp_path, monkeypatch):
    at = start(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Business value").run()
    text = " ".join(m.value for m in at.markdown)
    assert "a person checks every motor every round" in text


def test_results_page_says_which_round_each_number_comes_from(tmp_path, monkeypatch):
    """After the sealed switch, the plant view is round 2 while the sealed-first headline stays round 1."""
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["shape|lab"] = {**RUN, "forced_ba": 0.51, "ci": [0.40, 0.63]}
    sel = {**RUN, "forced_ba": 0.82, "ci": [0.68, 0.92]}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": True,
                         "runs": {"lab": {"selected": sel, "chosen_per_fold": {"1": "shape+rf"},
                                          "candidates": {"shape+rf": sel}},
                                  "16k_12b": {"selected": {**sel, "ci": [0.64, 0.92]},
                                              "chosen_per_fold": {"1": "shape+rf"}, "candidates": {"shape+rf": sel}}}}
    summary["plant_round1"] = {**summary["plant"], "catch_rate": 0.65, "false_alarm_rate": 0.83}
    summary["plant"] = {**summary["plant"], "catch_rate": 0.69, "false_alarm_rate": 0.17}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Round 1 (sealed first): 0.51" in text and "Round 2: 0.82" in text
    assert "The plant view uses round 2" in text
    assert "Per motor, round 2" in text and "69%" in text
    assert "Per motor, round 1" in text and "83%" in text


CHECKS = {"note": "exploratory", "shape+rf_real": [0.82, [0.68, 0.92]], "setting_only+rf": [0.50, [0.50, 0.50]],
          "tones+rf": [0.42, [0.37, 0.48]], "loudness+rf": [0.55, [0.45, 0.63]],
          "low_bands_1k+rf": [0.62, [0.49, 0.76]], "mid_bands_1k_4.5k+rf": [0.79, [0.64, 0.92]],
          "high_bands_4.5k+rf": [0.84, [0.70, 0.94]],
          "null_summary": {"n": 20, "mean": 0.47, "max": 0.69, "share_at_or_above_real": 0.0},
          "runin_hours": {"K001": ">50", "K003": "1"}, "runin_flagged": {"K001": 0.0, "K003": 0.71}}


def test_results_page_shows_the_round2_checks(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    sel = {**RUN, "forced_ba": 0.82, "ci": [0.68, 0.92]}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": True,
                         "runs": {"lab": {"selected": sel, "chosen_per_fold": {"1": "shape+rf"},
                                          "candidates": {"shape+rf": sel}},
                                  "8k_12b": {"selected": {**sel, "forced_ba": 0.75},
                                             "chosen_per_fold": {"1": "shape+rf"}, "candidates": {"shape+rf": sel}}}}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    (tmp_path / "round2_checks.json").write_text(json.dumps(CHECKS))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "not sealed" in " ".join(h.value for h in at.subheader)
    assert "20 times" in text and "0.47" in text and "0.69" in text
    assert "0.40 above" in text and "flag" in text           # 0.82 - 0.42, HR-15
    assert "lost 0.07" in text                                # lab 0.82 -> 8k 0.75, FR-017 for round 2
    assert "K003" in text and "1 h" in text


def test_null_sentence_says_when_a_random_group_came_close(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    sel = {**RUN, "forced_ba": 0.82, "ci": [0.68, 0.92]}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": True,
                         "runs": {"lab": {"selected": sel, "chosen_per_fold": {"1": "shape+rf"},
                                          "candidates": {"shape+rf": sel}}}}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    close = {**CHECKS, "null_summary": {"n": 20, "mean": 0.49, "max": 0.79, "share_at_or_above_real": 0.0}}
    (tmp_path / "round2_checks.json").write_text(json.dumps(close))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "None of the 20 reached 0.82" in text
    assert "close to it" in text and "moderate" in text


def test_estimates_never_show_100_or_0_percent(tmp_path, monkeypatch):
    """A rounded 100% reads as certainty, which the product never claims."""
    write_results(tmp_path)
    motors = json.loads((tmp_path / "motors.json").read_text())
    for m in motors:
        m.update(line=0.8, band=0.02, medium=0.05)
    motors[0]["p_median"], motors[1]["p_median"] = 0.003, 0.9974
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["plant"].update(ece=0.07, percent_ok=True)
    (tmp_path / "motors.json").write_text(json.dumps(motors))
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    estimates = set(at.dataframe[0].value["Damage estimate"])
    assert estimates == {"under 1%", "over 99%"}
    assert "100%" not in " ".join(m.value for m in at.markdown)


def test_results_page_reports_the_question_test(tmp_path, monkeypatch):
    """FR-018: 'passed X of 30' on the Results page; a person's read shown as pending until filled."""
    write_results(tmp_path)
    rows = [{"motor": "Motor 01", "question": "q", "must_decline": d,
             "answer": "I don’t know that from this data." if d else "a", "source": "Gemma-4-31B-IT",
             "auto_ok": True, "human_ok": None, "claude_ok": ok} for d, ok in ((True, True), (False, True), (False, False))]
    (tmp_path / "assistant_questions.json").write_text(json.dumps(rows))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "3 of 3 passed the automatic check" in text
    assert "2 of 3 were right when read by Claude" in text
    assert "Hamza's read: pending" in text
    assert "1 of 1 questions it had to decline were declined" in text


def test_round2_section_has_baselines_seen_number_tables_and_load(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["runs"]["always_damaged|lab"] = {**RUN, "forced_ba": 0.50, "seen_ba": None}
    summary["runs"]["loudness|lab"] = {**RUN, "forced_ba": 0.43}
    summary["runs"]["setting_only|lab"] = {**RUN, "forced_ba": 0.49}
    sel = {**RUN, "forced_ba": 0.82, "ci": [0.68, 0.92]}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": True,
                         "runs": {"lab": {"selected": sel, "chosen_per_fold": {"1": "shape+rf"},
                                          "candidates": {"shape+rf": sel}}}}
    summary["plant_round1"] = summary["plant"]
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    checks = {**CHECKS, "seen_ba": 0.94, "load_shift": {"N15_M07_F10->N15_M01_F10": [0.7, [0.5, 0.85]]}}
    (tmp_path / "round2_checks.json").write_text(json.dumps(checks))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert ") (" not in text
    assert "whole 95% range is above it: round 2 beats the simple baselines" in text
    assert "0.94" in text and "inflated" in text
    assert "N15_M07_F10->N15_M01_F10" in " ".join(str(df.value.to_dict()) for df in at.dataframe)


def test_round2_load_test_is_read_against_its_same_condition_control(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    sel = {**RUN, "forced_ba": 0.82, "ci": [0.68, 0.92]}
    summary["round2"] = {"fingerprint_round2": "y" * 64, "plant_switched": True,
                         "runs": {"lab": {"selected": sel, "chosen_per_fold": {"1": "shape+rf"},
                                          "candidates": {"shape+rf": sel}}}}
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    checks = {**CHECKS, "seen_ba": 0.94,
              "load_shift": {"N15_M07_F10->N15_M01_F10": [0.51, [0.5, 0.53]], "N15_M01_F10->N15_M07_F10": [0.5, [0.5, 0.5]]},
              "same_condition_control": {"N15_M07_F10->N15_M07_F10": [0.80, [0.64, 0.94]],
                                         "N15_M01_F10->N15_M01_F10": [0.81, [0.65, 0.93]]}}
    (tmp_path / "round2_checks.json").write_text(json.dumps(checks))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Results").run()
    text = " ".join(m.value for m in at.markdown)
    assert "does not carry over to a new load" in text


def test_value_page_warns_that_round2_rates_need_known_loads(tmp_path, monkeypatch):
    write_results(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    summary["plant_round1"] = summary["plant"]
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    at = start_again(tmp_path, monkeypatch)
    at.sidebar.radio[0].set_value("Business value").run()
    text = " ".join(w.value for w in at.warning) + " ".join(m.value for m in at.markdown)
    assert "only at loads it was trained on" in text
