"""
The simulation engine (Part C, items 9-13).

Discrete-tick loop, 1 sim-minute per tick. Each tick:
  1. apply/resolve any due disruptions
  2. advance every truck through its haul cycle
  3. advance crushers (pull from pre-crush stockpile, push to post-crush)
  4. advance processing plant (pull from post-crush stockpile, produce)
  5. record an OperationalRecord snapshot for every asset

Material flow is the thing to watch when validating: a disruption should
show up as (a) reduced truck/crusher throughput, (b) a stockpile filling
or draining abnormally, and (c) cumulative production falling behind
PRODUCTION_TARGET_T. If any of those three don't move when you inject a
disruption, something in this loop is wrong.
"""

from __future__ import annotations

import csv
from typing import List

from models import AssetState, RouteStatus, OperationalRecord
import topology
from disruptions import Disruption

# Fixed delay between a truck failing and a mechanic actually starting
# work on it -- gives OpsBrain (later) a "detected but not yet acted on"
# window that's realistic, not just decorative.
FAILED_DISPATCH_DELAY_MIN = 5


class Simulation:
    def __init__(self, scenario: List[Disruption], mode: str = "oversized"):
        self.tick = 0
        self.mode = mode
        self.trucks = topology.build_trucks(mode)
        self.crushers = topology.build_crushers()
        self.stockpiles = topology.build_stockpiles(mode)
        self.processing = topology.build_processing()
        self.routes = topology.ROUTES
        self.scenario = scenario
        self.records: List[OperationalRecord] = []
        self.cumulative_production_t = 0.0

        # OpsBrain (Phase 2) registers callbacks here. Called the tick a
        # disruption activates, as (sim, disruption). Left empty, the sim
        # runs exactly as it did in Phase 1.
        self.event_hooks: List = []

    # ------------------------------------------------------------------
    def reassign_truck(self, truck_id: str, new_route_id: str, until_tick: int):
        """
        Temporarily move a truck onto a different route (OpsBrain's
        "reassign equipment" decision). The truck reverts to its normal
        route once `until_tick` passes.
        """
        truck = self.trucks[truck_id]
        if truck.original_route_id is None:
            truck.original_route_id = truck.route_id
        truck.route_id = new_route_id
        truck.reassigned_until_tick = until_tick

    def _revert_expired_reassignments(self):
        for truck in self.trucks.values():
            if (truck.reassigned_until_tick is not None
                    and self.tick >= truck.reassigned_until_tick):
                truck.route_id = truck.original_route_id
                truck.original_route_id = None
                truck.reassigned_until_tick = None

    # ------------------------------------------------------------------
    def run(self, total_ticks: int = topology.TOTAL_TICKS):
        for _ in range(total_ticks):
            self.tick += 1
            self._revert_expired_reassignments()
            self._apply_disruptions()
            self.finish_current_tick()
        return self.records

    def finish_current_tick(self):
        """
        Move the machines for the tick that is in progress. OpsBrain's hooks
        fire part-way through a tick (events are applied, machines have not
        moved yet), so a what-if copy calls this first to carry on from the
        same point the real shift does.
        """
        self._update_trucks()
        self._update_crushers()
        self._update_processing()
        self._log_tick()

    # ------------------------------------------------------------------
    def _apply_disruptions(self):
        fired = []  # everything that started this tick, so OpsBrain can decide on it together
        for d in self.scenario:
            if d.resolved:
                continue

            if not d.applied and self.tick == d.trigger_tick:
                had_effect = self._activate_disruption(d)
                d.applied = True
                d.remaining_min = d.duration_min
                if had_effect:
                    fired.append(d)

            elif d.applied and d.remaining_min is not None:
                d.remaining_min -= topology.TICK_MINUTES
                if d.remaining_min <= 0:
                    self._resolve_disruption(d)
                    d.resolved = True

        if fired:
            for hook in self.event_hooks:
                hook(self, fired)

    def _activate_disruption(self, d: Disruption) -> bool:
        """Apply the disruption. Returns False if it changed nothing."""
        if d.disruption_type == "TRUCK_BREAKDOWN":
            truck = self.trucks[d.target_id]
            truck.state = AssetState.FAILED
            truck.failed_ticks_remaining = FAILED_DISPATCH_DELAY_MIN
            truck.maintenance_minutes_remaining = d.duration_min or 0

        elif d.disruption_type == "MAINTENANCE_DELAY":
            # Repair takes longer than planned (parts late, no mechanic free).
            # Only means something for a truck that is already down.
            truck = self.trucks[d.target_id]
            if truck.state not in (AssetState.FAILED, AssetState.MAINTENANCE):
                return False
            truck.maintenance_minutes_remaining += d.duration_min or 0

        elif d.disruption_type == "CRUSHER_DEGRADATION":
            crusher = self.crushers[d.target_id]
            crusher.health_pct = max(0.0, crusher.health_pct - (d.severity_pct or 0))

        elif d.disruption_type == "ROAD_CLOSURE":
            route = self.routes[d.target_id]
            route.status = RouteStatus.CLOSED

        return True

    def _resolve_disruption(self, d: Disruption):
        if d.disruption_type == "CRUSHER_DEGRADATION":
            crusher = self.crushers[d.target_id]
            crusher.health_pct = min(100.0, crusher.health_pct + (d.severity_pct or 0))

        elif d.disruption_type == "ROAD_CLOSURE":
            route = self.routes[d.target_id]
            route.status = RouteStatus.OPEN
        # TRUCK_BREAKDOWN resolves itself via the failed/maintenance
        # countdown in _update_trucks, not here.

    # ------------------------------------------------------------------
    def _update_trucks(self):
        for truck in self.trucks.values():
            route = self.routes[truck.route_id]

            if truck.state == AssetState.FAILED:
                truck.failed_ticks_remaining -= topology.TICK_MINUTES
                if truck.failed_ticks_remaining <= 0:
                    truck.state = AssetState.MAINTENANCE
                continue

            if truck.state == AssetState.MAINTENANCE:
                truck.maintenance_minutes_remaining -= topology.TICK_MINUTES
                if truck.maintenance_minutes_remaining <= 0:
                    truck.state = AssetState.AVAILABLE
                    truck.health_pct = 100.0
                    truck.fuel_pct = 100.0
                    truck.cargo_t = 0.0
                    truck.location = "PIT_LOADING"
                    truck.cycle_time_remaining_min = topology.LOAD_TIME_MIN
                continue

            if truck.location == "PIT_LOADING":
                if route.status == RouteStatus.CLOSED:
                    truck.state = AssetState.IDLE
                    continue
                truck.state = AssetState.RUNNING
                truck.running_minutes += topology.TICK_MINUTES
                truck.cycle_time_remaining_min -= topology.TICK_MINUTES
                if truck.cycle_time_remaining_min <= 0:
                    truck.cargo_t = truck.capacity_t
                    truck.location = "HAUL_LOADED"
                    truck.cycle_time_remaining_min = route.one_way_minutes(truck.speed_kmph)

            elif truck.location == "HAUL_LOADED":
                truck.state = AssetState.RUNNING
                truck.running_minutes += topology.TICK_MINUTES
                truck.fuel_pct = max(0.0, truck.fuel_pct - truck.fuel_burn_per_km * 0.5)
                truck.cycle_time_remaining_min -= topology.TICK_MINUTES
                if truck.cycle_time_remaining_min <= 0:
                    truck.location = "CRUSHER_DUMPING"
                    truck.cycle_time_remaining_min = topology.DUMP_TIME_MIN

            elif truck.location == "CRUSHER_DUMPING":
                truck.state = AssetState.RUNNING
                truck.running_minutes += topology.TICK_MINUTES
                pre_stockpile = self.stockpiles[
                    topology.PRE_STOCKPILE_FOR_CRUSHER[route.to_crusher]
                ]
                room = pre_stockpile.capacity_t - pre_stockpile.current_t
                deposit = min(truck.cargo_t, room)
                pre_stockpile.current_t += deposit
                truck.cargo_t -= deposit

                if truck.cargo_t > 0:
                    # Pre-crush stockpile is full: truck is backed up and
                    # cannot finish dumping. This is the backpressure signal.
                    continue

                truck.cycle_time_remaining_min -= topology.TICK_MINUTES
                if truck.cycle_time_remaining_min <= 0:
                    truck.location = "HAUL_EMPTY"
                    truck.cycle_time_remaining_min = route.one_way_minutes(truck.speed_kmph)

            elif truck.location == "HAUL_EMPTY":
                truck.state = AssetState.RUNNING
                truck.running_minutes += topology.TICK_MINUTES
                truck.fuel_pct = max(0.0, truck.fuel_pct - truck.fuel_burn_per_km * 0.5)
                truck.cycle_time_remaining_min -= topology.TICK_MINUTES
                if truck.cycle_time_remaining_min <= 0:
                    truck.location = "PIT_LOADING"
                    truck.cycle_time_remaining_min = topology.LOAD_TIME_MIN

    # ------------------------------------------------------------------
    def _update_crushers(self):
        post = self.stockpiles["STOCKPILE_POST"]
        for crusher in self.crushers.values():
            pre = self.stockpiles[topology.PRE_STOCKPILE_FOR_CRUSHER[crusher.asset_id]]

            eff_cap_per_tick = crusher.effective_capacity_tph() / 60.0 * topology.TICK_MINUTES
            processed = min(eff_cap_per_tick, pre.current_t)
            pre.current_t -= processed

            room = post.capacity_t - post.current_t
            deposited = min(processed, room)  # overflow (deposited < processed) = lost material
            post.current_t += deposited

            crusher.output_t_this_tick = deposited
            crusher.cumulative_output_t += deposited
            crusher.queue_t = pre.current_t

            if processed > 0:
                crusher.state = AssetState.RUNNING
                crusher.running_minutes += topology.TICK_MINUTES
            else:
                crusher.state = AssetState.AVAILABLE

    # ------------------------------------------------------------------
    def _update_processing(self):
        post = self.stockpiles["STOCKPILE_POST"]
        eff_cap_per_tick = self.processing.effective_capacity_tph() / 60.0 * topology.TICK_MINUTES
        processed = min(eff_cap_per_tick, post.current_t)
        post.current_t -= processed

        self.processing.output_t_this_tick = processed
        self.processing.cumulative_output_t += processed
        self.cumulative_production_t += processed

        if processed > 0:
            self.processing.state = AssetState.RUNNING
            self.processing.running_minutes += topology.TICK_MINUTES
        else:
            self.processing.state = AssetState.AVAILABLE

    # ------------------------------------------------------------------
    def _log_tick(self):
        elapsed = self.tick * topology.TICK_MINUTES

        for t in self.trucks.values():
            self.records.append(OperationalRecord(
                tick=self.tick, sim_minutes_elapsed=elapsed,
                asset_id=t.asset_id, asset_type="truck", state=t.state.value,
                location=t.location, capacity=t.capacity_t, current_load=t.cargo_t,
                throughput_actual=t.cargo_t if t.location == "CRUSHER_DUMPING" else 0.0,
                health=t.health_pct, fuel=round(t.fuel_pct, 1),
                utilisation=t.utilisation(elapsed),
            ))

        for c in self.crushers.values():
            self.records.append(OperationalRecord(
                tick=self.tick, sim_minutes_elapsed=elapsed,
                asset_id=c.asset_id, asset_type="crusher", state=c.state.value,
                location=c.location, capacity=c.capacity_tph, current_load=c.queue_t,
                throughput_actual=round(c.output_t_this_tick, 2),
                health=c.health_pct, fuel=None,
                utilisation=c.utilisation(elapsed),
            ))

        p = self.processing
        self.records.append(OperationalRecord(
            tick=self.tick, sim_minutes_elapsed=elapsed,
            asset_id=p.asset_id, asset_type="processing", state=p.state.value,
            location=p.location, capacity=p.capacity_tph, current_load=0.0,
            throughput_actual=round(p.output_t_this_tick, 2),
            health=p.health_pct, fuel=None,
            utilisation=p.utilisation(elapsed),
        ))

        for s in self.stockpiles.values():
            self.records.append(OperationalRecord(
                tick=self.tick, sim_minutes_elapsed=elapsed,
                asset_id=s.asset_id, asset_type="stockpile", state="N/A",
                location=s.location, capacity=s.capacity_t, current_load=round(s.current_t, 2),
                throughput_actual=0.0, health=100.0, fuel=None,
                utilisation=s.pct_full(),
            ))

    # ------------------------------------------------------------------
    def write_csv(self, path: str):
        if not self.records:
            return
        fieldnames = list(self.records[0].as_dict().keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.records:
                writer.writerow(r.as_dict())
