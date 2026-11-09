"""Plain-words explanations of an OpsBrain analysis.

GET /jobs/{id}/explain
  -> {"id", "status": "running"}                      while the analysis is still running
  -> {"id", "status": "done", "source", "text"}       when ready

Rules:
  * The explainer only RE-TELLS numbers the engine produced. It never decides.
  * With ANTHROPIC_API_KEY set, Claude writes the text. Without it, or if Claude
    mentions a number the engine never produced, a fixed template is used instead.
  * It only recommends. A person decides.
"""
import json
import os
import re
import urllib.request

from fastapi import APIRouter, HTTPException

from api import jobs

router = APIRouter(tags=["explain"])

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = (
    "You explain a mining operations analysis to a control-room operator. "
    "Use ONLY the facts in the JSON you are given. Never invent or calculate new numbers: "
    "quote the tonnes exactly as given. Do not give clock times. "
    "You only recommend; the person decides. "
    "Write short, plain sentences. For each disruption: what happened, what the best option is, "
    "what it gains versus doing nothing, and any trade-off. "
    "If act_is_worth_it is false, say that doing nothing is fine. Max 150 words per disruption."
)


# ---------- facts: the only things the explainer may talk about ----------
def build_facts(result: dict) -> dict:
    events = []
    for ev in result.get("events", []):
        opts = ev.get("options", [])
        best = next((o for o in opts if o.get("recommended")), None)
        base = next((o for o in opts if o.get("id") == "accept_loss"), None)
        events = events + [{
            "minute_into_shift": ev.get("tick"),
            "disruptions": [
                {"type": d.get("type"), "target": d.get("target"), "duration_min": d.get("duration_min")}
                for d in ev.get("events", [])
            ],
            "tonnes_produced_so_far": ev.get("production_so_far_t"),
            "tonnes_if_nobody_acts_from_here": base.get("final_production_t") if base else None,
            "options_searched": ev.get("options_searched"),
            "act_is_worth_it": ev.get("act_is_worth_it"),
            "recommended_option": best.get("label") if best else None,
            "recommended_final_tonnes": best.get("final_production_t") if best else None,
            "recommended_gain_tonnes": best.get("gain_vs_doing_nothing_t") if best else None,
            "other_options": [
                {"label": o.get("label"), "final_tonnes": o.get("final_production_t"),
                 "gain_tonnes": o.get("gain_vs_doing_nothing_t")}
                for o in opts if not o.get("recommended") and o.get("id") != "accept_loss"
            ],
        }]
    return {
        "story": result.get("title"),
        "shift_target_tonnes": result.get("production_target_t"),
        "final_tonnes_if_nobody_acts": result.get("final_production_if_nobody_acts_t"),
        "disruption_points": events,
    }


# ---------- fixed template: always available ----------
def _t(x) -> str:
    return f"{x:,.1f}".rstrip("0").rstrip(".") if isinstance(x, (int, float)) else str(x)


def _what(ev: dict) -> str:
    return " and ".join(
        f"{d['type'].replace('_', ' ').lower()} on {d['target']} for {d['duration_min']} min"
        for d in ev["disruptions"])


def event_text(ev: dict) -> str:
    """Plain words for ONE disruption point (also used by the Control Room page)."""
    what = _what(ev)
    text = f"{what[0].upper()}{what[1:]}. OpsBrain searched {ev['options_searched']} possible moves."
    if ev.get("tonnes_if_nobody_acts_from_here") is not None:
        text += f" If nobody acts, the shift ends at {_t(ev['tonnes_if_nobody_acts_from_here'])} t."
    if ev["act_is_worth_it"] and ev["recommended_option"]:
        text += (f" Best move: {ev['recommended_option']}. It ends the shift at "
                 f"{_t(ev['recommended_final_tonnes'])} t, which is {_t(ev['recommended_gain_tonnes'])} t "
                 f"more than doing nothing.")
    else:
        text += " No move beats doing nothing by enough, so doing nothing is fine."
    return text


def template_text(facts: dict) -> str:
    lines = [f"{facts['story']}. Shift target: {_t(facts['shift_target_tonnes'])} t. "
             f"If nobody acts at all, the shift ends at {_t(facts['final_tonnes_if_nobody_acts'])} t."]
    for i, ev in enumerate(facts["disruption_points"], 1):
        lines.append(f"Disruption {i} (minute {ev['minute_into_shift']}): {event_text(ev)}")
    lines.append("This is a recommendation only. A person decides.")
    return "\n\n".join(lines)


# ---------- guardrail: no invented numbers ----------
_NUM = re.compile(r"\d[\d,]*\.?\d*")


def _numbers_in(obj, out):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            try:
                out.add(float(m.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_in(v, out)


def numbers_are_grounded(text: str, facts: dict) -> bool:
    allowed = set()
    _numbers_in(facts, allowed)
    for v in list(allowed):                      # allow honest rounding and minutes -> hours
        allowed.update({round(v), round(v, 1), v / 60, round(v / 60, 1), float(int(v))})
    for m in _NUM.findall(text):
        try:
            n = float(m.replace(",", "").rstrip("."))
        except ValueError:
            continue
        if n <= 10:                              # counting words: "2 options", "3 steps"
            continue
        if not any(abs(n - a) < 0.051 for a in allowed):
            return False
    return True


# ---------- Claude call (optional) ----------
def call_claude(facts: dict) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 700,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": json.dumps(facts)}],
    }).encode()
    req = urllib.request.Request(API_URL, body, {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def explain(result: dict) -> dict:
    facts = build_facts(result)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            text = call_claude(facts)
            if text and numbers_are_grounded(text, facts):
                return {"source": "claude", "text": text}
        except Exception:
            pass                                  # any failure: fall back, never break the page
    return {"source": "template", "text": template_text(facts)}


@router.get("/jobs/{job_id}/explain")
def explain_job(job_id: str):
    try:
        args = jobs.parse_id(job_id)
    except ValueError:
        raise HTTPException(404, "no such job")
    view = jobs._view(job_id, jobs._start(job_id, args))
    if view["status"] != "done":
        return view
    return {"id": job_id, "status": "done", **explain(view["result"])}
