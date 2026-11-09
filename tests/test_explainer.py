import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import explainer, jobs

RESULT = {
    "scenario": "default", "title": "One truck breaks down", "mode": "balanced", "engine": "optimiser",
    "production_target_t": 5000, "final_production_if_nobody_acts_t": 5978.3,
    "events": [{
        "tick": 180, "clock_minutes": 180,
        "events": [{"type": "TRUCK_BREAKDOWN", "target": "TRUCK_06", "duration_min": 180}],
        "production_so_far_t": 1491.7, "options_searched": 15,
        "recommended": "Move TRUCK_01 -> R3 (until the disruption is over)", "act_is_worth_it": True,
        "options": [
            {"id": "accept_loss", "label": "Accept the loss", "final_production_t": 5978.3,
             "gain_vs_doing_nothing_t": 0, "recommended": False},
            {"id": "m1", "label": "Move TRUCK_01 -> R3 (until the disruption is over)",
             "final_production_t": 6000, "gain_vs_doing_nothing_t": 21.7, "recommended": True},
            {"id": "m2", "label": "Move TRUCK_04 -> R1 (until the disruption is over)",
             "final_production_t": 6000, "gain_vs_doing_nothing_t": 21.7, "recommended": False},
        ],
    }],
}

app = FastAPI()
app.include_router(jobs.router)
app.include_router(explainer.router)
client = TestClient(app)


def test_template_uses_engine_numbers(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = explainer.explain(RESULT)
    assert out["source"] == "template"
    for needle in ("5,978.3", "6,000", "21.7", "TRUCK_01", "A person decides"):
        assert needle in out["text"]


def test_template_when_acting_is_not_worth_it():
    r = {**RESULT, "events": [{**RESULT["events"][0], "act_is_worth_it": False}]}
    assert "doing nothing is fine" in explainer.template_text(explainer.build_facts(r))


def test_guardrail_accepts_rounding_and_hours():
    facts = explainer.build_facts(RESULT)
    assert explainer.numbers_are_grounded("It gains about 22 t and lasts 3 hours, ending at 6000 t.", facts)


def test_guardrail_rejects_invented_numbers():
    facts = explainer.build_facts(RESULT)
    assert not explainer.numbers_are_grounded("This gains 450 t.", facts)


def test_claude_text_used_when_grounded(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(explainer, "call_claude", lambda f: "Move TRUCK_01. It gains 21.7 t.")
    assert explainer.explain(RESULT)["source"] == "claude"


def test_falls_back_when_claude_invents_a_number(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(explainer, "call_claude", lambda f: "It gains 999 t.")
    assert explainer.explain(RESULT)["source"] == "template"


def test_falls_back_when_claude_fails(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    def boom(f):
        raise RuntimeError("network")
    monkeypatch.setattr(explainer, "call_claude", boom)
    assert explainer.explain(RESULT)["source"] == "template"


def test_endpoint_running_then_done(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    jobs._jobs.clear()
    def slow(*a):
        time.sleep(0.3)
        return RESULT
    monkeypatch.setattr(jobs, "analyse", slow)
    jid = "default.balanced.optimiser.3"
    assert client.get(f"/jobs/{jid}/explain").json()["status"] == "running"
    for _ in range(40):
        r = client.get(f"/jobs/{jid}/explain").json()
        if r["status"] == "done":
            break
        time.sleep(0.1)
    assert r["status"] == "done" and "21.7" in r["text"]


def test_endpoint_unknown_job():
    assert client.get("/jobs/garbage/explain").status_code == 404
