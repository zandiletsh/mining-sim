"""
Run one 12-hour shift with the default disruption scenario (a single
truck breakdown), write the full operational data log to CSV, and print
a validation summary so you can eyeball whether the simulation behaves
logically (Part C, items 12-13).

Usage:
    python main.py [scenario] [mode]

    scenario: default | degradation | closure | combined | delay | double | none
    mode:     oversized (old, 7 trucks, empty buffers - default)
              balanced  (new, 5 trucks, half-full buffers)

Examples:
    python main.py default balanced     # truck breakdown, balanced mine
    python main.py none oversized       # baseline, old setup
"""

import sys

from simulation import Simulation
import disruptions
import topology


SCENARIOS = {
    "default": disruptions.default_scenario,
    "degradation": disruptions.degradation_scenario,
    "closure": disruptions.road_closure_scenario,
    "combined": disruptions.combined_scenario,
    "delay": disruptions.delay_scenario,
    "double": disruptions.double_scenario,
    "none": lambda: [],
}


def summarize(sim: Simulation, scenario_name: str):
    target = topology.PRODUCTION_TARGET_T
    actual = sim.cumulative_production_t
    pct_of_target = round(100 * actual / target, 1)

    print(f"\n{'='*60}")
    print(f"SHIFT SUMMARY — scenario: {scenario_name}  |  mode: {sim.mode}")
    print(f"{'='*60}")
    print(f"Shift length:        {topology.SHIFT_MINUTES} min ({topology.SHIFT_MINUTES/60:.0f} hrs)")
    print(f"Production target:   {target:,.0f} t")
    print(f"Production actual:   {actual:,.1f} t  ({pct_of_target}% of target)")

    print(f"\n{'Truck':<10} {'Final state':<12} {'Utilisation %':<14}")
    for t in sim.trucks.values():
        print(f"{t.asset_id:<10} {t.state.value:<12} {t.utilisation(topology.SHIFT_MINUTES):<14}")

    print(f"\n{'Crusher':<12} {'Health %':<10} {'Cumulative t':<14} {'Utilisation %':<14}")
    for c in sim.crushers.values():
        print(f"{c.asset_id:<12} {c.health_pct:<10} {c.cumulative_output_t:<14.1f} {c.utilisation(topology.SHIFT_MINUTES):<14}")

    print(f"\n{'Stockpile':<18} {'Final tonnes':<14} {'% full':<10}")
    for s in sim.stockpiles.values():
        print(f"{s.asset_id:<18} {s.current_t:<14.1f} {s.pct_full():<10}")

    print(f"\nDisruptions applied:")
    for d in sim.scenario:
        status = "resolved" if d.resolved else ("active" if d.applied else "not yet triggered")
        print(f"  - {d.disruption_type} on {d.target_id} @ tick {d.trigger_tick} "
              f"(duration {d.duration_min} min) -> {status}")
    print()


def main():
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    mode = sys.argv[2] if len(sys.argv) > 2 else "oversized"

    if scenario_name not in SCENARIOS:
        print(f"Unknown scenario '{scenario_name}'. Options: {list(SCENARIOS.keys())}")
        sys.exit(1)
    if mode not in ("oversized", "balanced"):
        print(f"Unknown mode '{mode}'. Options: oversized, balanced")
        sys.exit(1)

    scenario = SCENARIOS[scenario_name]()
    sim = Simulation(scenario, mode=mode)
    sim.run()

    out_path = f"/mnt/user-data/outputs/mine_sim_log_{scenario_name}_{mode}.csv"
    sim.write_csv(out_path)
    print(f"Operational data log written to: {out_path} ({len(sim.records)} rows)")

    summarize(sim, scenario_name)


if __name__ == "__main__":
    main()
