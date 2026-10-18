"""Shared logic for the web app's server functions. The AMD key stays here, on the server (FR-013).

Facts always come from the server's own copy of the results, never from the browser, so a viewer cannot make the
assistant say something the detector did not produce (FR-006).
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _bearing import assistant, copilot, notes  # noqa: E402

APP = json.loads((HERE / "_data" / "app.json").read_text(encoding="utf-8"))
MOTORS = {m["motor_name"]: m for m in APP["motors"]}
MAX_BODY = 1_500_000            # a chart picture is about 100 KB; anything far bigger is refused


def key():
    return os.environ.get("AMD_KEY") or None


def track_record() -> str:
    p = APP["proof"]
    rnd = next(r for r in p["rounds"] if r["round"] == p["plant_round"])
    q = rnd["quality"].get(APP["motors"][0]["setting"]) or rnd["same_load"]
    return (f"round {rnd['round']}: honest balanced accuracy on unseen bearings {q['ba']:.2f} "
            f"(95% range {q['ci'][0]:.2f} to {q['ci'][1]:.2f}); it held only at loads it was trained on"
            if p["plant_round"] < 3 else
            f"round {rnd['round']}: honest balanced accuracy on unseen bearings {q['ba']:.2f} (95% range "
            f"{q['ci'][0]:.2f} to {q['ci'][1]:.2f})")


def motor_or_error(name):
    m = MOTORS.get(copilot._motor_name(str(name)))
    if m is None:
        raise ValueError("unknown motor")
    return m


def chart_facts(m, diff: bool = True) -> dict:
    h = APP["hiss"]
    return {"blue line": (f"{m['motor_name']}: how much louder (above zero) or quieter (below zero) its current is "
                          "than the middle of the healthy bearings, at each pitch, in dB" if diff else
                          f"{m['motor_name']}: how loud its current is at each pitch, {h['unit']}"),
            "grey band": "where the six healthy lab bearings sit (middle 80%)",
            "how big the differences are": "small: about 1 to 2 dB; the detector adds up many small shifts",
            "evidence note": "the detector's evidence compares with the average motor in training, not with the grey band",
            "marked pitches": f"outer-ring pitch {h['bearing_pitches']['outer ring']} Hz, inner-ring pitch "
                              f"{h['bearing_pitches']['inner ring']} Hz",
            "shaded area": "the pitches the detector leans on most, on average over all motors",
            "purple dashed columns marked 'sign 1' and 'sign 2'": "this motor's top signs: the pitches in its evidence, "
                                                                   "which pushed its verdict most",
            "pitch range shown": f"{h['edges'][0]:.0f} to {h['edges'][-1]:,.0f} Hz",
            "outside the healthy band": outside_band(m) or "none: the blue line stays inside or close to the grey band"}


def outside_band(m, top: int = 3) -> str:
    """Where this motor's line leaves the healthy grey band most (computed from app.json, so the numbers are true)."""
    h = APP["hiss"]
    v = h["per_bearing"].get(m["bearing"], [])
    gaps = []
    for i, x in enumerate(v):
        lo, hi = h["healthy_low"][i], h["healthy_high"][i]
        if x > hi or x < lo:
            gaps.append((max(x - hi, lo - x), i, "above" if x > hi else "below"))
    parts = [f"{h['edges'][i]:,.0f} to {h['edges'][i + 1]:,.0f} Hz: {side} the band by {gap:.0f} dB"
             for gap, i, side in sorted(gaps, reverse=True)[:top] if gap >= 1]
    return "; ".join(parts)


def dispatch(route: str, body: dict) -> dict:
    k = key()
    if route == "health":
        return {"assistant": bool(k), "models": list(assistant.MODELS)}
    if route == "note":
        m = motor_or_error(body.get("motor"))
        facts = notes.facts_for(m)
        r = assistant.write_note(facts, k)
        return {"text": r.text, "source": r.source, "template": notes.template_note(facts),
                "problems": r.problems}
    if route == "ask":
        m = motor_or_error(body.get("motor"))
        q = str(body.get("question", ""))[:300].strip()
        if not q:
            raise ValueError("empty question")
        return copilot.checked_answer(q, notes.facts_for(m), track_record(), k)
    if route == "plan":
        minutes = max(10, min(int(body.get("minutes", 120)), 600))
        per_check = max(5, min(int(body.get("per_check", 20)), 120))
        skip = [str(s) for s in body.get("skip", [])][:32]
        request = str(body.get("request", ""))[:300]
        return copilot.plan_shift(list(MOTORS.values()), track_record(), minutes, per_check, request, k, skip)
    if route == "explain":
        m = motor_or_error(body.get("motor"))
        image = str(body.get("image", ""))
        return copilot.explain_chart(image, notes.facts_for(m), chart_facts(m, bool(body.get("diff", True))), k)
    raise ValueError("unknown route")


def serve(handler, route: str):
    """Answer one request inside a Vercel Python function (or the local dev server)."""
    try:
        n = int(handler.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("request too large")
        body = json.loads(handler.rfile.read(n) or b"{}") if n else {}
        out, status = dispatch(route, body), 200
    except ValueError as exc:
        out, status = {"error": str(exc)}, 400
    except Exception as exc:            # never leak details or the key
        out, status = {"error": f"server error: {type(exc).__name__}"}, 500
    data = json.dumps(out).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
