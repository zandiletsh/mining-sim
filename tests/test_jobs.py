import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import jobs

app = FastAPI()
app.include_router(jobs.router)
client = TestClient(app)


def _fake(scenario, mode, engine, top_n):
    time.sleep(0.2)
    return {"scenario": scenario, "mode": mode, "engine": engine, "top_n": top_n}


def _wait(job_id, tries=50):
    for _ in range(tries):
        r = client.get(f"/jobs/{job_id}").json()
        if r["status"] != "running":
            return r
        time.sleep(0.1)
    raise AssertionError("job never finished")


def setup_function():
    jobs._jobs.clear()


def test_job_returns_at_once_then_finishes(monkeypatch):
    monkeypatch.setattr(jobs, "analyse", _fake)
    t0 = time.time()
    r = client.post("/jobs", json={"scenario": "combined", "mode": "balanced",
                                   "engine": "optimiser", "top_n": 3})
    assert r.status_code == 202
    assert time.time() - t0 < 0.15          # did not wait for the analysis
    assert r.json()["status"] == "running"
    done = _wait(r.json()["id"])
    assert done["status"] == "done"
    assert done["result"]["scenario"] == "combined"


def test_same_request_same_job(monkeypatch):
    monkeypatch.setattr(jobs, "analyse", _fake)
    a = client.post("/jobs", json={"scenario": "delay"}).json()["id"]
    b = client.post("/jobs", json={"scenario": "delay"}).json()["id"]
    assert a == b


def test_other_pod_can_rebuild_the_job(monkeypatch):
    monkeypatch.setattr(jobs, "analyse", _fake)
    job_id = jobs.make_id("double", "balanced", "optimiser", 3)
    assert job_id not in jobs._jobs          # this "pod" never saw it
    assert _wait(job_id)["status"] == "done"


def test_bad_requests(monkeypatch):
    monkeypatch.setattr(jobs, "analyse", _fake)
    assert client.post("/jobs", json={"scenario": "nope"}).status_code == 422
    assert client.post("/jobs", json={"top_n": 99}).status_code == 422
    assert client.get("/jobs/garbage").status_code == 404
    assert client.get("/jobs/nope.balanced.optimiser.3").status_code == 404


def test_failed_job(monkeypatch):
    def boom(*a):
        raise RuntimeError("x")
    monkeypatch.setattr(jobs, "analyse", boom)
    r = client.post("/jobs", json={"scenario": "default"}).json()
    assert _wait(r["id"])["status"] == "failed"


def test_post_again_retries_a_failed_job(monkeypatch):
    def boom(*a):
        raise RuntimeError("x")
    monkeypatch.setattr(jobs, "analyse", boom)
    r = client.post("/jobs", json={"scenario": "default"}).json()
    assert _wait(r["id"])["status"] == "failed"
    monkeypatch.setattr(jobs, "analyse", _fake)
    client.post("/jobs", json={"scenario": "default"})
    assert _wait(r["id"])["status"] == "done"
