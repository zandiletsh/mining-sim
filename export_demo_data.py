"""
Runs a shift with OpsBrain watching, and dumps everything a visual demo
needs to JSON: a per-tick snapshot of the whole mine (for animating the
layout) plus the full decision record for each disruption (context,
options, and their simulated consequences) for the event feed.
"""

import json
import copy

import topology
import disruptions
from simulation import Simulation
from opsbrain.context import build_context
from opsbrain.optimiser import generate_candidates
from opsbrain.consequences import evaluate_all, pick_best

SCENARIO = disruptions.combined_scenario()
MODE = "balanced"
TOP_N = 3  # show "accept the loss" plus the best TOP_N of everything searched

events = []


def on_disruption(sim, fired):
    ctx = build_context(sim, fired)
    options = generate_candidates(sim, fired)
    all_evaluations = evaluate_all(sim, options)
    baseline = next(e for e in all_evaluations if e.option.option_id == "accept_loss")
    best = pick_best(all_evaluations)
    others = sorted(
        (e for e in all_evaluations if e is not baseline),
        key=lambda e: (-e.final_production_t, e.option.complexity),
    )
    evaluations = [baseline] + others[:TOP_N]

    events.append({
        "tick": ctx.tick,
        "minutesElapsed": ctx.shift_minutes_elapsed,
        "disruptionType": ctx.disruption_type,
        "disruptionTarget": ctx.disruption_target,
        "durationMin": ctx.disruption_duration_min,
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
            for e in evaluations
        ],
        "recommendedLabel": best.option.label,
    })


sim = Simulation(SCENARIO, mode=MODE)
sim.event_hooks.append(on_disruption)

ticks = []
for _ in range(topology.TOTAL_TICKS):
    sim.tick += 1
    sim._revert_expired_reassignments()
    sim._apply_disruptions()
    sim._update_trucks()
    sim._update_crushers()
    sim._update_processing()

    if sim.tick % 2 == 0:  # thin to every 2 minutes to keep the file small
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

output = {
    "shiftMinutes": topology.SHIFT_MINUTES,
    "productionTarget": topology.PRODUCTION_TARGET_T,
    "finalProduction": round(sim.cumulative_production_t, 1),
    "trucks": list(sim.trucks.keys()),
    "routes": {
        r.route_id: {"from": r.from_pit, "to": r.to_crusher}
        for r in topology.ROUTES.values()
    },
    "crushers": list(sim.crushers.keys()),
    "stockpiles": list(sim.stockpiles.keys()),
    "events": events,
    "ticks": ticks,
}

import os

# Written next to the page that reads it, so this works on any computer.
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_artifact")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "demo_data.json")
with open(out_path, "w") as f:
    json.dump(output, f)

print(f"ticks: {len(ticks)}, events: {len(events)}")
print(f"final production: {output['finalProduction']}")
print(f"wrote {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
