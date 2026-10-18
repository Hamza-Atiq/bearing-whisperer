"""The AMD copilot: plan a shift with tools (FR-021) and explain a motor's picture (FR-022).

Both run on open models served on AMD GPUs through AMD Token Factory. The model only sees what the product's tools
return, and every answer is checked before it is shown: a plan may only name motors, statuses and numbers the tools
gave it; an explanation may only use numbers from the facts. If a check fails or the service is down, a fixed rule
answers instead and says so.
"""
import json
import re
import time

import requests

from . import assistant, notes

MAX_STEPS = 5
EXPLAIN_BUDGET_S = 45          # all model tries together; the web host stops a request at 60 s
PLAN_BUDGET_S = 45             # same limit for the shift plan's tool loop
STATUS_RANK = {"check bearing": 0, "ask a person": 1, "healthy": 2}
SURE_RANK = {"high": 0, "medium": 1, "low": 2}

PLAN_SYSTEM = (
    "You plan a maintenance technician's shift in a factory. You must call the tools to learn about the motors; never "
    "guess. Be quick: call get_fleet once, then get_motors once with every motor you might visit. Visit motors marked 'check bearing' first (most sure first), then 'ask a person'. Never plan a visit to a "
    "'healthy' motor unless the technician asks. Fit the visits into the time given, using the minutes per check "
    "given. Skip motors the technician asks to skip. When done, reply with ONLY a JSON object: "
    '{"visits": [{"motor": "Motor 07", "reason": "<one short plain sentence using only words and numbers from the '
    'tool results>"}], "summary": "<one or two plain sentences>"}. No days or hours until failure, no percentages.')

EXPLAIN_SYSTEM = (
    "You explain a chart to a new maintenance trainee who is not an engineer. The chart shows how loud a motor's "
    "electric current is at each pitch (left = low pitch, right = high pitch). Use ONLY what you see and the facts "
    "given; never add numbers that are not in the facts. Plain English, 4 or 5 short sentences, at most 110 words. "
    "Say what the blue line is and what the grey band is. Say where the blue line is outside the grey band ONLY at the "
    "places listed under 'outside the healthy band' (if none are listed, say it stays close to the grey band). The "
    "detector's evidence compares this motor with the average motor in training, which is not the grey band; if you "
    "mention the evidence, say that. Then give "
    "the detector's verdict in this exact form: 'The detector says: <status>, how sure: <how_sure>.' using the exact "
    "words in the facts. End with: 'This is recorded lab data, not a live plant.'")

