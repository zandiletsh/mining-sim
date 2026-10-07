"""
Phase 2 demo: OpsBrain watching a live shift.

Runs the mine simulation tick by tick. Every time a disruption fires,
OpsBrain:
  1. Detects it (the sim calls our hook)
  2. Understands the current state    (opsbrain/context.py)
  3. Generates response options       (opsbrain/rules.py)
  4. Simulates each option forward    (opsbrain/consequences.py)
  5. Explains the trade-offs          (opsbrain/explain.py)

The real shift then continues on its own (accept-loss / no auto-action —
human-in-the-loop, per the project's design principle: OpsBrain informs,
a person decides).

Usage:
    python run_opsbrain.py [scenario] [mode] [engine]
    scenario: default | degradation | closure | combined | delay | double | none
    mode:     oversized | balanced
    engine:   rules (3 hand-picked options) | optimiser (searches them all)
    Defaults: combined / balanced / optimiser, since that's the scenario
    with all three disruption types to react to.
"""

import sys

from simulation import Simulation
import disruptions
import topology
from opsbrain.context import build_context, print_context
from opsbrain.rules import generate_options
from opsbrain.optimiser import generate_candidates
from opsbrain.consequences import evaluate_all
from opsbrain.explain import print_decision_table

ENGINES = {"rules": generate_options, "optimiser": generate_candidates}
ENGINE = "optimiser"


SCENARIOS = {
    "default": disruptions.default_scenario,
    "degradation": disruptions.degradation_scenario,
    "closure": disruptions.road_closure_scenario,
    "combined": disruptions.combined_scenario,
    "delay": disruptions.delay_scenario,
    "double": disruptions.double_scenario,
    "none": lambda: [],
}


def on_disruption(sim, fired):
    """Called once per tick with every event that started on that tick."""
    ctx = build_context(sim, fired)
    print_context(ctx)

    options = ENGINES[ENGINE](sim, fired)
    evaluations = evaluate_all(sim, options)
    print_decision_table(ctx, evaluations, top_n=3 if ENGINE == "optimiser" else None)


def main():
    global ENGINE
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "combined"
    mode = sys.argv[2] if len(sys.argv) > 2 else "balanced"
    ENGINE = sys.argv[3] if len(sys.argv) > 3 else "optimiser"
    if ENGINE not in ENGINES:
        sys.exit(f"Unknown engine '{ENGINE}'. Options: {list(ENGINES)}")

    scenario = SCENARIOS[scenario_name]()
    sim = Simulation(scenario, mode=mode)
    sim.event_hooks.append(on_disruption)

    print(f"OpsBrain watching shift — scenario: {scenario_name}, mode: {mode}, engine: {ENGINE}")
    sim.run()

    print(f"\n{'='*60}")
    print(f"SHIFT ENDED — actual production: {sim.cumulative_production_t:,.1f} t "
          f"({100*sim.cumulative_production_t/topology.PRODUCTION_TARGET_T:.1f}% of target)")
    print(f"(This run took no OpsBrain-recommended action — it shows the "
          f"'do nothing' baseline the options above were compared against.)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
