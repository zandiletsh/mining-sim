"""Prometheus metrics for the OpsBrain API."""

import time

from prometheus_client import Counter, Histogram, Gauge, CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# --- how the API is doing -------------------------------------------------
HTTP_REQUESTS = Counter(
    "opsbrain_http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_SECONDS = Histogram(
    "opsbrain_http_request_seconds", "HTTP request time in seconds", ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15, 30, 60, 120))
IN_PROGRESS = Gauge("opsbrain_http_requests_in_progress", "Requests being handled right now")

# --- what OpsBrain is doing -----------------------------------------------
ANALYSES = Counter(
    "opsbrain_analyses_total", "Analyses asked for", ["scenario", "engine", "cache"])
ANALYSE_SECONDS = Histogram(
    "opsbrain_analyse_seconds", "Time to simulate a shift and search options",
    ["engine"], buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120))
OPTIONS_SEARCHED = Histogram(
    "opsbrain_options_searched", "Fleet moves searched per disruption",
    buckets=(1, 3, 5, 10, 15, 25, 50, 100, 250))
BEST_GAIN_T = Gauge(
    "opsbrain_best_gain_tonnes",
    "Tonnes gained by the recommended option vs doing nothing (latest analysis, first disruption)",
    ["scenario", "engine"])
DISRUPTIONS = Counter(
    "opsbrain_disruptions_total", "Disruptions seen, by type", ["type"])


def record_analysis(result: dict, seconds: float) -> None:
    """Called once each time a shift is really simulated (not when served from cache)."""
    ANALYSE_SECONDS.labels(result["engine"]).observe(seconds)
    for ev in result["events"]:
        OPTIONS_SEARCHED.observe(ev["options_searched"])
        for d in ev["events"]:
            DISRUPTIONS.labels(d["type"]).inc()
    if result["events"]:
        first = result["events"][0]
        best = max(o["gain_vs_doing_nothing_t"] for o in first["options"])
        BEST_GAIN_T.labels(result["scenario"], result["engine"]).set(best)


async def metrics_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    IN_PROGRESS.inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        IN_PROGRESS.dec()
        route = request.scope.get("route")
        path = route.path if route is not None else "unmatched"  # keeps labels few
        HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        HTTP_SECONDS.labels(request.method, path).observe(time.perf_counter() - start)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
