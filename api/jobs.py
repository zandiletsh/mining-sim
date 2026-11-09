"""Background jobs for slow analyses.

POST /jobs        -> 202 {"id": "...", "status": "running"}   (returns at once)
GET  /jobs/{id}   -> {"id", "status": "running" | "done" | "failed", "result"?}

The job id IS the request: "scenario.mode.engine.top_n". Answers are deterministic,
so any pod/task can rebuild a job it has never seen. That keeps polling working
when several copies run behind a load balancer, with no database.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from opsbrain.analyse import ENGINES, MODES, SCENARIOS, analyse

router = APIRouter(tags=["jobs"])

MAX_WORKERS = 2          # parallel analyses per pod (the optimiser is CPU heavy)
MAX_KEPT = 200           # finished jobs kept in memory per pod
TTL_SECONDS = 3600

_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="job")
_lock = threading.Lock()
_jobs: dict = {}         # id -> {"future": Future, "created": float}


class JobRequest(BaseModel):
    scenario: str = "default"
    mode: str = "balanced"
    engine: str = "optimiser"
    top_n: int = 3


def make_id(scenario: str, mode: str, engine: str, top_n: int) -> str:
    return f"{scenario}.{mode}.{engine}.{top_n}"


def parse_id(job_id: str):
    """Return (scenario, mode, engine, top_n) or raise ValueError."""
    parts = job_id.split(".")
    if len(parts) != 4:
        raise ValueError("bad id")
    scenario, mode, engine, top_n = parts
    if scenario not in SCENARIOS or mode not in MODES or engine not in ENGINES:
        raise ValueError("unknown option")
    n = int(top_n)
    if not 1 <= n <= 10:
        raise ValueError("top_n out of range")
    return scenario, mode, engine, n


def _cleanup():
    now = time.time()
    for k in [k for k, v in _jobs.items()
              if v["future"].done() and now - v["created"] > TTL_SECONDS]:
        del _jobs[k]
    if len(_jobs) > MAX_KEPT:
        done = sorted((k for k, v in _jobs.items() if v["future"].done()),
                      key=lambda k: _jobs[k]["created"])
        for k in done[: len(_jobs) - MAX_KEPT]:
            del _jobs[k]


def _start(job_id: str, args: tuple, retry: bool = False):
    """Start the job on this pod unless it is already known (same request = same job).
    A failed job is only retried when the caller POSTs again."""
    with _lock:
        _cleanup()
        job = _jobs.get(job_id)
        if job is None or (retry and job["future"].done() and job["future"].exception()):
            _jobs[job_id] = {"future": _pool.submit(analyse, *args), "created": time.time()}
    return _jobs[job_id]


def _view(job_id: str, job: dict) -> dict:
    fut = job["future"]
    if not fut.done():
        return {"id": job_id, "status": "running"}
    if fut.exception() is not None:
        return {"id": job_id, "status": "failed", "error": "analysis failed"}
    return {"id": job_id, "status": "done", "result": fut.result()}


@router.post("/jobs", status_code=202)
def create_job(req: JobRequest):
    try:
        args = parse_id(make_id(req.scenario, req.mode, req.engine, req.top_n))
    except ValueError:
        raise HTTPException(422, "unknown scenario, mode, engine or top_n (1-10)")
    job_id = make_id(*args)
    return _view(job_id, _start(job_id, args, retry=True))


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        args = parse_id(job_id)
    except ValueError:
        raise HTTPException(404, "no such job")
    # unknown on this pod? Another pod may have created it: rebuild it here.
    return _view(job_id, _start(job_id, args))
