"""
Objective 4 — Decide.

Simple if/then rules (no ML/optimisation yet — that's a later phase).
Given a disruption, produce a short list of feasible response options.
Every option is one of:

  - "accept_loss"     do nothing, let the disruption run its course
  - "reassign_truck"  move a healthy truck onto the affected route/crusher
                       for the duration of the disruption

Each option carries an `apply` function that mutates a Simulation in
place — the consequence simulator (consequences.py) clones the sim and
calls `apply` on the clone, so trying an option never touches the real run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from models import AssetState
import topology
from disruptions import Disruption


@dataclass
class Option:
    option_id: str
    label: str
    description: str
    apply: Callable  # apply(sim) -> None, called once on a cloned sim


def _routes_feeding(crusher_id: str) -> List[str]:
    return [r.route_id for r in topology.ROUTES.values() if r.to_crusher == crusher_id]


def _other_crusher(crusher_id: str) -> str:
    others = [c for c in topology.build_crushers().keys() if c != crusher_id]
    return others[0]


def _truck_on_route(sim, route_id: str) -> Optional[str]:
    for t in sim.trucks.values():
        if t.route_id == route_id and t.state not in (AssetState.FAILED, AssetState.MAINTENANCE):
            return t.asset_id
    return None


def _idle_or_spare_trucks(sim, exclude_route: str) -> List[str]:
    """Trucks not on the affected route and not already broken down."""
    return [
        t.asset_id for t in sim.trucks.values()
        if t.route_id != exclude_route and t.state not in (AssetState.FAILED, AssetState.MAINTENANCE)
    ]


def _accept_loss_option() -> Option:
    return Option(
        option_id="accept_loss",
        label="Accept the loss",
        description="Take no action. The affected asset stays down until repaired/resolved on its own schedule.",
        apply=lambda sim: None,
    )


def _reassign_option(source_truck_id: str, target_route_id: str, until_tick: int, reason: str) -> Option:
    return Option(
        option_id=f"reassign_{source_truck_id}_to_{target_route_id}",
        label=f"Reassign {source_truck_id} to {target_route_id}",
        description=reason,
        apply=lambda sim: sim.reassign_truck(source_truck_id, target_route_id, until_tick),
    )


def generate_options(sim, disruption: Disruption) -> List[Option]:
    options = [_accept_loss_option()]
    until_tick = sim.tick + (disruption.duration_min or 0)

    if disruption.disruption_type == "TRUCK_BREAKDOWN":
        broken_truck = sim.trucks[disruption.target_id]
        affected_route = broken_truck.original_route_id or broken_truck.route_id
        candidates = _idle_or_spare_trucks(sim, exclude_route=affected_route)
        for candidate_id in candidates[:2]:
            options.append(_reassign_option(
                candidate_id, affected_route, until_tick,
                f"Pull {candidate_id} off its normal route to cover {affected_route} "
                f"while {disruption.target_id} is down. Its old route loses coverage instead."
            ))

    elif disruption.disruption_type == "CRUSHER_DEGRADATION":
        degraded = disruption.target_id
        healthy = _other_crusher(degraded)
        healthy_routes = _routes_feeding(healthy)
        degraded_routes = _routes_feeding(degraded)
        for route_from in degraded_routes:
            truck_id = _truck_on_route(sim, route_from)
            if truck_id is None:
                continue
            for route_to in healthy_routes[:1]:
                options.append(_reassign_option(
                    truck_id, route_to, until_tick,
                    f"Shift {truck_id} from {route_from} (feeding the degraded crusher) "
                    f"to {route_to} (feeding the healthy crusher, which has spare capacity)."
                ))

    elif disruption.disruption_type == "ROAD_CLOSURE":
        closed_route = disruption.target_id
        stuck_truck = _truck_on_route(sim, closed_route)
        if stuck_truck:
            other_routes = [r for r in topology.ROUTES if r != closed_route]
            for alt_route in other_routes[:2]:
                options.append(_reassign_option(
                    stuck_truck, alt_route, until_tick,
                    f"Redirect {stuck_truck} to {alt_route} while {closed_route} is closed, "
                    f"instead of letting it sit idle."
                ))

    return options[:3]  # cap at 3, matching the project's demo shape
