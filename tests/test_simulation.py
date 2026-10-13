"""Checks that the forecasts OpsBrain makes come true, and the optimiser is never worse than the rules."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import disruptions
from simulation import Simulation
from opsbrain.rules import generate_options
from opsbrain.optimiser import generate_candidates
from opsbrain.consequences import evaluate_all, pick_best

SCENARIOS = {
    "combined": disruptions.combined_scenario,
    "delay": disruptions.delay_scenario,
    "double": disruptions.double_scenario,
}


def _first_event_forecast(name):
    seen = []

    def hook(sim, fired):
        if seen:
            return
        rules = evaluate_all(sim, generate_options(sim, fired))
        opt = evaluate_all(sim, generate_candidates(sim, fired))
        base = next(e for e in opt if e.option.option_id == "accept_loss")
        seen.append((base.final_production_t, pick_best(rules).final_production_t,
                     pick_best(opt).final_production_t))

    sim = Simulation(SCENARIOS[name](), mode="balanced")
    sim.event_hooks.append(hook)
    sim.run()
    return seen[0], round(sim.cumulative_production_t, 1)


@pytest.mark.parametrize("name", SCENARIOS)
def test_forecast_matches_what_really_happens(name):
    (forecast, _, _), actual = _first_event_forecast(name)
    assert forecast == actual


@pytest.mark.parametrize("name", SCENARIOS)
def test_optimiser_never_worse_than_rules(name):
    (_, rules_best, opt_best), _ = _first_event_forecast(name)
    assert opt_best >= rules_best


def test_delay_keeps_the_truck_down_longer():
    with_delay = Simulation(disruptions.delay_scenario(), mode="balanced")
    with_delay.run()
    without = Simulation([disruptions.delay_scenario()[0]], mode="balanced")
    without.run()
    assert with_delay.cumulative_production_t < without.cumulative_production_t