TOOLS = [
    {"type": "function", "function": {
        "name": "get_fleet", "description": "List every motor with its status and how sure the detector is.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["any", "check bearing", "ask a person", "healthy"]}}}}},
    {"type": "function", "function": {
        "name": "get_motors", "description": "The detector's facts for several motors at once (preferred).",
        "parameters": {"type": "object", "properties": {"motors": {"type": "array", "items": {"type": "string"}}},
                       "required": ["motors"]}}},
    {"type": "function", "function": {
        "name": "get_motor", "description": "The detector's facts for one motor: status, how sure, evidence, urgency.",
        "parameters": {"type": "object", "properties": {"motor": {"type": "string"}}, "required": ["motor"]}}},
    {"type": "function", "function": {
        "name": "get_track_record", "description": "How well the detector did on bearings it never saw.",
        "parameters": {"type": "object", "properties": {}}}},
]


class Tools:
    def __init__(self, motors: list[dict], track_record: str):
        self.by_name = {m["motor_name"]: m for m in motors}
        self.track_record = track_record
        self.calls: list[dict] = []
        self.seen_text: list[str] = []

    def run(self, name: str, args: dict) -> dict:
        if name == "get_fleet":
            want = args.get("status", "any")
            out = [{"motor": m["motor_name"], "status": m["plant_word"], "how_sure": m["how_sure"]}
                   for m in self.by_name.values() if want in ("any", None) or m["plant_word"] == want]
            result = {"motors": out}
        elif name == "get_motor":
            m = self.by_name.get(_motor_name(args.get("motor", "")))
            result = notes.facts_for(m) if m else {"error": "no such motor"}
        elif name == "get_motors":
            out = {}
            for raw in list(args.get("motors", []))[:32]:
                m = self.by_name.get(_motor_name(str(raw)))
                out[_motor_name(str(raw))] = notes.facts_for(m) if m else {"error": "no such motor"}
            result = {"motors": out}
        elif name == "get_track_record":
            result = {"track_record": self.track_record}
        else:
            result = {"error": f"unknown tool {name}"}
        self.calls.append({"tool": name, "args": args, "result_size": len(json.dumps(result))})
        self.seen_text.append(json.dumps(result))
        return result


def _motor_name(text: str) -> str:
    m = re.search(r"(\d+)", text or "")
    return f"Motor {int(m.group(1)):02d}" if m else (text or "")


def _call(model, messages, key, post, tools=None, max_tokens=900, timeout=None):
    body = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if tools:
        body["tools"] = tools
    if model.startswith("Qwen"):
        body["reasoning_effort"] = "low"
        body["max_tokens"] = max(max_tokens, 2000)
    r = post(f"{assistant.BASE_URL}/chat/completions", json=body, timeout=timeout or assistant.TIMEOUT_S,
             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()["choices"][0]["message"]


def _json_from(text: str):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        raise ValueError("no JSON in the answer")
    return json.loads(m.group(0))


def rule_plan(motors: list[dict], minutes: int, per_check: int, skip=()) -> list[dict]:
    """The fixed fallback: check-bearing first, most sure first, then ask-a-person, until time runs out."""
    skip = {_motor_name(s) for s in skip}
    todo = sorted((m for m in motors if m["plant_word"] != "healthy" and m["motor_name"] not in skip),
                  key=lambda m: (STATUS_RANK[m["plant_word"]], SURE_RANK[m["how_sure"]], -(m["p_median"] or 0)))
    n = max(0, minutes // max(per_check, 1))
    return [{"motor": m["motor_name"], "reason": f"{m['plant_word']}, how sure: {m['how_sure']}"} for m in todo[:n]]


def check_plan(plan: dict, motors: list[dict], seen_text: str, minutes: int, per_check: int, skip=()) -> list[str]:
    problems = []
    by_name = {m["motor_name"]: m for m in motors}
    visits = plan.get("visits")
    if not isinstance(visits, list):
        return ["no list of visits"]
    if len(visits) > max(0, minutes // max(per_check, 1)):
        problems.append("more visits than the time allows")
    names = [_motor_name(v.get("motor", "")) for v in visits]
    if len(set(names)) != len(names):
        problems.append("a motor is listed twice")
    skip = {_motor_name(s) for s in skip}
    allowed_numbers = notes._numbers(seen_text) | {float(minutes), float(per_check)}
    for v, name in zip(visits, names):
        m = by_name.get(name)
        if m is None:
            problems.append(f"unknown motor {v.get('motor')}")
            continue
        if name not in seen_text:
            problems.append(f"{name} was never returned by a tool")
        if name in skip:
            problems.append(f"{name} was asked to be skipped")
        if m["plant_word"] == "healthy":
            problems.append(f"{name} is healthy")
        reason = str(v.get("reason", "")).lower()
        for word in notes.STATUS_WORDS:
            if word in reason and word != m["plant_word"]:
                problems.append(f"{name}: reason says '{word}' but the status is '{m['plant_word']}'")
        invented = notes._numbers(reason) - allowed_numbers
        if invented:
            problems.append(f"{name}: numbers not from the tools {sorted(invented)}")
    summary_numbers = notes._numbers(str(plan.get("summary", "")))
    invented = summary_numbers - allowed_numbers - {float(len(visits)), float(len(visits) * per_check)}
    if invented:
        problems.append(f"summary: numbers not from the tools {sorted(invented)}")
    text = " ".join([str(plan.get("summary", ""))] + [str(v.get("reason", "")) for v in visits]).lower()
    for w in notes.FORBIDDEN:
        if (w in text) if not w[0].isalpha() else re.search(rf"\b{re.escape(w)}\b", text):
            problems.append(f"claim the detector cannot make: '{w}'")
    ranks = [(STATUS_RANK[by_name[n]["plant_word"]]) for n in names if n in by_name]
    if ranks != sorted(ranks):
        problems.append("an 'ask a person' motor comes before a 'check bearing' motor")
    return problems


def plan_shift(motors, track_record, minutes, per_check, request, key, skip=(), post=requests.post) -> dict:
    tools = Tools(motors, track_record)
    problems, steps = [], []
    if key:
        deadline = time.monotonic() + PLAN_BUDGET_S
        for model in assistant.MODELS:
            if deadline - time.monotonic() < 5:
                problems.append(f"{model}: skipped, out of time")
                continue
            tools.calls, tools.seen_text = [], []
            messages = [{"role": "system", "content": PLAN_SYSTEM},
                        {"role": "user", "content": f"I have {minutes} minutes. One check takes about {per_check} "
                                                    f"minutes. Skip: {', '.join(skip) or 'none'}. {request}".strip()}]
            try:
                for _ in range(MAX_STEPS):
                    left = deadline - time.monotonic()
                    if left < 5:
                        raise TimeoutError("out of time")
                    msg = _call(model, messages, key, post, TOOLS, timeout=left)
                    calls = msg.get("tool_calls") or []
                    if not calls:
                        plan = _json_from(msg.get("content", ""))
                        found = check_plan(plan, motors, " ".join(tools.seen_text), minutes, per_check, skip)
                        if found:
                            raise ValueError("; ".join(found))
                        return _finish(plan["visits"], plan.get("summary", ""), model, tools.calls, problems, motors)
                    messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
                    for c in calls:
                        args = json.loads(c["function"].get("arguments") or "{}")
                        result = tools.run(c["function"]["name"], args)
                        messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)})
                raise ValueError("too many steps")
            except Exception as exc:
                problems.append(f"{model}: {type(exc).__name__}: {str(exc)[:200]}")
                steps = tools.calls
    visits = rule_plan(motors, minutes, per_check, skip)
    summary = (f"{len(visits)} visits fit into {minutes} minutes at {per_check} minutes each: check-bearing motors "
               "first, most sure first, then ask-a-person motors.")
    return _finish(visits, summary, "rule", steps, problems, motors)


def _finish(visits, summary, source, steps, problems, motors):
    by_name = {m["motor_name"]: m for m in motors}
    out = []
    for v in visits:
        m = by_name[_motor_name(v["motor"])]
        facts = notes.facts_for(m)
        out.append({"motor": m["motor_name"], "status": m["plant_word"], "how_sure": m["how_sure"],
                    "reason": v.get("reason", ""), "work_order": notes.work_order(facts, m)})
    return {"visits": out, "summary": summary, "source": source, "steps": steps, "problems": problems}


def explain_chart(image_data_url: str, facts: dict, chart_facts: dict, key, post=requests.post) -> dict:
    """FR-022: a vision model reads the picture plus the facts; numbers it uses must come from the facts."""
    allowed = notes._numbers(json.dumps(facts) + json.dumps(chart_facts))
    problems = []
    if key and image_data_url.startswith("data:image/png;base64,"):
        text_facts = f"Detector facts:\n{assistant._facts_text(facts)}\nChart facts:\n{assistant._facts_text(chart_facts)}"
        deadline = time.monotonic() + EXPLAIN_BUDGET_S
        for model in assistant.MODELS:
            left = deadline - time.monotonic()
            if left < 5:
                problems.append(f"{model}: skipped, out of time")
                continue
            try:
                msg = _call(model, [{"role": "system", "content": EXPLAIN_SYSTEM},
                                    {"role": "user", "content": [
                                        {"type": "text", "text": text_facts},
                                        {"type": "image_url", "image_url": {"url": image_data_url}}]}],
                            key, post, max_tokens=400, timeout=left)
                text = (msg.get("content") or "").strip()
                found = check_explanation(text, facts, allowed)
                if not found:
                    return {"text": text, "source": model, "problems": problems}
                problems.append(f"{model}: {'; '.join(found)}")
            except Exception as exc:
                problems.append(f"{model}: {type(exc).__name__}")
    return {"text": template_explanation(facts, chart_facts), "source": "template", "problems": problems}


def check_explanation(text: str, facts: dict, allowed: set) -> list[str]:
    problems = []
    low = text.lower()
    if not text:
        return ["empty"]
    if len(text.split()) > 130:
        problems.append("too long")
    invented = notes._numbers(text) - allowed
    if invented:
        problems.append(f"numbers not in the facts {sorted(invented)}")
    # "healthy" also names the grey reference ("the healthy lab bearings"); only a verdict word may contradict.
    verdict_text = re.sub(r"\bhealthy(?:\s+lab)?\s+(?:bearings?|range|band|motors?|reference|ones)\b", "", low)
    if facts["status"] not in low:
        problems.append(f"does not state the status '{facts['status']}'")
    for other in notes.STATUS_WORDS:
        if other != facts["status"] and other in verdict_text:
            problems.append(f"contradicts the status: says '{other}'")
    for w in notes.FORBIDDEN:
        if (w in low) if not w[0].isalpha() else re.search(rf"\b{re.escape(w)}\b", low):
            problems.append(f"claim the detector cannot make: '{w}'")
    return problems


ANSWER_FORBIDDEN = ("will fail", "guarantee", "definitely", "certain")
DECLINE = "I don't know that from this data."


def check_answer(text: str, facts: dict, results_line: str) -> list[str]:
    """Follow-up answers (FR-015): numbers only from the facts or the results line, no contradicting verdict."""
    low = (text or "").lower()
    if not low:
        return ["empty"]
    problems = []
    invented = notes._numbers(text) - notes._numbers(json.dumps(facts) + " " + results_line) - {95.0}
    if invented:
        problems.append(f"numbers not in the facts {sorted(invented)}")
    verdict_text = re.sub(r"\bhealthy(?:\s+lab)?\s+(?:bearings?|range|band|motors?|reference|ones)\b", "", low)
    for other in notes.STATUS_WORDS:
        if other != facts["status"] and other in verdict_text:
            problems.append(f"contradicts the status: says '{other}'")
    for w in ANSWER_FORBIDDEN:
        if re.search(rf"\b{re.escape(w)}\b", low):
            problems.append(f"claim the detector cannot make: '{w}'")
    return problems


def checked_answer(question: str, facts: dict, results_line: str, key, post=requests.post) -> dict:
    r = assistant.answer(question, facts, results_line, key, post)
    if r.source == "template":
        return {"text": r.text, "source": "template", "problems": []}
    found = check_answer(r.text, facts, results_line)
    if found:
        return {"text": DECLINE, "source": "template", "problems": [f"{r.source}: {'; '.join(found)}"]}
    return {"text": r.text, "source": r.source, "problems": []}


def template_explanation(facts: dict, chart_facts: dict) -> str:
    ev = "; ".join(facts["evidence"]) or "no single clear sign"
    return ("The blue line shows how loud this motor's current is at each pitch, from low pitch on the left to high "
            "pitch on the right. The grey band shows where the healthy lab bearings sit. Where the blue line leaves "
            f"the grey band, this motor sounds different. The detector's main signs: {ev}. Its verdict: "
            f"{facts['status']} (how sure: {facts['how_sure']}). This is recorded lab data, not a live plant.")
