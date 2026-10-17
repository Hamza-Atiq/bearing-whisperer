import json

from bearing import copilot


def motor(n, word, sure, p=0.9):
    return {"motor_name": f"Motor {n:02d}", "plant_word": word, "how_sure": sure, "p_median": p,
            "evidence": ["more electrical buzz between 1,041 and 1,330 Hz than the average motor in training"],
            "urgency": "this week" if word == "check bearing" else None}


MOTORS = [motor(1, "check bearing", "high"), motor(2, "ask a person", "low", 0.6), motor(3, "healthy", "high", 0.1),
          motor(4, "check bearing", "medium", 0.8)]


class Reply:
    def __init__(self, message, status=200):
        self.status_code = status
        self._m = message

    def json(self):
        return {"choices": [{"message": self._m}]}


def scripted(*messages):
    seq = list(messages)
    sent = []

    def post(url, json=None, **kw):
        sent.append(json)
        return Reply(seq.pop(0))
    post.sent = sent
    return post


def tool_call(name, args, i="c1"):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": i, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def test_rule_plan_orders_and_fits_time():
    plan = copilot.rule_plan(MOTORS, minutes=60, per_check=20)
    assert [v["motor"] for v in plan] == ["Motor 01", "Motor 04", "Motor 02"]
    assert len(copilot.rule_plan(MOTORS, minutes=40, per_check=20)) == 2
    assert [v["motor"] for v in copilot.rule_plan(MOTORS, 60, 20, skip=["motor 1"])] == ["Motor 04", "Motor 02"]


def test_plan_uses_tools_and_passes_the_check():
    final = {"role": "assistant", "content": json.dumps({
        "visits": [{"motor": "Motor 01", "reason": "check bearing, how sure: high"},
                   {"motor": "Motor 04", "reason": "check bearing, how sure: medium"}],
        "summary": "Two visits."})}
    post = scripted(tool_call("get_fleet", {"status": "any"}), final)
    out = copilot.plan_shift(MOTORS, "0.80", 40, 20, "", "k", post=post)
    assert out["source"] == "Gemma-4-31B-IT"
    assert [s["tool"] for s in out["steps"]] == ["get_fleet"]
    assert out["visits"][0]["work_order"]["status"].startswith("DRAFT")
    assert post.sent[1]["messages"][-1]["role"] == "tool"


def test_plan_with_an_invented_fact_falls_back_to_the_rule():
    bad = {"role": "assistant", "content": json.dumps({
        "visits": [{"motor": "Motor 03", "reason": "healthy but 95% likely to fail in 3 days"}], "summary": "x"})}
    post = scripted(tool_call("get_fleet", {}), bad, tool_call("get_fleet", {}), bad)
    out = copilot.plan_shift(MOTORS, "0.80", 40, 20, "", "k", post=post)
    assert out["source"] == "rule"
    assert len(out["problems"]) == 2
    assert [v["motor"] for v in out["visits"]] == ["Motor 01", "Motor 04"]


def test_plan_check_catches_each_kind_of_error():
    seen = json.dumps({"motors": [{"motor": m["motor_name"]} for m in MOTORS]})
    p = lambda visits: copilot.check_plan({"visits": visits, "summary": ""}, MOTORS, seen, 40, 20)
    assert p([{"motor": "Motor 09", "reason": ""}])
    assert any("healthy" in x for x in p([{"motor": "Motor 03", "reason": ""}]))
    assert any("before" in x for x in p([{"motor": "Motor 02", "reason": ""}, {"motor": "Motor 01", "reason": ""}]))
    assert any("time" in x for x in p([{"motor": f"Motor 0{i}", "reason": ""} for i in (1, 4, 2)]))
    assert any("numbers" in x for x in p([{"motor": "Motor 01", "reason": "buzz at 7,000 Hz"}]))
    assert any("numbers" in x for x in p([{"motor": "Motor 01", "reason": "more buzz between 1,041 and 1,330 Hz"}]))
    from bearing import notes                       # numbers count only once a tool has returned them
    seen_motor = seen + json.dumps(notes.facts_for(MOTORS[0]))
    assert not copilot.check_plan({"visits": [{"motor": "Motor 01", "reason": "more buzz between 1,041 and 1,330 Hz"}]},
                                  MOTORS, seen_motor, 40, 20)
    assert any("never returned" in x for x in copilot.check_plan(
        {"visits": [{"motor": "Motor 01", "reason": ""}]}, MOTORS, "", 40, 20))


