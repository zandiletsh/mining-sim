# OpsBrain

**A decision engine for when something breaks in a complex physical operation.**

Monitoring tells you *what happened*. OpsBrain tells you *what to do next*, and what each choice would cost.

First domain: **mining**. Status: **working prototype on a simulated mine** (no real mine data yet).

---

## The problem

A haul truck breaks down. Normal systems say: *"Truck 06 is unavailable for 3 hours."*

The real question is bigger: **what should we do now?** One truck going down changes haul capacity, crusher feed, plant throughput, stockpile levels and the shift target. People usually decide from experience and gut feel, under time pressure.

## What OpsBrain does

1. **Detects** the disruption.
2. **Understands** the state of the mine right now.
3. **Searches** the possible responses (9 to 15 fleet moves per problem).
4. **Simulates** each one forward to the end of the shift.
5. **Ranks** them against doing nothing, and **explains** the trade-offs in plain words.
6. **A person decides.** OpsBrain only recommends. It never acts on its own.

### Example (from the simulated mine)

Two problems hit in the same minute: a truck breaks down and a crusher loses 60% of its capacity.

| Choice | Shift output |
|---|---|
| Do nothing | 5,396.7 t |
| OpsBrain's best move (send Truck 01 to route R3) | **6,000 t** (**+603.3 t**, about 11%) |

> *"Truck breakdown on TRUCK_06 for 150 min and crusher degradation on CRUSHER_1 for 240 min. OpsBrain searched 15 possible moves. If nobody acts, the shift ends at 5,396.7 t. Best move: Move TRUCK_01 -> R3. It ends the shift at 6,000 t, which is 603.3 t more than doing nothing."*

That text comes from the built-in explainer. Every number in it is produced by the engine, not invented.

---

## How it works

```
 Disruption ──► Detect ──► Context ──┬─► Rules ──────┐
 (simulated mine)                    └─► Optimiser ──┴─► What-if ──► Explain ──► API ──► Control Room ──► Person decides
                                                         (run the shift                (recommend only)
                                                          to the end)
```

- **Simulated mine:** pits, haul trucks, crushers, stockpile and plant. One tick is one minute, over a 12-hour shift. The plant (500 t/h) is the bottleneck.
- **Rules:** three hand-picked responses.
- **Optimiser:** searches up to two truck moves, 9 to 15 options per problem.
- **What-if simulator:** copies the mine and runs each option to the end of the shift. In the tests, the forecast matches the real result exactly.
- **Explain:** ranks options against doing nothing. It recommends a move only if it gains at least 1 t.

---

## Platform and engineering

The same container image runs in three places.

| Area | What is built |
|---|---|
| **Service** | FastAPI. `POST /analyse` (answer in one go), `POST /jobs` (answer in the background), `GET /jobs/{id}/explain` (plain words), `/health`, `/metrics` |
| **Containers** | Docker (non-root user, health check), Docker Compose (API + Prometheus + Grafana) |
| **Kubernetes** | K3s (via k3d): 2 replicas, rolling updates, startup/readiness/liveness probes, autoscaling 2 to 5 pods at 60% CPU |
| **Cloud** | Terraform on AWS: VPC, load balancer, ECR, ECS Fargate, IAM, autoscaling 2 to 5 tasks (23 resources) |
| **CI** | GitHub Actions: unit tests, Docker build with a live health check, Kubernetes manifest validation |
| **Observability** | Prometheus metrics, Grafana dashboard with 10 panels |
| **Tests** | 28 automatic tests |

Proven on AWS: under load, the service scaled from 2 to 5 tasks by itself, then everything was destroyed with `terraform destroy` to stop the cost.

### Design decisions

- **Human in the loop.** The system recommends. A person approves. This is a deliberate safety choice for high-consequence environments.
- **Explanations cannot invent numbers.** The explainer can use Claude (optional) to write the text. A check compares every number in the text against the engine's output. If anything does not match, or there is no API key, it falls back to a fixed template.
- **Background jobs with no database.** The job id contains the request itself (`scenario.mode.engine.top_n`). Answers are deterministic, so any pod can rebuild a job it has never seen. Polling works behind a load balancer with several copies.
- **Cost control.** No NAT gateway, small Fargate tasks, and a clean `terraform destroy`.

---

## Run it

Needs Python 3.11+ and Docker.

```bash
# tests
pip install -r requirements-dev.txt
python -m pytest -q            # 28 passed

# API + Prometheus + Grafana
docker compose up --build
# API docs:   http://localhost:8000/docs
# Grafana:    http://localhost:3000
```

Try it: `POST /jobs` with `{"scenario":"combined","mode":"balanced","engine":"optimiser","top_n":3}`, then `GET /jobs/{id}/explain`.

Optional: set `ANTHROPIC_API_KEY` to let Claude write the explanations. Never commit the key.

More detail: `k8s/README.md` (Kubernetes) and `terraform/README.md` (AWS).

### Project layout

```
topology.py, models.py, disruptions.py, simulation.py   the simulated mine
opsbrain/                                                context, rules, optimiser, what-if, ranking
api/                                                     FastAPI service, metrics, jobs, explainer
demo_artifact/                                           Control Room replay page and its data
monitoring/                                              Prometheus and Grafana
k8s/   terraform/   .github/workflows/                   Kubernetes, AWS, CI
```

---

## Honest status and limits

- It runs on a **simulated mine**, not real equipment data.
- The optimiser takes 5 to 15 seconds per problem (this is why background jobs exist).
- Terraform state is local. A production setup would use remote state (S3).
- It has not been tested with real operators or real mine systems.

## What is next

- Connect to real operational data (fleet management, plant systems).
- Add risk and uncertainty to the forecasts, not only a single best estimate.
- Record each decision and its real outcome, so the system can learn from them.
- Other industries: logistics, construction.

---

**Built by Zandile Tshabalala** — cloud and platform engineer. Questions or ideas: open an issue or message me on LinkedIn.
