"""Adds a plain-words explanation to every event in the Control Room data files.

Run from the project folder:   python add_explanations.py
It edits demo_artifact/demo_data*.json in place. Safe to run again.
Uses the same wording as the API explainer (api/explainer.py), no API key needed.
"""
import glob
import json
import os

from api.explainer import build_facts, event_text


def explain_event(ev: dict) -> str:
    """Control Room event (camelCase) -> plain words."""
    options = ev["options"]
    base = next(o for o in options if o["isBaseline"])
    best = next((o for o in options if o["isRecommended"]), None)
    acts = bool(best) and not best["isBaseline"]
    shaped = {  # the shape build_facts() expects from the API
        "title": "", "production_target_t": 0, "final_production_if_nobody_acts_t": 0,
        "events": [{
            "tick": ev["tick"],
            "events": [{"type": e["type"], "target": e["target"], "duration_min": e["durationMin"]}
                       for e in ev["events"]],
            "production_so_far_t": ev["productionSoFar"],
            "options_searched": ev["searched"],
            "act_is_worth_it": acts,
            "options": [{"id": o["id"], "label": o["label"], "final_production_t": o["finalProduction"],
                         "gain_vs_doing_nothing_t": o["deltaVsBaseline"],
                         "recommended": o["isRecommended"]} for o in options],
        }],
    }
    return event_text(build_facts(shaped)["disruption_points"][0])


def main():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_artifact")
    for path in sorted(glob.glob(os.path.join(folder, "demo_data*.json"))):
        with open(path) as f:
            data = json.load(f)
        n = 0
        for run in data["runs"].values():
            for ev in run["events"]:
                ev["explanation"] = explain_event(ev)
                n += 1
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"{os.path.basename(path)}: {n} explanations")


if __name__ == "__main__":
    main()
