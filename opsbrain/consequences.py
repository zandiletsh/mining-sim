"""
Objective 5 — Simulate.

For each option, run a full copy of the mine forward from right now to
the end of the shift, apply that one option, and see what total
production comes out. This is literally "what-if": the clone shares
everything that already happened, then diverges by exactly one decision.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List

import topology
from opsbrain.rules import Option


@dataclass
class Evaluation:
    option: Option
    final_production_t: float
    production_vs_target_pct: float
    crusher_health_end: dict
    stockpile_pct_end: dict


def evaluate_option(sim, option: Option) -> Evaluation:
    # The history log isn't needed for a what-if and is slow to copy.
    history, sim.records = sim.records, []
    try:
        clone = copy.deepcopy(sim)
    finally:
        sim.records = history
    clone.event_hooks = []          # don't re-trigger OpsBrain inside the what-if
    option.apply(clone)

    # The hook fired part-way through this tick; finish it, then run the rest.
    clone.finish_current_tick()
    remaining_ticks = topology.TOTAL_TICKS - clone.tick
    clone.run(total_ticks=remaining_ticks)

    return Evaluation(
        option=option,
        final_production_t=round(clone.cumulative_production_t, 1),
        production_vs_target_pct=round(
            100 * clone.cumulative_production_t / topology.PRODUCTION_TARGET_T, 1
        ),
        crusher_health_end={c.asset_id: c.health_pct for c in clone.crushers.values()},
        stockpile_pct_end={s.asset_id: s.pct_full() for s in clone.stockpiles.values()},
    )


def evaluate_all(sim, options: List[Option]) -> List[Evaluation]:
    return [evaluate_option(sim, opt) for opt in options]


MIN_WORTH_ACTING_T = 1.0  # a gain smaller than this isn't worth disturbing the fleet


def pick_best(evaluations: List[Evaluation]) -> Evaluation:
    """
    Highest final production wins. Ties go to the simpler option (fewer
    trucks moved). If nothing beats doing nothing by at least
    MIN_WORTH_ACTING_T, the answer is to accept the loss.
    """
    baseline = next(e for e in evaluations if e.option.option_id == "accept_loss")
    best = min(evaluations, key=lambda e: (-e.final_production_t, e.option.complexity))
    if best.final_production_t - baseline.final_production_t < MIN_WORTH_ACTING_T:
        return baseline
    return best
