"""
OpsBrain API.

Run:  uvicorn api.main:app --reload
Docs: http://localhost:8000/docs
"""

import time
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from opsbrain.analyse import SCENARIOS, MODES, ENGINES, analyse
from api import metrics

app = FastAPI(
    title="OpsBrain API",
    description="Detects mine disruptions, searches fleet moves, and explains the trade-offs. "
                "It only recommends. A person decides.",
    version="0.2.0",
)
app.middleware("http")(metrics.metrics_middleware)


class AnalyseRequest(BaseModel):
    scenario: Literal[tuple(SCENARIOS)] = "combined"
    mode: Literal[MODES] = "balanced"
    engine: Literal[tuple(ENGINES)] = "optimiser"
    top_n: int = Field(3, ge=1, le=10, description="How many best options to show per event")


@lru_cache(maxsize=64)
def _cached(scenario, mode, engine, top_n):
    start = time.perf_counter()
    result = analyse(scenario, mode, engine, top_n)
    metrics.record_analysis(result, time.perf_counter() - start)
    return result


@app.get("/health")
def health():
    """Is the service alive? (Used by Docker and Kubernetes checks.)"""
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Numbers for Prometheus to collect."""
    return metrics.metrics_response()


@app.get("/scenarios")
def scenarios():
    """The disruption stories you can run."""
    return {
        "scenarios": [{"key": k, "title": v[0]} for k, v in SCENARIOS.items()],
        "modes": list(MODES),
        "engines": list(ENGINES),
    }


@app.post("/analyse")
def analyse_endpoint(req: AnalyseRequest):
    """Run a shift with OpsBrain watching. Returns, for every disruption, the
    best options, what each would produce, and what happens if nobody acts."""
    try:
        hits_before = _cached.cache_info().hits
        result = _cached(req.scenario, req.mode, req.engine, req.top_n)
        was_cached = _cached.cache_info().hits > hits_before
        metrics.ANALYSES.labels(req.scenario, req.engine, "hit" if was_cached else "miss").inc()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
