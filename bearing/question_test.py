"""FR-018: fixed technician questions written before testing, including 3 the assistant must decline."""
import json
import time
from pathlib import Path

from . import assistant, notes, round2

QUESTIONS = Path("tests/assistant_questions.json")


def auto_check(text: str, must_decline: bool) -> bool:
    low = text.lower().replace("’", "'")
    if must_decline:
        return "don't know" in low
    return "days" not in low and "%" not in low


def run(results=Path("results")) -> list[dict]:
    motors = json.loads((results / "motors.json").read_text(encoding="utf-8"))
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    line = f"honest balanced accuracy on unseen bearings {round2.plant_run(summary)['forced_ba']}"
    picked = [m for word in ("check bearing", "ask a person", "healthy")
              for m in [next((x for x in motors if x["plant_word"] == word), None)] if m]
    key = assistant.load_key()
    rows = []
    for m in picked:
        facts = notes.facts_for(m)
        for item in json.loads(QUESTIONS.read_text(encoding="utf-8")):
            r = assistant.answer(item["q"], facts, line, key)
            rows.append({"motor": m["motor_name"], "question": item["q"], "must_decline": item["must_decline"],
                         "answer": r.text, "source": r.source, "auto_ok": auto_check(r.text, item["must_decline"]),
                         "human_ok": None})
            time.sleep(4)                                  # stay under 20 requests a minute
    (results / "assistant_questions.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


if __name__ == "__main__":
    run()
