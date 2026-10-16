"""Bearing Whisperer: the web app a judge opens from one link (FR-013)."""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bearing import assistant, business, notes, round2  # noqa: E402

RESULTS = Path(os.environ.get("RESULTS_DIR", ROOT / "results"))
BANNER = ("Recorded lab bearings from the public Paderborn dataset (CC BY-NC 4.0), not a live plant. "
          "Each motor is one lab bearing on the shaft line; drive-like measurement quality is simulated.")
FLAG_GAP = 0.10        # pre-registered size of a "large" difference (prereg.json flag_gap_ba)
PAGES = ["Plant", "Motor", "Results", "Business value", "About"]
STATUS_ORDER = {"check bearing": 0, "ask a person": 1, "healthy": 2}
SURE_ORDER = {"high": 0, "medium": 1, "low": 2}
ICON = {"check bearing": "🔴", "ask a person": "🟡", "healthy": "🟢"}
ORIGIN_WORDS = {"healthy": "a healthy bearing", "artificial": "a bearing with lab-made damage",
                "real": "a bearing with real wear damage"}


@st.cache_data
def load_results(results_dir: str, version: float = 0.0):
    folder = Path(results_dir)
    motors = json.loads((folder / "motors.json").read_text(encoding="utf-8"))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return motors, summary


def sort_motors(motors):
    return sorted(motors, key=lambda m: (STATUS_ORDER[m["plant_word"]], SURE_ORDER[m["how_sure"]],
                                         -(m["p_median"] or 0)))


def api_key():
    try:
        key = st.secrets.get("AMD_KEY")
    except Exception:
        key = None
    return key or assistant.load_key()


@st.cache_data(ttl=3600, show_spinner="Asking the assistant on AMD Token Factory...")
def assistant_note(facts_json: str) -> dict:
    r = assistant.write_note(json.loads(facts_json), api_key())
    return {"text": r.text, "source": r.source}


def show_percent(m, summary):
    """FR-001: a percentage only if it was checked on unseen bearings, and only next to its own line (Gap 2)."""
    return bool(summary["plant"].get("percent_ok")) and m["p_median"] is not None and m.get("line") is not None


def pct(x):
    """Never 0% or 100%: the detector is never certain."""
    if x >= 0.995:
        return "over 99%"
    if x < 0.005:
        return "under 1%"
    return f"{x:.0%}"


def handoff_zone(m):
    return f"{m['line'] - m['band']:.0%} to {m['line'] + m['band']:.0%}"


def how_sure_text(m, summary):
    if show_percent(m, summary):
        return f"{m['how_sure']}; damage estimate {pct(m['p_median'])}, 'ask a person' zone {handoff_zone(m)}"
    return m["how_sure"]


def percent_caption(summary):
    p = summary["plant"]
    return (f"Damage estimate: the detector's estimate that the bearing is damaged, checked on bearings it never saw. "
            f"Most lab bearings here are damaged ({p['n_damaged']} of {p['n_damaged'] + p['n_healthy']}), so "
            "estimates start high: compare it with the line, not with 50%. Below the 'ask a person' zone means "
            "healthy, above it means check bearing. 'How sure' says how far the estimate is from that zone.")


def fmt(x):
    return x if isinstance(x, str) else ("n/a" if x is None else f"{x:.2f}")


def results_version(folder: Path) -> float:
    """Changes when the result files change, so a fresh run is never hidden by the cache."""
    return sum(f.stat().st_mtime for f in (folder / "motors.json", folder / "summary.json") if f.exists())


def go_motor(name=None):
    if name:
        st.session_state.motor = name
    st.session_state.page = "Motor"


