"""
Objective 4 — Decide (smarter version).

The rules in rules.py look at 2-3 hand-picked ideas. This module instead
searches: it lists every allowed way to re-deploy the fleet, simulates
each one forward to the end of the shift, and keeps whichever gives the
most production. Same simulator, same Option shape, so the rest of
OpsBrain (consequences, explain) works unchanged.

Constraints (the "constraints" step from the project plan):
  - Only healthy trucks can be moved (not failed, not in maintenance)
  - Trucks can only go to routes that are open
  - At most MAX_TRUCKS_MOVED trucks are moved (a dispatcher can't
    reshuffle the whole fleet at once)
  - No route gets more crowded than MAX_TRUCKS_PER_ROUTE, or than the
    busiest route already is (road spacing and loading-bay safety)

Each move is tried for two lengths of time: until the disruption is
over, or for the rest of the shift.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import List

from models import AssetState, RouteStatus
import topology
from disruptions import Disruption
from opsbrain.rules import Option, _accept_loss_option, expected_end_tick

MAX_TRUCKS_MOVED = 2
MAX_TRUCKS_PER_ROUTE = 2


def _movable_trucks(sim) -> List[str]:
    return [
        t.asset_id for t in sim.trucks.values()
        if t.state not in (AssetState.FAILED, AssetState.MAINTENANCE)
    ]


def _open_routes(sim) -> List[str]:
    return [r.route_id for r in sim.routes.values() if r.status == RouteStatus.OPEN]


def _route_load_after(sim, moves: dict) -> dict:
    """How many trucks would be on each route if `moves` were applied."""
    load = {r: 0 for r in sim.routes}
    for t in sim.trucks.values():
        load[moves.get(t.asset_id, t.route_id)] += 1
    return load


def _label(moves: dict, horizon_name: str) -> str:
    parts = ", ".join(f"{t} -> {r}" for t, r in moves.items())
    return f"Move {parts} ({horizon_name})"


def generate_candidates(sim, disruptions) -> List[Option]:
    """
    Accept-loss plus every allowed fleet re-deployment. `disruptions` is
    everything that started this tick; the search looks at the whole mine
    as it is now, so several events at once are handled together.
    """
    if isinstance(disruptions, Disruption):
        disruptions = [disruptions]
    options = [_accept_loss_option()]

    until_repair = max(expected_end_tick(sim, d) for d in disruptions)
    horizons = [("until the disruption is over", until_repair)]
    if until_repair < topology.TOTAL_TICKS:
        horizons.append(("for the rest of the shift", topology.TOTAL_TICKS + 1))

    movable = _movable_trucks(sim)
    routes = _open_routes(sim)

    # No route may get more crowded than MAX_TRUCKS_PER_ROUTE, or than the
    # busiest route already is today (the big fleet starts with 3 on R1).
    route_cap = max(MAX_TRUCKS_PER_ROUTE, max(_route_load_after(sim, {}).values()))

    for n_moved in range(1, MAX_TRUCKS_MOVED + 1):
        for trucks in combinations(movable, n_moved):
            # each chosen truck goes to an open route other than its current one
            choices = [[r for r in routes if r != sim.trucks[t].route_id] for t in trucks]
            for destinations in product(*choices):
                moves = dict(zip(trucks, destinations))
                if max(_route_load_after(sim, moves).values()) > route_cap:
                    continue
                for horizon_name, until_tick in horizons:
                    options.append(_make_option(moves, horizon_name, until_tick))
    return options


def _make_option(moves: dict, horizon_name: str, until_tick: int) -> Option:
    def apply(sim, moves=dict(moves), until_tick=until_tick):
        for truck_id, route_id in moves.items():
            sim.reassign_truck(truck_id, route_id, until_tick)

    key = "_".join(f"{t}_to_{r}" for t, r in moves.items())
    return Option(
        option_id=f"move_{key}_{until_tick}",
        label=_label(moves, horizon_name),
        description=(
            "Move " + " and ".join(f"{t} onto {r}" for t, r in moves.items())
            + f" {horizon_name}. The trucks' old routes lose that coverage."
        ),
        apply=apply,
        complexity=len(moves),
    )
