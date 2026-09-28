"""
Defines the mine layout and normal operating conditions (Part A + the
"normal operating conditions" half of Part B).

    Pit A ─┐
           ├─ R1 ─→ Crusher 1 ─┐
    Pit B ─┤                   ├─→ Stockpile (post-crush) ─→ Processing
           └─ R3 ─→ Crusher 2 ─┘
    (R2: Pit B -> Crusher 1, gives Pit B a routing choice)

Change constants here to retune the whole mine without touching
simulation logic.
"""

from models import Truck, Crusher, ProcessingPlant, Stockpile, Route

# --- Shift parameters -------------------------------------------------
SHIFT_MINUTES = 720          # 12-hour shift
TICK_MINUTES = 1             # 1 sim-minute per tick
TOTAL_TICKS = SHIFT_MINUTES // TICK_MINUTES
PRODUCTION_TARGET_T = 5000.0  # tonnes/shift, measured at processing output

# --- Load/dump fixed times (per truck, independent of route distance) -
LOAD_TIME_MIN = 6.0
DUMP_TIME_MIN = 3.0

# --- Routes -------------------------------------------------------------
ROUTES = {
    "R1": Route(route_id="R1", from_pit="PIT_A", to_crusher="CRUSHER_1", distance_km=4.5),
    "R2": Route(route_id="R2", from_pit="PIT_B", to_crusher="CRUSHER_1", distance_km=6.0),
    "R3": Route(route_id="R3", from_pit="PIT_B", to_crusher="CRUSHER_2", distance_km=3.0),
}

# --- Trucks -----------------------------------------------------------
# Two fleet sizes:
#   "oversized" (old, default) = 7 trucks -> buffers absorb most disruptions
#   "balanced"  (new)          = 5 trucks -> trucks are the bottleneck,
#                                 so a breakdown actually costs production
FLEET_SPECS = {
    "oversized": [
        ("TRUCK_01", "R1"), ("TRUCK_02", "R1"), ("TRUCK_03", "R1"),
        ("TRUCK_04", "R2"), ("TRUCK_05", "R2"),
        ("TRUCK_06", "R3"), ("TRUCK_07", "R3"),
    ],
    # One truck per route: each crusher's main feed now depends on a
    # single truck, so losing that truck (or closing its road) really
    # cuts supply, instead of other trucks quietly covering for it.
    "balanced": [
        ("TRUCK_01", "R1"),
        ("TRUCK_04", "R2"),
        ("TRUCK_06", "R3"),
    ],
}


def build_trucks(mode: str = "oversized") -> dict:
    trucks = {}
    for truck_id, route_id in FLEET_SPECS[mode]:
        trucks[truck_id] = Truck(
            asset_id=truck_id,
            capacity_t=90.0,
            speed_kmph=35.0,
            fuel_burn_per_km=0.9,
            route_id=route_id,
            cycle_time_remaining_min=LOAD_TIME_MIN,
        )
    return trucks


# --- Crushers -------------------------------------------------------------
def build_crushers() -> dict:
    return {
        "CRUSHER_1": Crusher(asset_id="CRUSHER_1", capacity_tph=450.0, location="CRUSHER_1"),
        "CRUSHER_2": Crusher(asset_id="CRUSHER_2", capacity_tph=250.0, location="CRUSHER_2"),
    }


# --- Stockpiles -------------------------------------------------------------
# One pre-crush buffer per crusher (so a crusher-specific disruption shows up
# clearly as its own buffer filling), one shared post-crush buffer feeding
# the single processing plant.
#
# "oversized" mode uses big buffers -> they soak up almost any disruption.
# "balanced" mode uses much smaller buffers, started half-full: there's
# only a thin cushion, so a real disruption drains it and production
# actually drops, instead of the buffer quietly covering for it.
STOCKPILE_SPECS = {
    "oversized": {
        "STOCKPILE_PRE_C1": 1200.0,
        "STOCKPILE_PRE_C2": 800.0,
        "STOCKPILE_POST": 3000.0,
    },
    "balanced": {
        "STOCKPILE_PRE_C1": 250.0,
        "STOCKPILE_PRE_C2": 150.0,
        "STOCKPILE_POST": 350.0,
    },
}


def build_stockpiles(mode: str = "oversized") -> dict:
    specs = STOCKPILE_SPECS[mode]
    locations = {
        "STOCKPILE_PRE_C1": "PRE_CRUSHER_1",
        "STOCKPILE_PRE_C2": "PRE_CRUSHER_2",
        "STOCKPILE_POST": "POST_CRUSH",
    }
    start_pct = 0.3 if mode == "balanced" else 0.0
    return {
        asset_id: Stockpile(
            asset_id=asset_id,
            capacity_t=cap,
            location=locations[asset_id],
            current_t=cap * start_pct,
        )
        for asset_id, cap in specs.items()
    }


PRE_STOCKPILE_FOR_CRUSHER = {
    "CRUSHER_1": "STOCKPILE_PRE_C1",
    "CRUSHER_2": "STOCKPILE_PRE_C2",
}


# --- Processing plant -------------------------------------------------------
def build_processing() -> ProcessingPlant:
    return ProcessingPlant(asset_id="PROCESSING_1", capacity_tph=500.0, location="PROCESSING")


# --- Availability target (used for validation, not enforced directly) -----
AVAILABILITY_TARGET_PCT = 85.0
