"""
One function that runs a whole shift with OpsBrain watching and returns
plain data (dicts), so the API, the demo exporter or a test can all use it.
Nobody acts on the advice here: the shift shows what OpsBrain would have
recommended at each event, and what happens if nobody does anything.
"""

from __future__ import annotations

import topology
import disruptions
from simulation import Simulation
from opsbrain.context import build_context
from opsbrain.rules import generate_options
from opsbrain.optimiser import generate_candidates
from opsbrain.consequences import evaluate_all, pick_best

SCENARIOS = {
    "default": ("One truck breaks down", disruptions.default_scenario),
    "degradation": ("A crusher loses capacity", disruptions.degradation_scenario),
    "closure": ("A road closes", disruptions.road_closure_scenario),
    "combined": ("Three separate problems", disruptions.combined_scenario),
    "delay": ("Repair runs late", disruptions.delay_scenario),
    "double": ("Two problems at once", disruptions.double_scenario),
}
MODES = ("balanced", "oversized")
ENGINES = {"optimiser": generate_candidates, "rules": generate_options}


def analyse(scenario: str = "combined", mode: str = "balanced",
            engine: str = "optimiser", top_n: int = 3) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario '{scenario}'")
    if mode not in MODES:
        raise ValueError(f"unknown mode '{mode}'")
    if engine not in ENGINES:
        raise ValueError(f"unknown engine '{engine}'")
    generate = ENGINES[engine]
    events = []

    def on_disruption(sim, fired):
        ctx = build_context(sim, fired)
        evaluations = evaluate_all(sim, generate(sim, fired))
        baseline = next(e for e in evaluations if e.option.option_id == "accept_loss")
        best = pick_best(evaluations)
        others = sorted(
            (e for e in evaluations if e is not baseline),
            key=lambda e: (-e.final_production_t, e.option.complexity),
        )
        events.append({
            "tick": ctx.tick,
            "clock_minutes": ctx.shift_minutes_elapsed,
            "events": [
                {"type": k, "target": t, "duration_min": m} for k, t, m in ctx.events
            ],
            "production_so_far_t": ctx.production_so_far_t,
            "options_searched": len(evaluations),
            "recommended": best.option.label,
            "act_is_worth_it": best is not baseline,
            "options": [
                {
                    "id": e.option.option_id,
                    "label": e.option.label,
                    "description": e.option.description,
                    "final_production_t": e.final_production_t,
                    "gain_vs_doing_nothing_t": round(
                        e.final_production_t - baseline.final_production_t, 1),
                    "recommended": e is best,
                }
                for e in [baseline] + others[:top_n]
            ],
        })

    sim = Simulation(SCENARIOS[scenario][1](), mode=mode)
    sim.event_hooks.append(on_disruption)
    for _ in range(topology.TOTAL_TICKS):
        sim.tick += 1
        sim._revert_expired_reassignments()
        sim._apply_disruptions()
        sim.finish_current_tick()

    return {
        "scenario": scenario,
        "title": SCENARIOS[scenario][0],
        "mode": mode,
        "engine": engine,
        "production_target_t": topology.PRODUCTION_TARGET_T,
        "final_production_if_nobody_acts_t": round(sim.cumulative_production_t, 1),
        "events": events,
    }