def page_plant(motors, summary):
    st.header("Which motor needs attention first?")
    ordered = sort_motors(motors)
    counts = {w: sum(m["plant_word"] == w for m in motors) for w in STATUS_ORDER}
    st.write(f"{len(motors)} motors: {ICON['check bearing']} {counts['check bearing']} check bearing, "
             f"{ICON['ask a person']} {counts['ask a person']} ask a person, {ICON['healthy']} {counts['healthy']} healthy.")
    first = ordered[0]
    if first["plant_word"] == "healthy":
        st.success("No motor needs a check right now.")
    else:
        with st.container(border=True):
            reason = first["evidence"][0] if first["evidence"] else "no single clear sign"
            st.markdown(f"**Check first: {first['motor_name']}**, {ICON[first['plant_word']]} {first['plant_word']} "
                        f"(how sure: {how_sure_text(first, summary)}). Why: {reason}.")
            st.button(f"Open {first['motor_name']}", on_click=go_motor, args=(first["motor_name"],), type="primary")
    rows = []
    for m in ordered:
        row = {"Motor": m["motor_name"], "Status": f"{ICON[m['plant_word']]} {m['plant_word']}",
               "How sure": m["how_sure"]}
        if show_percent(m, summary):
            row.update({"Damage estimate": pct(m["p_median"]), "Ask a person": handoff_zone(m)})
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=280)
    st.caption("'How sure' is how confident the detector is, not how bad the damage is. "
               "Check-bearing motors come first, most sure first.")
    if any(show_percent(m, summary) for m in motors):
        st.caption(percent_caption(summary))
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    left.selectbox("Open another motor", [m["motor_name"] for m in ordered], key="motor")
    right.button("Open", on_click=go_motor)


def page_motor(motors, summary):
    by_name = {m["motor_name"]: m for m in motors}
    m = by_name.get(st.session_state.get("motor")) or sort_motors(motors)[0]
    st.header(f"{m['motor_name']}: {ICON[m['plant_word']]} {m['plant_word']}")
    st.write(f"How sure: **{how_sure_text(m, summary)}**. Urgency: **{m['urgency'] or 'none'}**.")
    if show_percent(m, summary):
        st.caption(percent_caption(summary))
    facts = notes.facts_for(m)
    res = assistant_note(json.dumps(facts, sort_keys=True))
    if res["source"] == "template":
        st.warning("The AMD assistant is offline or its answer failed our fact check, so this shows the plain "
                   "template note only.")
        st.subheader("Plain template note")
        st.write(res["text"])
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("AMD assistant note")
            st.caption(f"Written by {res['source']} on AMD Token Factory (AMD GPUs), then checked against the "
                       "detector's facts.")
            st.write(res["text"])
        with right:
            st.subheader("Plain template note")
            st.caption("Filled in by fixed code from the same facts, for comparison.")
            st.write(notes.template_note(facts))
    with st.expander("Draft work order (needs a person's approval)"):
        st.json(notes.work_order(facts, m))
    with st.expander("Ask a follow-up question"):
        q = st.text_input("Your question", key="question")
        if q:
            run = round2.plant_run(summary)
            line = f"honest balanced accuracy on unseen bearings {fmt(run['forced_ba'])}"
            st.write(assistant.answer(q, facts, line, api_key()).text)
    with st.expander("The detector facts the notes must stick to"):
        st.json(facts)
    with st.expander("For judges: what this bearing really is"):
        st.write(f"{m['motor_name']} is lab bearing {m['bearing']}, {ORIGIN_WORDS[m['origin']]}. Its verdict comes "
                 f"from test group {m['fold']}, in which the detector never trained on this bearing.")


def quality_flags(runs) -> list[str]:
    """FR-017 and HR-15, judged with the sizes fixed in the pre-registration."""
    out = []
    for det in ("shape", "tones"):
        lab, low = runs.get(f"{det}|lab"), runs.get(f"{det}|8k_12b")
        if lab and low and lab["forced_ba"] is not None and low["forced_ba"] is not None:
            drop = round(lab["forced_ba"] - low["forced_ba"], 2)
            verdict = ("a flag (0.10 or more): it may have leaned on high-pitch content" if drop >= FLAG_GAP
                       else "a small change, as expected")
            change = f"lost {drop:.2f}" if drop >= 0 else f"gained {-drop:.2f}"
            out.append(f"From lab quality to 8 kHz, '{det}' {change}: {verdict}.")
    shape, tones = runs.get("shape|lab"), runs.get("tones|lab")
    if shape and tones and shape["forced_ba"] is not None and tones["forced_ba"] is not None:
        gap = shape["forced_ba"] - tones["forced_ba"]
        verdict = ("a flag (0.10 or more): it may be hearing more than the bearing" if gap >= FLAG_GAP
                   else "below the 0.10 flag")
        out.append(f"At lab quality, 'shape' scores {gap:+.2f} against 'tones' (bearing pitches only): {verdict}.")
    return out


