"""
Runs shifts with OpsBrain watching, and dumps everything the visual demo
needs to JSON, one file per scenario: a per-tick snapshot of the whole mine
(for animating the layout) plus the full decision record for each event
(context, options searched, and their simulated consequences).

Run it from the project folder:  python export_demo_data.py
"""

import json
import os
from itertools import product

import topology
import disruptions
from simulation import Simulation
from opsbrain.context import build_context
from opsbrain.optimiser import generate_candidates
from opsbrain.consequences import evaluate_all, pick_best

MODE = "balanced"
TOP_N = 3  # show "accept the loss" plus the best TOP_N of everything searched

# key -> (file, picker title, one-line story, scenario builder)
SCENARIOS = {
    "combined": (
        "demo_data.json",
        "Three separate problems",
        "A truck breaks down, later a crusher loses capacity, later a road closes.",
        disruptions.combined_scenario,
    ),
    "delay": (
        "demo_data_delay.json",
        "Repair runs late",
        "A truck breaks down with a 90 minute repair, then the repair takes 120 minutes longer.",
        disruptions.delay_scenario,
    ),
    "double": (
        "demo_data_double.json",
        "Two problems at once",
        "A truck breaks down and a crusher loses 60% capacity in the same minute.",
        disruptions.double_scenario,
    ),
}


def build_run(key, decisions):
    """One full shift. decisions[i] == "1" means the operator applies the
    recommendation at event number i; "0" means carries on without acting."""
    file_name, title, blurb, make_scenario = SCENARIOS[key]
    events = []

    def on_disruption(sim, fired):
        ctx = build_context(sim, fired)
        all_evaluations = evaluate_all(sim, generate_candidates(sim, fired))
        baseline = next(e for e in all_evaluations if e.option.option_id == "accept_loss")
        best = pick_best(all_evaluations)
        others = sorted(
            (e for e in all_evaluations if e is not baseline),
            key=lambda e: (-e.final_production_t, e.option.complexity),
        )
        shown = [baseline] + others[:TOP_N]

        events.append({
            "tick": ctx.tick,
            "minutesElapsed": ctx.shift_minutes_elapsed,
            "disruptionType": ctx.disruption_type,
            "disruptionTarget": ctx.disruption_target,
            "durationMin": ctx.disruption_duration_min,
            "events": [
                {"type": kind, "target": target, "durationMin": minutes}
                for kind, target, minutes in ctx.events
            ],
            "productionSoFar": ctx.production_so_far_t,
            "pctOfTarget": ctx.pct_of_target_so_far,
            "searched": len(all_evaluations),
            "options": [
                {
                    "id": e.option.option_id,
                    "label": e.option.label,
                    "description": e.option.description,
                    "finalProduction": e.final_production_t,
                    "deltaVsBaseline": round(e.final_production_t - baseline.final_production_t, 1),
                    "isRecommended": e.option.option_id == best.option.option_id,
                    "isBaseline": e.option.option_id == "accept_loss",
                }
                for e in shown
            ],
            "recommendedLabel": best.option.label,
        })
        # The operator clicked "Apply": the real mine now follows the best option.
        i = len(events) - 1
        if i < len(decisions) and decisions[i] == "1":
            best.option.apply(sim)

    sim = Simulation(make_scenario(), mode=MODE)
    sim.event_hooks.append(on_disruption)

    ticks = []
    for _ in range(topology.TOTAL_TICKS):
        sim.tick += 1
        sim._revert_expired_reassignments()
        sim._apply_disruptions()
        sim.finish_current_tick()

        if sim.tick % 2 == 0:  # every 2 minutes keeps the file small
            ticks.append({
                "tick": sim.tick,
                "production": round(sim.cumulative_production_t, 1),
                "trucks": {
                    t.asset_id: {
                        "state": t.state.value,
                        "route": t.route_id,
                        "location": t.location,
                        "cargo": round(t.cargo_t, 1),
                    }
                    for t in sim.trucks.values()
                },
                "crushers": {
                    c.asset_id: {"health": round(c.health_pct, 1), "state": c.state.value}
                    for c in sim.crushers.values()
                },
                "stockpiles": {
                    s.asset_id: round(s.pct_full(), 1) for s in sim.stockpiles.values()
                },
            })

    return {
        "finalProduction": round(sim.cumulative_production_t, 1),
        "events": events,
        "ticks": ticks,
    }, sim


def build(key):
    file_name, title, blurb, make_scenario = SCENARIOS[key]
    # how many events does this scenario have? (run once with no action)
    first, sim = build_run(key, "")
    n = len(first["events"])
    runs = {}
    for combo in product("01", repeat=n):
        decisions = "".join(combo)
        runs[decisions], _ = build_run(key, decisions)
    return {
        "scenarioKey": key,
        "scenarioTitle": title,
        "scenarioBlurb": blurb,
        "shiftMinutes": topology.SHIFT_MINUTES,
        "productionTarget": topology.PRODUCTION_TARGET_T,
        "eventCount": n,
        "runs": runs,
        "trucks": list(sim.trucks.keys()),
        "routes": {
            r.route_id: {"from": r.from_pit, "to": r.to_crusher}
            for r in topology.ROUTES.values()
        },
        "crushers": list(sim.crushers.keys()),
        "stockpiles": list(sim.stockpiles.keys()),
    }


if __name__ == "__main__":
    # Written next to the page that reads them, so this works on any computer.
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_artifact")
    os.makedirs(out_dir, exist_ok=True)
    for key, (file_name, *_rest) in SCENARIOS.items():
        data = build(key)
        path = os.path.join(out_dir, file_name)
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        finals = {k: r["finalProduction"] for k, r in data["runs"].items()}
        print(f"{key:<9} events: {data['eventCount']}  final by decisions: {finals}  "
              f"-> {file_name} ({os.path.getsize(path)/1024:.0f} KB)")