def test_no_key_means_rule_plan():
    out = copilot.plan_shift(MOTORS, "0.80", 20, 20, "", None)
    assert out["source"] == "rule" and len(out["visits"]) == 1


def test_explanation_is_checked_and_falls_back():
    from bearing import notes
    facts = notes.facts_for(MOTORS[0])
    good = {"role": "assistant", "content": "The blue line is this motor. It rises above the grey band between "
                                            "1,041 and 1,330 Hz. The detector says check bearing, how sure: high. "
                                            "This is recorded lab data, not a live plant."}
    out = copilot.explain_chart("data:image/png;base64,AAA", facts, {"x": "pitch"}, "k", post=scripted(good))
    assert out["source"] == "Gemma-4-31B-IT"
    bad = {"role": "assistant", "content": "It is healthy and will fail in 4 days."}
    out = copilot.explain_chart("data:image/png;base64,AAA", facts, {}, "k", post=scripted(bad))
    assert out["source"] == "template" and "check bearing" in out["text"]


def test_plan_summary_numbers_must_come_from_tools_or_simple_sums():
    seen = json.dumps({"motors": [{"motor": m["motor_name"]} for m in MOTORS]})
    visits = [{"motor": "Motor 01", "reason": ""}, {"motor": "Motor 04", "reason": ""}]
    ok = copilot.check_plan({"visits": visits, "summary": "2 visits, 40 minutes."}, MOTORS, seen, 40, 20)
    bad = copilot.check_plan({"visits": visits, "summary": "Saves 12000 USD."}, MOTORS, seen, 40, 20)
    assert not ok and any("summary" in x for x in bad)


def test_explanation_may_name_the_healthy_reference_but_not_call_the_motor_healthy():
    from bearing import notes
    facts = notes.facts_for(MOTORS[0])
    ok = ("The grey band shows the healthy lab bearings. The blue line rises above it. Status: check bearing, how sure: "
          "high. This is recorded lab data, not a live plant.")
    assert not copilot.check_explanation(ok, facts, set())
    bad = "The motor looks healthy. This is recorded lab data, not a live plant."
    found = copilot.check_explanation(bad, facts, set())
    assert any("contradicts" in p for p in found) and any("does not state" in p for p in found)


def test_answers_are_checked_before_they_are_shown():
    from bearing import notes
    facts = notes.facts_for(MOTORS[0])
    good = {"role": "assistant", "content": "Because there is more electrical buzz between 1,041 and 1,330 Hz."}
    out = copilot.checked_answer("why?", facts, "score 0.80", "k", post=scripted(good))
    assert out["source"] == "Gemma-4-31B-IT"
    bad = {"role": "assistant", "content": "It will fail within 12 days."}
    out = copilot.checked_answer("when?", facts, "score 0.80", "k", post=scripted(bad))
    assert out["source"] == "template" and out["text"] == copilot.DECLINE and out["problems"]


def test_get_motors_fetches_several_at_once():
    tools = copilot.Tools(MOTORS, "x")
    out = tools.run("get_motors", {"motors": ["Motor 01", "motor 4", "Motor 77"]})
    assert out["motors"]["Motor 01"]["status"] == "check bearing"
    assert out["motors"]["Motor 04"]["how_sure"] == "medium"
    assert "error" in out["motors"]["Motor 77"]
