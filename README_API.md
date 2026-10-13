# OpsBrain API

Run it with Docker:

    docker compose up --build

Then open http://localhost:8000/docs

## Endpoints
- `GET /health` - is it alive?
- `GET /scenarios` - the stories you can run
- `POST /analyse` - run a shift with OpsBrain watching

Example body for `/analyse`:

    {"scenario": "double", "mode": "balanced", "engine": "optimiser", "top_n": 3}

## Without Docker

    pip install -r requirements-dev.txt
    uvicorn api.main:app --reload
    pytest

## Monitoring (Prometheus + Grafana)

`docker compose up --build` also starts:
- Prometheus: http://localhost:9090 (collects numbers from `/metrics` every 5 seconds)
- Grafana: http://localhost:3000 (the OpsBrain dashboard opens by itself, no login)

To fill the dashboard with data, in a second window run:

    python monitoring/generate_load.py
