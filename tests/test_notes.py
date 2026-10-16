from bearing import notes

MOTOR = {"motor_name": "Motor 07", "plant_word": "check bearing", "how_sure": "medium",
         "evidence": ["more electrical buzz between 2,018 and 2,575 Hz than the average motor in training"],
         "urgency": "next routine visit, with a manual check", "bearing": "KA04"}


def test_template_note_passes_its_own_checks():
    for word in ("check bearing", "ask a person", "healthy"):
        facts = notes.facts_for({**MOTOR, "plant_word": word})
        text = notes.template_note(facts)
        assert notes.validate_note(text, facts) == [], (word, text)


def test_action_notes_say_confirm_first():
    facts = notes.facts_for(MOTOR)
    assert "vibration or ultrasound" in notes.template_note(facts)


def test_rejects_note_with_invented_number():
    facts = notes.facts_for(MOTOR)
    bad = notes.template_note(facts) + " It will fail in 12 days."
    problems = notes.validate_note(bad, facts)
    assert any("12" in p for p in problems)


def test_rejects_long_note_and_jargon():
    facts = notes.facts_for(MOTOR)
    long = notes.template_note(facts) + " word" * 80
    assert any("words" in p for p in notes.validate_note(long, facts))
    jargon = notes.template_note(facts) + " BPFO sideband detected."
    assert any("jargon" in p for p in notes.validate_note(jargon, facts))


def test_rejects_missing_confirmation():
    facts = notes.facts_for(MOTOR)
    text = "Motor 07: check bearing. How sure: medium."
    assert any("confirm" in p for p in notes.validate_note(text, facts))


def test_work_order_is_a_draft_needing_approval():
    wo = notes.work_order(notes.facts_for(MOTOR), MOTOR)
    assert wo["status"] == "DRAFT, needs a person's approval"
    assert wo["urgency"] == "next routine visit, with a manual check"


def test_rejects_note_that_contradicts_the_status():
    facts = notes.facts_for({**MOTOR, "plant_word": "healthy", "how_sure": "high"})
    text = notes.template_note(facts) + " Please check bearing soon."
    assert any("contradicts" in p for p in notes.validate_note(text, facts))
    facts = notes.facts_for(MOTOR)
    text = notes.template_note(facts) + " Or ask a person."
    assert any("contradicts" in p for p in notes.validate_note(text, facts))


def test_accepts_honest_wording_and_motor_number_without_zero():
    facts = notes.facts_for(MOTOR)
    text = notes.template_note(facts).replace("Motor 07", "Motor 7") + " The system is uncertain about the cause."
    assert notes.validate_note(text, facts) == []


def test_template_notes_stay_short_with_two_evidence_lines():
    two = ["more electrical buzz between 2,018 and 2,575 Hz than the average motor in training",
           "a stronger trace at an outer- or inner-ring bearing pitch than the average motor in training"]
    for word in ("check bearing", "ask a person", "healthy"):
        facts = notes.facts_for({**MOTOR, "plant_word": word, "evidence": two})
        assert notes.validate_note(notes.template_note(facts), facts) == []


def test_facts_and_template_carry_the_urgency():
    facts = notes.facts_for(MOTOR)
    assert facts["urgency"] == "next routine visit, with a manual check"
    assert "next routine visit" in notes.template_note(facts)
    healthy = notes.facts_for({**MOTOR, "plant_word": "healthy", "urgency": None})
    assert healthy["urgency"] == "none"


def test_rejects_note_without_urgency_or_evidence():
    facts = notes.facts_for(MOTOR)
    text = ("Motor 07: check bearing, how sure: medium. Confirm with a vibration or ultrasound check before "
            "replacing anything. This is recorded lab data, not a live plant.")
    problems = notes.validate_note(text, facts)
    assert any("urgency" in p for p in problems)
    assert any("evidence" in p for p in problems)


def test_rejects_action_note_that_also_says_healthy():
    facts = notes.facts_for(MOTOR)
    text = notes.template_note(facts) + " The motor looks healthy."
    assert any("contradicts" in p for p in notes.validate_note(text, facts))


ROUND2_EVIDENCE = ["a sharper peak at an outer-ring bearing pitch than the average motor in training",
                   "more clicks (a more spiky current) than the average motor in training"]


def test_round2_evidence_words_are_checked_too():
    facts = notes.facts_for({**MOTOR, "evidence": ROUND2_EVIDENCE})
    assert notes.validate_note(notes.template_note(facts), facts) == []
    text = ("Motor 07: check bearing. How sure: medium. Act at the next routine visit, with a manual check, and "
            "confirm with a vibration or ultrasound check before replacing anything. "
            "This is recorded lab data, not a live plant.")
    assert any("evidence" in p for p in notes.validate_note(text, facts))
    ok = text.replace("How sure: medium.", "How sure: medium. The current showed a sharper peak.")
    assert notes.validate_note(ok, facts) == []
