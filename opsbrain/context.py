"""
Objective 3 — Understand.

Builds a plain snapshot of "what's going on right now" the moment a
disruption fires. This is what a control-room operator would want to
see first: what broke, and what the rest of the operation looks like
at that instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import topology
from disruptions import Disruption


@dataclass
class Context:
    tick: int
    shift_minutes_elapsed: int
    shift_minutes_remaining: int
    disruption_type: str
    disruption_target: str
    disruption_duration_min: Optional[int]
    production_so_far_t: float
    production_target_t: float
    pct_of_target_so_far: float
    stockpile_levels: dict          # asset_id -> pct full
    truck_states: dict              # asset_id -> (state, route_id)
    crusher_health: dict            # asset_id -> health_pct


def build_context(sim, disruption: Disruption) -> Context:
    elapsed = sim.tick * topology.TICK_MINUTES
    remaining = topology.SHIFT_MINUTES - elapsed

    return Context(
        tick=sim.tick,
        shift_minutes_elapsed=elapsed,
        shift_minutes_remaining=remaining,
        disruption_type=disruption.disruption_type,
        disruption_target=disruption.target_id,
        disruption_duration_min=disruption.duration_min,
        production_so_far_t=round(sim.cumulative_production_t, 1),
        production_target_t=topology.PRODUCTION_TARGET_T,
        pct_of_target_so_far=round(
            100 * sim.cumulative_production_t / topology.PRODUCTION_TARGET_T, 1
        ),
        stockpile_levels={s.asset_id: s.pct_full() for s in sim.stockpiles.values()},
        truck_states={t.asset_id: (t.state.value, t.route_id) for t in sim.trucks.values()},
        crusher_health={c.asset_id: c.health_pct for c in sim.crushers.values()},
    )


def print_context(ctx: Context):
    print(f"\n{'-'*60}")
    print(f"EVENT DETECTED  (tick {ctx.tick}, {ctx.shift_minutes_elapsed} min into shift)")
    print(f"{'-'*60}")
    print(f"{ctx.disruption_type} on {ctx.disruption_target}"
          + (f" (expected {ctx.disruption_duration_min} min)" if ctx.disruption_duration_min else ""))
    print(f"Production so far: {ctx.production_so_far_t:,.1f} t "
          f"({ctx.pct_of_target_so_far}% of {ctx.production_target_t:,.0f} t target)")
    print(f"Shift time left:   {ctx.shift_minutes_remaining} min")
    print("Stockpiles: " + ", ".join(f"{k}={v}%" for k, v in ctx.stockpile_levels.items()))
    print("Trucks:     " + ", ".join(f"{k}={s}/{r}" for k, (s, r) in ctx.truck_states.items()))
    print("Crushers:   " + ", ".join(f"{k}={h}%health" for k, h in ctx.crusher_health.items()))
