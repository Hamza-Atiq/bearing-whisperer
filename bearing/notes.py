"""Technician notes. Every fact comes from the detector (FR-006); action means confirm first (FR-007)."""
import re

MAX_WORDS = 80
CONFIRM = "confirm with a vibration or ultrasound check before replacing anything"
JARGON = ["bpfo", "bpfi", "fft", "spectrum", "sideband", "harmonic", "logistic", "pmsm", "balanced accuracy",
          "classifier", "probability", "fold"]
FORBIDDEN = ["days", "hours until", "will fail", "certain", "guarantee", "definitely", "%"]

NEXT_STEP = {
    "check bearing": f"Check this bearing and {CONFIRM}.",
    "ask a person": f"Have a person look at this motor and {CONFIRM}.",
    "healthy": "No action needed now. Keep it on the normal check schedule.",
}


def facts_for(motor: dict) -> dict:
    return {
        "motor": motor["motor_name"],
        "status": motor["plant_word"],
        "how_sure": motor["how_sure"],
        "evidence": list(motor.get("evidence", [])),
        "next_step": NEXT_STEP[motor["plant_word"]],
        "urgency": motor.get("urgency") or "none",
        "data_note": "This is recorded lab data, not a live plant.",
    }


def template_note(facts: dict) -> str:
    evidence = "; ".join(facts["evidence"]) or "no single clear sign"
    when = "" if facts["urgency"] == "none" else f" When: {facts['urgency']}."
    return (f"{facts['motor']}: {facts['status']} (how sure: {facts['how_sure']}). "
            f"What the current showed: {evidence}. {facts['next_step']}{when} {facts['data_note']}")


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


EVIDENCE_WORDS = ("buzz", "trace", "peak", "clicks")   # the plain words evidence lines use (evaluate._phrase, round2.phrase)
STATUS_WORDS = ("check bearing", "ask a person", "healthy")


def _names_motor(text: str, motor: str) -> bool:
    """'Motor 07' may also be written 'Motor 7'."""
    name, _, number = motor.rpartition(" ")
    if not number.isdigit():
        return motor.lower() in text.lower()
    return re.search(rf"\b{re.escape(name)}\s+0*{int(number)}\b", text, re.IGNORECASE) is not None


def validate_note(text: str, facts: dict) -> list[str]:
    problems = []
    low = text.lower()
    if len(text.split()) > MAX_WORDS:
        problems.append(f"too long: {len(text.split())} words (max {MAX_WORDS})")
    if not _names_motor(text, facts["motor"]):
        problems.append("does not name the motor")
    if facts["status"] not in low:
        problems.append(f"does not state the status '{facts['status']}'")
    for other in STATUS_WORDS:
        if other != facts["status"] and other in low:
            problems.append(f"contradicts the status: says '{other}'")
    if not re.search(rf"\b{facts['how_sure']}\b", low):
        problems.append("does not say how sure")
    if facts["status"] != "healthy" and "vibration or ultrasound" not in low:
        problems.append("does not say to confirm with a vibration or ultrasound check")
    if facts.get("urgency", "none") != "none" and facts["urgency"].split(",")[0].lower() not in low:
        problems.append(f"does not say the urgency '{facts['urgency']}'")
    needed = [w for w in EVIDENCE_WORDS if any(w in e for e in facts["evidence"])]
    if needed and not any(w in low for w in needed):
        problems.append(f"does not mention the evidence ({' or '.join(needed)})")
    allowed = _numbers(" ".join([facts["motor"], *facts["evidence"]]))
    invented = _numbers(text) - allowed
    if invented:
        problems.append(f"numbers not in the detector facts: {sorted(invented)}")
    for w in JARGON:
        if re.search(rf"\b{re.escape(w)}\b", low):
            problems.append(f"jargon: {w}")
    for w in FORBIDDEN:
        if (w in low) if not w[0].isalpha() else re.search(rf"\b{re.escape(w)}\b", low):
            problems.append(f"claim the detector cannot make: '{w}'")
    return problems


def work_order(facts: dict, motor: dict) -> dict:
    """FR-008: a draft only. A person approves it before it is used."""
    return {"motor": facts["motor"], "problem": f"Detector says: {facts['status']}",
            "urgency": motor.get("urgency") or "none",
            "suggested_check": "Vibration or ultrasound check of the bearing on the shaft line",
            "how_sure": facts["how_sure"], "status": "DRAFT, needs a person's approval"}