def page_round2(r2, summary=None, checks=None):
    st.subheader("Round 2: listening for what damage makes")
    st.write("Round 1 above was sealed first. Round 2 was designed after seeing it, to cancel each bearing's own "
             "fingerprint: it listens for bearing pitches that stick out of the noise next to them, and for clicks. "
             "To stay fair, the choice among six combinations was made on training bearings only; the test "
             "bearings judged that choice once.")
    lab = r2["runs"].get("lab")
    if lab:
        sel = lab["selected"]
        st.write(f"Round 2 honest score at lab quality: {fmt(sel['forced_ba'])}, 95% range over bearings "
                 f"{fmt(sel['ci'][0])} to {fmt(sel['ci'][1])}. False alarms on healthy recordings: "
                 f"{fmt(sel['false_alarm'])}. Missed damaged recordings: {fmt(sel['miss'])}.")
        baselines = {k.split("|")[0]: r for k, r in (summary or {}).get("runs", {}).items()
                     if k.endswith("|lab") and k.split("|")[0] in ("loudness", "setting_only", "always_damaged")}
        if baselines:
            name, best = max(baselines.items(), key=lambda kv: kv[1]["forced_ba"] or 0)
            if sel["ci"][0] is not None and sel["ci"][0] > best["forced_ba"]:
                verdict = "its whole 95% range is above it: round 2 beats the simple baselines (SC-2)."
            else:
                verdict = "its 95% range includes that score, so round 2 does not clearly beat the simple baselines."
            st.write(f"Against the best simple baseline ({name}, {fmt(best['forced_ba'])}), {verdict}")
        if checks and checks.get("seen_ba") is not None:
            st.write(f"The inflated score of the same method, on bearings it had seen (recordings split at random, as in "
                     f"round 1; computed after round 2): {fmt(checks['seen_ba'])}, against {fmt(sel['forced_ba'])} "
                     "honest.")
        chosen = sorted(set(lab["chosen_per_fold"].values()))
        st.write(f"Combination chosen inside the training bearings: {', '.join(chosen)}.")
        st.dataframe(pd.DataFrame([{"Combination": n, "Honest score (lab)": fmt(r["forced_ba"])}
                                   for n, r in lab["candidates"].items()]), hide_index=True)
    if lab:
        st.write("Round 2 per operating condition and per bearing (lab quality):")
        st.dataframe(pd.DataFrame([{"Condition": c, "Honest score": fmt(v)}
                                   for c, v in lab["selected"]["per_condition"].items()]), hide_index=True)
        st.dataframe(pd.DataFrame(lab["selected"]["per_bearing"]), hide_index=True, height=200)
    if checks and checks.get("load_shift"):
        control = checks.get("same_condition_control", {})
        rows = [{"Train -> test": k, "Honest score": fmt(v[0]),
                 "Same single load (control)": fmt(control.get(f"{k.split('->')[1]}->{k.split('->')[1]}", [None])[0])}
                for k, v in checks["load_shift"].items()]
        st.write("Round 2 when the load changes (trained at one load, tested at the other; computed after round 2). "
                 "The control trains and tests at one single load, so it uses the same amount of training data:")
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        drops = [control[f"{k.split('->')[1]}->{k.split('->')[1]}"][0] - v[0] for k, v in checks["load_shift"].items()
                 if f"{k.split('->')[1]}->{k.split('->')[1]}" in control]
        if drops and min(drops) >= FLAG_GAP:
            st.write("Trained at one load and tested at another, round 2 falls to about chance, while trained and "
                     "tested at the same single load it keeps its score. So what it learned does not carry over to a "
                     "new load: a drive would need examples at every load it runs at.")
    st.dataframe(pd.DataFrame([{"Quality": q, "Round 2 honest score": fmt(r["selected"]["forced_ba"]),
                                "95% range": f"{fmt(r['selected']['ci'][0])} to {fmt(r['selected']['ci'][1])}"}
                               for q, r in r2["runs"].items()]), hide_index=True)
    if r2.get("plant_switched"):
        st.write("The plant view uses round 2, because at 16 kHz / 12 bit its whole 95% range is above 0.5 "
                 "(rule sealed before round 2 ran).")
    else:
        st.write("The plant view stays on round 1: round 2's 95% range at 16 kHz / 12 bit is not entirely above "
                 "0.5 (rule sealed before round 2 ran).")
    st.caption(f"Round 2 rules fingerprint: {r2['fingerprint_round2'][:12]}")


