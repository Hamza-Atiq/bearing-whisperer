"""Notes written by an open model on AMD Token Factory (AMD GPUs). Checked before use; template if anything fails.

The key is read from the environment, the app's secret store, or .env, and is never printed or sent anywhere else.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import notes

BASE_URL = "https://developer.amd.com.cn/radeon/api/v1"
MODELS = ("Gemma-4-31B-IT", "Qwen3.8-27B")
TIMEOUT_S = 60
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

NOTE_SYSTEM = (
    "You write short maintenance notes for a factory technician who is not an engineer. Use ONLY the facts in "
    "the user message. Do not add any number, cause, time to failure or part name that is not in the facts. "
    "Plain English, no technical jargon, 3 or 4 short sentences, at most 70 words. "
    "Sentence 1: the motor name and the status in the exact words given, for example 'Motor 07: check bearing.' "
    "Sentence 2: 'How sure: <word>.' using the exact word given. "
    "Sentence 3: what the current showed, in everyday words, keeping the words 'electrical buzz', 'trace', 'peak' or 'clicks' "
    "and any numbers exactly as written in the evidence. "
    "If the status is 'check bearing' or 'ask a person', also say when to act, using the urgency words given, "
    "and say to confirm with a vibration or ultrasound check before replacing anything. "
    "End with: 'This is recorded lab data, not a live plant.'")

ANSWER_SYSTEM = (
    "You answer a technician's question about one motor. Use ONLY the facts, the meanings and the results line "
    "given. If the answer is not in them, say: 'I don't know that from this data.' Never predict days or hours until "
    "failure. Plain English, at most 80 words.")


MEANINGS = (
    "how sure: how far the detector's estimate is from its 'ask a person' zone. high means far from it, medium means "
    "a little outside it, low means inside it. It is how confident the detector is, not how bad the damage is. "
    "check bearing: the detector says damaged. ask a person: the detector is not sure and hands the motor to a "
    "person. healthy: the detector says not damaged.")


@dataclass
class NoteResult:
    text: str
    source: str                      # model name, or "template"
    problems: list = field(default_factory=list)


def load_key() -> str | None:
    if "AMD_KEY" in os.environ:
        return os.environ["AMD_KEY"] or None
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "AMD_KEY":
                return value.strip().strip('"').strip("'") or None
    return None


def _chat(model, system, user, key, post) -> str:
    body = {"model": model, "max_tokens": 1500 if model.startswith("Qwen") else 400,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if model.startswith("Qwen"):
        body["reasoning_effort"] = "low"
    r = post(f"{BASE_URL}/chat/completions", json=body, timeout=TIMEOUT_S,
             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return (r.json()["choices"][0]["message"].get("content") or "").strip()


def _facts_text(facts: dict) -> str:
    return "\n".join(f"{k}: {'; '.join(v) if isinstance(v, list) else v}" for k, v in facts.items())


def write_note(facts: dict, key: str | None, post=requests.post) -> NoteResult:
    problems = []
    if key:
        for model in MODELS:
            try:
                text = _chat(model, NOTE_SYSTEM, _facts_text(facts), key, post)
            except Exception as exc:
                problems.append(f"{model}: {type(exc).__name__}")
                continue
            found = notes.validate_note(text, facts)
            if not found:
                return NoteResult(text, model, problems)
            problems.append(f"{model}: {found}")
    return NoteResult(notes.template_note(facts), "template", problems)


def answer(question: str, facts: dict, results_line: str, key: str | None, post=requests.post) -> NoteResult:
    """FR-015 (Should). Declines when the answer is not in the facts."""
    if not key:
        return NoteResult("The assistant is offline.", "template")
    user = f"Facts:\n{_facts_text(facts)}\nMeanings: {MEANINGS}\nResults: {results_line}\nQuestion: {question}"
    for model in MODELS:
        try:
            return NoteResult(_chat(model, ANSWER_SYSTEM, user, key, post), model)
        except Exception:
            continue
    return NoteResult("The assistant is offline.", "template")
