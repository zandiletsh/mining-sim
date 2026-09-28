"""
Disruption events (Part B, item 6).

Phase 1 ships three disruption types. Each is a plain dict describing
*what* happens and *when* — the Simulation class is responsible for
applying the effect. Keeping disruptions as data (not code scattered
through the sim loop) matters for Phase 2: OpsBrain will eventually need
to look at "what disruption is active" as a first-class fact, and later
you'll want to fire these from a scenario file instead of hardcoding them.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Disruption:
    disruption_type: str      # "TRUCK_BREAKDOWN" | "CRUSHER_DEGRADATION" | "ROAD_CLOSURE"
    trigger_tick: int
    target_id: str            # truck_id / crusher_id / route_id
    duration_min: Optional[int] = None   # None = until explicitly resolved
    severity_pct: Optional[float] = None  # for degradation: how much capacity is lost
    applied: bool = False
    resolved: bool = False
    remaining_min: Optional[int] = None   # countdown to auto-resolve; set at apply time


def default_scenario() -> list:
    """
    A minimal first scenario: one truck breakdown mid-shift.
    Add more Disruption objects here (or load from JSON later) to layer
    in crusher degradation / road closures once breakdown is validated.
    """
    return [
        Disruption(
            disruption_type="TRUCK_BREAKDOWN",
            trigger_tick=180,          # 3 hours into the shift
            # TRUCK_06 is the only truck feeding Crusher 2 in "balanced"
            # mode, so this fully cuts that crusher's supply, not just
            # thins it (still exists in "oversized" mode too).
            target_id="TRUCK_06",
            duration_min=180,          # 3 hour repair
        ),
    ]


def degradation_scenario() -> list:
    return [
        Disruption(
            disruption_type="CRUSHER_DEGRADATION",
            trigger_tick=240,
            target_id="CRUSHER_1",
            severity_pct=70.0,   # crusher loses 70% of effective capacity
            duration_min=240,
        ),
    ]


def road_closure_scenario() -> list:
    return [
        Disruption(
            disruption_type="ROAD_CLOSURE",
            trigger_tick=300,
            target_id="R1",
            duration_min=280,
        ),
    ]


def combined_scenario() -> list:
    """All three, spaced out, for stress-testing the full system at once."""
    return (
        default_scenario()
        + degradation_scenario()
        + road_closure_scenario()
    )