def ranking_check(motors):
    """Share damaged among motors in the lower and upper half of damage estimates (Gap 2: calibrated on average
    is not the same as pointing the right way)."""
    ms = sorted((m for m in motors if m["p_median"] is not None), key=lambda m: m["p_median"])
    half = len(ms) // 2
    if half == 0:
        return None
    share = lambda group: sum(m["label"] for m in group) / len(group)
    return share(ms[:half]), share(ms[half:])


def page_round2_checks(c, r2):
    """Checks run AFTER round 2 to test its surprise result. Not sealed; every number from round2_checks.json."""
    st.subheader("Checks on round 2's result (exploratory: run after it, not sealed)")
    real, null = c["shape+rf_real"][0], c["null_summary"]
    st.write(f"Null test: in each test group a random bearing was called 'healthy' instead of the real one, "
             f"{null['n']} times, and the same method was rerun. It scored {fmt(null['mean'])} on average (highest "
             f"{fmt(null['max'])}); with the real labels it scored {fmt(real)}. "
             + (f"None of the {null['n']} reached {fmt(real)}" if null["share_at_or_above_real"] == 0 else
                f"{null['share_at_or_above_real']:.0%} of them reached {fmt(real)}")
             + (", but the highest came close to it, so the evidence that the real healthy bearings stand out is "
                "moderate, not strong." if real - null["max"] < FLAG_GAP else
                ": the real healthy bearings stand out from the damaged ones in a way that carries over to bearings "
                "the method never saw."))
    st.write(f"Speed and load setting alone, same forest: {fmt(c['setting_only+rf'][0])} (about 0.5, so the setting "
             "does not leak the answer).")
    gap = real - c["tones+rf"][0]
    st.write(f"Physics check (HR-15): the same forest hearing only the classic bearing pitches scores "
             f"{fmt(c['tones+rf'][0])}, so round 2 is {gap:.2f} above it"
             + (": a flag (0.10 or more), it may be hearing more than the bearing." if gap >= FLAG_GAP
                else ": below the 0.10 flag."))
    lab, low = r2["runs"].get("lab"), r2["runs"].get("8k_12b")
    if lab and low:
        drop = round(lab["selected"]["forced_ba"] - low["selected"]["forced_ba"], 2)
        st.write(f"From lab quality to 8 kHz, round 2 lost {drop:.2f}"
                 + (": a flag (0.10 or more)." if drop >= FLAG_GAP else ": a small change."))
    st.write(f"Where it listens (same forest, one pitch range at a time): up to 1 kHz {fmt(c['low_bands_1k+rf'][0])}; "
             f"1 to 4.5 kHz {fmt(c['mid_bands_1k_4.5k+rf'][0])}; above 4.5 kHz {fmt(c['high_bands_4.5k+rf'][0])}; one "
             f"overall loudness number {fmt(c['loudness+rf'][0])}."
             + (" The difference sits in the broad noise above 1 kHz, not at the bearing pitches."
                if min(c["mid_bands_1k_4.5k+rf"][0], c["high_bands_4.5k+rf"][0]) - c["low_bands_1k+rf"][0] >= FLAG_GAP
                else ""))
    runin = ", ".join(f"{b} {h} h: {c['runin_flagged'][b]:.0%}" for b, h in c["runin_hours"].items())
    hours = {b: float(h.lstrip(">")) for b, h in c["runin_hours"].items()}
    same = min(hours, key=hours.get) == max(c["runin_flagged"], key=c["runin_flagged"].get)
    st.write(f"Run-in time before the test (Lessmeier 2016, Table 7) against the share of each healthy bearing's "
             f"recordings round 2 flags as damaged: {runin}."
             + (" The healthy bearing with the shortest run-in is the one flagged most, so the forest may partly hear "
                "how long a bearing was run in, not damage." if same else "")
             + " Six healthy bearings cannot settle this.")


def page_questions(rows):
    """FR-018: fixed questions written before testing, 3 of which the assistant must decline."""
    st.subheader("The AMD assistant's question test (FR-018)")
    n = len(rows)
    auto = sum(r["auto_ok"] for r in rows)
    decline = [r for r in rows if r["must_decline"]]
    declined = sum("don't know" in r["answer"].lower().replace("’", "'") for r in decline)
    claude = [r for r in rows if r.get("claude_ok") is not None]
    human = [r for r in rows if r.get("human_ok") is not None]
    sources = sorted({r["source"] for r in rows})
    st.write(f"{n} answers ({', '.join(sources)}): {auto} of {n} passed the automatic check; "
             f"{declined} of {len(decline)} questions it had to decline were declined. "
             + (f"{sum(r['claude_ok'] for r in claude)} of {len(claude)} were right when read by Claude. " if claude else "")
             + (f"Hamza's read: {sum(r['human_ok'] for r in human)} of {len(human)}." if human else "Hamza's read: pending."))


