import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from api.main import app

c = TestClient(app)


def test_health():
    assert c.get("/health").json() == {"status": "ok"}


def test_scenarios():
    keys = [s["key"] for s in c.get("/scenarios").json()["scenarios"]]
    assert {"combined", "delay", "double"} <= set(keys)


def test_double_matches_demo_numbers():
    r = c.post("/analyse", json={"scenario": "double"}).json()
    assert r["final_production_if_nobody_acts_t"] == 5396.7
    ev = r["events"][0]
    assert len(ev["events"]) == 2 and ev["act_is_worth_it"]
    best = [o for o in ev["options"] if o["recommended"]][0]
    assert best["final_production_t"] == 6000.0 and best["gain_vs_doing_nothing_t"] == 603.3


def test_oversized_says_accept_the_loss():
    r = c.post("/analyse", json={"scenario": "default", "mode": "oversized"}).json()
    assert all(not e["act_is_worth_it"] for e in r["events"])


def test_bad_input_rejected():
    assert c.post("/analyse", json={"scenario": "nope"}).status_code == 422


def test_metrics_endpoint_counts_requests_and_analyses():
    c.get("/health")
    c.post("/analyse", json={"scenario": "delay", "top_n": 2})
    c.post("/analyse", json={"scenario": "delay", "top_n": 2})  # second one comes from the cache
    text = c.get("/metrics").text
    assert 'opsbrain_http_requests_total{method="GET",path="/health",status="200"}' in text
    assert 'opsbrain_analyses_total{cache="miss",engine="optimiser",scenario="delay"}' in text
    assert 'opsbrain_analyses_total{cache="hit",engine="optimiser",scenario="delay"}' in text
    assert "opsbrain_options_searched_count" in text
    assert 'opsbrain_disruptions_total{type="TRUCK_BREAKDOWN"}' in text
    assert "opsbrain_best_gain_tonnes" in text
