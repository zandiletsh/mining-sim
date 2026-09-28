"""
Core data models for the mine simulation.

Every physical thing in the mine (truck, crusher, processing plant,
stockpile) is represented as a dataclass with a shared `AssetState`
vocabulary. This is deliberate: OpsBrain (Phase 2+) will reason over
whatever states and fields exist here, so keep this the single source
of truth for "what a thing is and what state it can be in."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AssetState(str, Enum):
    AVAILABLE = "AVAILABLE"      # idle and ready to be assigned work
    RUNNING = "RUNNING"          # actively working (hauling, crushing, processing)
    IDLE = "IDLE"                # available but currently has no work assigned
    MAINTENANCE = "MAINTENANCE"  # undergoing scheduled or breakdown repair
    FAILED = "FAILED"            # broken down, awaiting maintenance to begin


class RouteStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class OperationalRecord:
    """One row of the operational data log, emitted every tick per asset."""
    tick: int
    sim_minutes_elapsed: int
    asset_id: str
    asset_type: str          # "truck" | "crusher" | "processing" | "stockpile"
    state: str
    location: str
    capacity: float
    current_load: float
    throughput_actual: float
    health: float
    fuel: Optional[float]
    utilisation: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Truck:
    asset_id: str
    capacity_t: float
    speed_kmph: float
    fuel_burn_per_km: float
    route_id: Optional[str] = None
    state: AssetState = AssetState.AVAILABLE
    location: str = "PIT_LOADING"  # "PIT_LOADING" | "HAUL_LOADED" | "CRUSHER_DUMPING" | "HAUL_EMPTY"
    fuel_pct: float = 100.0
    health_pct: float = 100.0
    cargo_t: float = 0.0
    cycle_time_remaining_min: float = 0.0
    running_minutes: int = 0       # for utilisation calc
    maintenance_minutes_remaining: int = 0
    failed_ticks_remaining: int = 0  # detection/dispatch delay before repair starts

    def utilisation(self, elapsed_minutes: int) -> float:
        if elapsed_minutes <= 0:
            return 0.0
        return round(100 * self.running_minutes / elapsed_minutes, 1)


@dataclass
class Crusher:
    asset_id: str
    capacity_tph: float                # tonnes/hour at full health
    location: str
    state: AssetState = AssetState.AVAILABLE
    health_pct: float = 100.0
    queue_t: float = 0.0               # material waiting to be crushed
    output_t_this_tick: float = 0.0
    cumulative_output_t: float = 0.0
    running_minutes: int = 0
    maintenance_minutes_remaining: int = 0

    def effective_capacity_tph(self) -> float:
        """Degradation reduces effective throughput, not just a binary on/off."""
        return self.capacity_tph * (self.health_pct / 100.0)

    def utilisation(self, elapsed_minutes: int) -> float:
        if elapsed_minutes <= 0:
            return 0.0
        return round(100 * self.running_minutes / elapsed_minutes, 1)


@dataclass
class Stockpile:
    asset_id: str
    capacity_t: float
    location: str
    current_t: float = 0.0

    def pct_full(self) -> float:
        return round(100 * self.current_t / self.capacity_t, 1)


@dataclass
class ProcessingPlant:
    asset_id: str
    capacity_tph: float
    location: str
    state: AssetState = AssetState.AVAILABLE
    health_pct: float = 100.0
    output_t_this_tick: float = 0.0
    cumulative_output_t: float = 0.0
    running_minutes: int = 0

    def effective_capacity_tph(self) -> float:
        return self.capacity_tph * (self.health_pct / 100.0)

    def utilisation(self, elapsed_minutes: int) -> float:
        if elapsed_minutes <= 0:
            return 0.0
        return round(100 * self.running_minutes / elapsed_minutes, 1)


@dataclass
class Route:
    route_id: str
    from_pit: str
    to_crusher: str
    distance_km: float
    status: RouteStatus = RouteStatus.OPEN

    def one_way_minutes(self, speed_kmph: float) -> float:
        return (self.distance_km / speed_kmph) * 60.0