def page_results(summary, motors, checks=None, questions=None):
    h = summary["runs"][summary["headline_key"]]
    st.header("How good is it, honestly?")
    r2 = summary.get("round2")
    r2lab = (r2 or {}).get("runs", {}).get("lab", {}).get("selected")
    if r2lab:
        st.write(f"Two rounds. Round 1 (sealed first): {fmt(h['forced_ba'])}, 95% range {fmt(h['ci'][0])} to "
                 f"{fmt(h['ci'][1])}. Round 2: {fmt(r2lab['forced_ba'])}, 95% range {fmt(r2lab['ci'][0])} to "
                 f"{fmt(r2lab['ci'][1])}. Round 2 was designed after seeing round 1 and sealed before it ran; it chose "
                 "among six combinations using training bearings only (details below). "
                 + ("The plant view uses round 2, because its whole 95% range at 16 kHz / 12 bit is above 0.5 (rule "
                    "sealed before round 2 ran)." if r2.get("plant_switched") else "The plant view stays on round 1."))
        st.subheader("Round 1 (sealed first)")
    c1, c2 = st.columns(2)
    c1.metric("Honest score: bearings it never saw", fmt(h["forced_ba"]))
    c2.metric("Inflated score: bearings it had seen", fmt(h["seen_ba"]))
    if h["seen_ba"] is not None and h["forced_ba"] is not None and h["seen_ba"] - h["forced_ba"] >= FLAG_GAP:
        st.write("They differ because when the same bearings are in training and testing, the detector can recognise "
                 "each bearing instead of learning what damage sounds like. Only the first number tells you what "
                 "happens on a new motor.")
    else:
        st.write("The two numbers are close here, so recognising individual bearings did not add much. Only the "
                 "first number tells you what happens on a new motor.")
    st.write(f"Balanced accuracy, 95% range over bearings: {fmt(h['ci'][0])} to {fmt(h['ci'][1])}. "
             f"False alarms on healthy recordings: {fmt(h['false_alarm'])}. Missed damaged recordings: {fmt(h['miss'])}.")
    if h.get("decided_nothing"):
        st.error("With hand-off it decided nothing at this setting: that counts as a failure (SC-5).")
    else:
        st.write(f"With hand-off: it decides {fmt(h['decided_share'])} of recordings, with balanced accuracy "
                 f"{fmt(h['decided_ba'])} on those.")
    def plant_line(p, which):
        return (f"Per motor{which}, 16 kHz / 12 bit, one condition: flags {p['catch_rate']:.0%} of "
                f"{p['n_damaged']} damaged motors and {p['false_alarm_rate']:.0%} of {p['n_healthy']} healthy motors.")
    if summary.get("plant_round1"):
        st.write(plant_line(summary["plant_round1"], ", round 1"))
        st.write(plant_line(summary["plant"], ", round 2 (shown in the plant view)"))
    else:
        st.write(plant_line(summary["plant"], " (plant view)"))
    halves = ranking_check(motors)
    if halves:
        low, up = halves
        st.write(f"In the plant view, do higher estimates mean a more likely damaged bearing? Motors in the lower half of damage "
                 f"estimates: {low:.0%} damaged; upper half: {up:.0%} damaged."
                 + ("" if up > low else " So here a higher estimate does not point to damage: read the status "
                    "and its 'ask a person' zone, not the size of the percentage."))
    st.caption("This headline mixes all four operating conditions in training and testing. "
               "A claim about a new load comes only from the load test below (HR-13).")
    st.subheader("Against simple baselines (lab quality)")
    st.dataframe(pd.DataFrame([{"Detector": k.split("|")[0], "Honest score": fmt(r["forced_ba"])}
                               for k, r in summary["runs"].items() if k.endswith("|lab")]), hide_index=True)
    baselines = {k.split("|")[0]: r for k, r in summary["runs"].items()
                 if k.endswith("|lab") and k.split("|")[0] in ("loudness", "setting_only", "always_damaged")}
    if baselines and h["forced_ba"] is not None:
        name, best = max(baselines.items(), key=lambda kv: kv[1]["forced_ba"] or 0)
        det = summary["headline_key"].split("|")[0]
        if h["ci"][0] is not None and h["ci"][0] > best["forced_ba"]:
            st.write(f"Against the best simple baseline ({name}, {fmt(best['forced_ba'])}), '{det}' scores "
                     f"{fmt(h['forced_ba'])}, and its whole 95% range is above it: it beats the simple baselines.")
        elif h["ci"][1] is not None and h["ci"][1] < best["forced_ba"]:
            st.write(f"Against the best simple baseline ({name}, {fmt(best['forced_ba'])}), '{det}' scores "
                     f"{fmt(h['forced_ba'])}, and its whole 95% range is below it: it does worse than the simple "
                     "baselines (SC-2).")
        else:
            st.write(f"Against the best simple baseline ({name}, {fmt(best['forced_ba'])}), '{det}' scores "
                     f"{fmt(h['forced_ba'])}; its 95% range ({fmt(h['ci'][0])} to {fmt(h['ci'][1])}) includes that "
                     "score, so it does not clearly beat the simple baselines (SC-2).")
    for k, r in summary["runs"].items():
        if k.endswith("|lab") and r["ci"][1] is not None and r["ci"][1] < 0.5:
            st.write(f"'{k.split('|')[0]}' scored below chance: its whole 95% range ({fmt(r['ci'][0])} to "
                     f"{fmt(r['ci'][1])}) is under 0.5. On unseen bearings it leans the wrong way: it flags "
                     "healthy recordings more often than damaged ones.")
    st.subheader("Drive-like quality (simulated)")
    st.dataframe(pd.DataFrame([{"Detector": k.split("|")[0], "Quality": k.split("|")[1],
                                "Honest score": fmt(r["forced_ba"]),
                                "Clipped samples": r.get("n_clipped_samples", 0)}
                               for k, r in summary["runs"].items() if k.split("|")[0] in ("shape", "tones")]),
                 hide_index=True)
    st.caption("Written before testing (FR-017): the strongest bearing trace is below about 1 kHz, so 'tones' should "
               "lose almost nothing at lower sample rates. A big drop for 'shape' is a flag that it leaned on "
               "high-pitch content such as switching noise, not a proof. 'Shape' far above 'tones' means it may be "
               "hearing more than the classic bearing pitches (HR-15). 'Large' was fixed in advance as 0.10.")
    for line in quality_flags(summary["runs"]):
        st.write(line)
    if summary.get("load_shift"):
        st.subheader("When the load changes (trained at one load, tested at the other)")
        st.dataframe(pd.DataFrame([{"Train -> test": k, "Honest score": fmt(r["forced_ba"])}
                                   for k, r in summary["load_shift"].items()]), hide_index=True)
    st.subheader("Per operating condition (N15_M01_F10 is the low-load condition)")
    st.dataframe(pd.DataFrame([{"Condition": c, "Honest score": fmt(v)} for c, v in h["per_condition"].items()]),
                 hide_index=True)
    st.subheader("Per bearing: share of its recordings flagged")
    st.dataframe(pd.DataFrame(h["per_bearing"]), hide_index=True)
    st.subheader("How much the cut-offs move between test groups")
    st.dataframe(pd.DataFrame([{"Group": g, **t} for g, t in h["thresholds"].items()]), hide_index=True)
    if summary.get("round2"):
        page_round2(summary["round2"], summary, checks)
        if checks:
            page_round2_checks(checks, summary["round2"])
    if questions:
        page_questions(questions)
    st.write("The dataset authors' split (Lessmeier 2016, Table 8) was not run: it has only one healthy training "
             "bearing, so the line and the ask-a-person band could not be set honestly, and the authors report "
             "3-class accuracy, which is not comparable. This was decided before any result was seen.")
    st.subheader("What this cannot rule out")
    st.write("Healthy bearings differ from damaged ones in run-in time and mounting, not only damage. Shaft-wobble "
             "tones sit about 1.4 Hz from every bearing tone at 1,500 rpm and only about 0.8 Hz at 900 rpm, where a "
             "slightly wobbling shaft tone can spill 1 to 5% of its power into the bearing-tone window. The detector "
             "may partly learn these. Only six healthy bearings exist, so these results are exploratory.")
    st.caption(f"Every run is listed above, not only the best. Pre-registration fingerprint: {summary['prereg_fingerprint'][:12]}")


