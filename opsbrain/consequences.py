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
    clone = copy.deepcopy(sim)
    clone.event_hooks = []          # don't re-trigger OpsBrain inside the what-if
    option.apply(clone)

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
