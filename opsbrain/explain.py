"""
Objective 6 — Explain.

Turns the evaluated options into the decision table from the project's
"flagship demonstration" (09:42 / 09:43 walkthrough): options side by
side, production impact, and a plain-language recommendation. A human
still makes the call — this just lays out the trade-offs.
"""

from __future__ import annotations

from typing import List

from opsbrain.consequences import Evaluation
from opsbrain.context import Context


def print_decision_table(ctx: Context, evaluations: List[Evaluation]):
    baseline = next(e for e in evaluations if e.option.option_id == "accept_loss")

    print(f"\nOPTIONS  (baseline = accept the loss, do nothing)")
    print(f"{'Option':<45} {'Final production':<20} {'vs baseline':<15}")
    for e in evaluations:
        delta = e.final_production_t - baseline.final_production_t
        delta_str = f"{delta:+.1f} t" if e.option.option_id != "accept_loss" else "-"
        print(f"{e.option.label:<45} {e.final_production_t:,.1f} t{'':<10} {delta_str:<15}")

    best = max(evaluations, key=lambda e: e.final_production_t)

    print(f"\nRecommended: {best.option.label}")
    print(f"  Why: {best.option.description}")
    if best.option.option_id == "accept_loss":
        print(f"  Every reassignment option tried made things worse or the same — "
              f"the disruption is better absorbed than reacted to here.")
    else:
        gain = best.final_production_t - baseline.final_production_t
        print(f"  Expected gain over doing nothing: {gain:+.1f} t by shift end.")
    print(f"{'-'*60}")