def page_value(summary):
    p = summary["plant"]
    st.header("Business value: an illustrative example")
    st.warning("Illustrative, not a measured saving. The catch and false-alarm rates are measured on lab bearings; "
               "everything else is an assumption you can change.")
    n = st.slider("Motors run by drives (assumption)", 10, 500, 100)
    fault = st.slider("Share with a bearing fault each year (assumption)", 0.01, 0.20, 0.05)
    breakdown = st.number_input("Cost of one surprise breakdown, USD (assumption)", 1_000, 1_000_000, 20_000)
    check = st.number_input("Cost of one check visit, USD (assumption)", 10, 5_000, 150)
    rounds = st.slider("Screening rounds per year (assumption)", 1, 12, 4)
    v = business.illustrative_value(n, fault, p["catch_rate"], p["false_alarm_rate"], p["handoff_healthy"],
                                    breakdown, check, rounds)
    source = " (plant view, round 2)" if summary.get("plant_round1") else ""
    if summary.get("plant_round1"):
        st.warning("These rates come from round 2, which held up only at loads it was trained on: trained at one "
                   "load and tested at another, it fell to about chance (Results page). A plant would need examples "
                   "at every load its motors run at.")
    st.write(f"Measured on lab motors{source}: catches {p['catch_rate']:.0%} of damaged motors; flags {p['false_alarm_rate']:.0%} "
             f"of healthy motors and hands off {p['handoff_healthy']:.0%} of them (only {p['n_healthy']} healthy motors).")
    st.metric("Illustrative net value per year (USD)", f"{v['net']:,.0f}")
    st.write(f"Breakdowns avoided: {v['caught']:.1f}. Check visits to healthy motors: {v['wasted_visits']:.0f}.")
    st.write(f"**For comparison, a person checks every motor every round:** breakdowns avoided "
             f"{v['visit_all_caught']:.1f}, check visits to healthy motors {v['visit_all_wasted_visits']:.0f}, "
             f"illustrative net value {v['visit_all_net']:,.0f} USD per year (assumes a manual check finds every fault).")
    if v["visit_all_net"] >= v["net"]:
        st.write(f"At the rates measured here, checking every motor is worth more than following the detector: "
                 f"the detector still sends a person to {p['false_alarm_rate'] + p['handoff_healthy']:.0%} of healthy "
                 f"motors and catches only {p['catch_rate']:.0%} of damaged ones. It would pay off only with far "
                 "fewer false alarms than it has on unseen bearings.")
    st.caption("Assumes every caught fault would otherwise have become a surprise breakdown, and ignores damaged "
               "motors that were handed to a person (they would get a manual check too).")


