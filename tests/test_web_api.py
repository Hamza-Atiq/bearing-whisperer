import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "web" / "api"


def test_server_functions_run_the_tested_code():
    for f in ("assistant.py", "notes.py", "copilot.py"):
        assert (API / "_bearing" / f).read_bytes() == (ROOT / "bearing" / f).read_bytes(), \
            f"{f} differs: run python -m bearing.sync_web"


def test_published_data_matches_the_saved_results():
    import json
    app = json.loads((API / "_data" / "app.json").read_text(encoding="utf-8"))
    assert app["motors"] == json.loads((ROOT / "results" / "motors.json").read_text(encoding="utf-8"))
    assert (ROOT / "web" / "public" / "data" / "app.json").read_bytes() == (API / "_data" / "app.json").read_bytes()


@pytest.fixture
def common(monkeypatch):
    monkeypatch.delenv("AMD_KEY", raising=False)
    sys.path.insert(0, str(API))
    mod = importlib.import_module("_common")
    yield mod
    sys.path.remove(str(API))


def test_without_a_key_the_site_still_answers(common):
    assert common.dispatch("health", {})["assistant"] is False
    note = common.dispatch("note", {"motor": "Motor 01"})
    assert note["source"] == "template" and "Motor 01" in note["text"]
    plan = common.dispatch("plan", {"minutes": 60, "per_check": 20})
    assert plan["source"] == "rule" and len(plan["visits"]) <= 3


def test_facts_come_from_the_server_not_the_browser(common):
    note = common.dispatch("note", {"motor": "Motor 01", "facts": {"status": "healthy"}})
    assert common.MOTORS["Motor 01"]["plant_word"] in note["text"]
    with pytest.raises(ValueError):
        common.dispatch("note", {"motor": "Motor 99"})
    with pytest.raises(ValueError):
        common.dispatch("ask", {"motor": "Motor 01", "question": ""})


def test_track_record_names_the_round_behind_the_plant_view(common):
    line = common.track_record()
    assert line.startswith(f"round {common.APP['proof']['plant_round']}")
