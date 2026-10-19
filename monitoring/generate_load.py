"""Sends a mix of requests to the API so the Grafana dashboard has something to show.
Run:  python monitoring/generate_load.py          (needs the stack running)
For the Kubernetes setup:  set OPSBRAIN_URL=http://localhost:8080  first
Stop with Ctrl+C."""
import itertools, json, time, urllib.request

import os
BASE = os.environ.get("OPSBRAIN_URL", "http://localhost:8000")
SCENARIOS = ["combined", "delay", "double", "default", "degradation", "closure"]
MODES = ["balanced", "oversized"]
ENGINES = ["optimiser", "rules"]
TOP_N = [1, 2, 3, 4, 5]  # different values so some requests really simulate (not cached)


def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except Exception as e:
        return getattr(e, "code", str(e))


for scenario, mode, engine, n in itertools.cycle(itertools.product(SCENARIOS, MODES, ENGINES, TOP_N)):
    print(scenario, mode, engine, n, "->", call("/analyse", {"scenario": scenario, "mode": mode, "engine": engine, "top_n": n}))
    call("/health"); call("/scenarios")
    call("/analyse", {"scenario": "nope"})  # a bad request on purpose, shows up as an error
    time.sleep(1.5)