def page_about(summary):
    st.header("About")
    st.write("**What runs on AMD:** the assistant that turns each verdict into a technician's note, answers "
             "follow-up questions and drafts work orders runs on an open model (Gemma, with Qwen as backup) served "
             "on AMD GPUs through AMD Token Factory. The detector itself is a small model that runs anywhere.")
    st.write("**Data:** Paderborn University bearing data (Lessmeier et al., PHME 2016), CC BY-NC 4.0. The tested "
             "bearing sits in a separate module on the shaft line, outside the motor. The current was measured by "
             "lab sensors between drive and motor; drive-like quality is simulated. Results shown here are derived "
             "from that data and shared under the same licence.")
    st.write("**Not claimed:** days until failure, results for bearings inside a motor, or any drive brand's sensor.")


def main():
    st.set_page_config(page_title="Bearing Whisperer", page_icon="⚙️", layout="wide")
    st.info(BANNER)
    motors, summary = load_results(str(RESULTS), results_version(RESULTS))
    page = st.sidebar.radio("Page", PAGES, key="page")
    if page == "Plant":
        page_plant(motors, summary)
    elif page == "Motor":
        page_motor(motors, summary)
    elif page == "Results":
        checks_file = RESULTS / "round2_checks.json"
        checks = json.loads(checks_file.read_text(encoding="utf-8")) if checks_file.exists() else None
        q_file = RESULTS / "assistant_questions.json"
        questions = json.loads(q_file.read_text(encoding="utf-8")) if q_file.exists() else None
        page_results(summary, motors, checks, questions)
    elif page == "Business value":
        page_value(summary)
    else:
        page_about(summary)


main()
