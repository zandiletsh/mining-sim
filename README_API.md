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
