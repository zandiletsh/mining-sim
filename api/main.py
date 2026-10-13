"""
OpsBrain API.

Run:  uvicorn api.main:app --reload
Docs: http://localhost:8000/docs
"""

from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from opsbrain.analyse import SCENARIOS, MODES, ENGINES, analyse

app = FastAPI(
    title="OpsBrain API",
    description="Detects mine disruptions, searches fleet moves, and explains the trade-offs. "
                "It only recommends. A person decides.",
    version="0.1.0",
)


class AnalyseRequest(BaseModel):
    scenario: Literal[tuple(SCENARIOS)] = "combined"
    mode: Literal[MODES] = "balanced"
    engine: Literal[tuple(ENGINES)] = "optimiser"
    top_n: int = Field(3, ge=1, le=10, description="How many best options to show per event")


@lru_cache(maxsize=64)
def _cached(scenario, mode, engine, top_n):
    return analyse(scenario, mode, engine, top_n)


@app.get("/health")
def health():
    """Is the service alive? (Used by Docker and Kubernetes checks.)"""
    return {"status": "ok"}


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
        return _cached(req.scenario, req.mode, req.engine, req.top_n)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
