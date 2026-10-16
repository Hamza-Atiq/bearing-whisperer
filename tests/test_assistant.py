from bearing import assistant, notes

FACTS = notes.facts_for({"motor_name": "Motor 07", "plant_word": "check bearing", "how_sure": "medium",
                         "evidence": ["more electrical buzz between 2,018 and 2,575 Hz than the average motor in training"]})


class Reply:
    def __init__(self, status, text=""):
        self.status_code, self._text = status, text

    def json(self):
        return {"choices": [{"message": {"content": self._text}}]}


def test_uses_gemma_when_note_is_good():
    good = notes.template_note(FACTS)
    calls = []
    post = lambda url, **kw: (calls.append(kw["json"]["model"]), Reply(200, good))[1]
    r = assistant.write_note(FACTS, "rc-test", post=post)
    assert r.source == "Gemma-4-31B-IT" and calls == ["Gemma-4-31B-IT"]


def test_falls_back_to_qwen_when_gemma_adds_a_number():
    good = notes.template_note(FACTS)
    replies = iter([Reply(200, good + " Fails in 3 days."), Reply(200, good)])
    r = assistant.write_note(FACTS, "rc-test", post=lambda url, **kw: next(replies))
    assert r.source == "Qwen3.8-27B"


def test_falls_back_to_template_when_all_models_fail():
    def post(url, **kw):
        raise TimeoutError("down")
    r = assistant.write_note(FACTS, "rc-test", post=post)
    assert r.source == "template" and r.text == notes.template_note(FACTS)


def test_no_key_means_template_without_calling():
    def post(url, **kw):
        raise AssertionError("must not call")
    assert assistant.write_note(FACTS, None, post=post).source == "template"


def test_load_key_respects_empty_env(monkeypatch):
    monkeypatch.setenv("AMD_KEY", "")
    assert assistant.load_key() is None


def test_answers_get_the_meaning_of_how_sure():
    """FR-015 names 'what does this mean?'; the model must be given the meaning, not guess it."""
    seen = []
    post = lambda url, **kw: (seen.append(kw["json"]["messages"][1]["content"]), Reply(200, "ok"))[1]
    assistant.answer("What does 'how sure: medium' mean?", FACTS, "results", "rc-test", post=post)
    assert "not how bad the damage is" in seen[0]


def test_answer_rules_allow_the_meanings_and_define_each_word():
    assert "meanings" in assistant.ANSWER_SYSTEM.lower()
    for word in ("high", "medium", "low"):
        assert f"{word} means" in assistant.MEANINGS
