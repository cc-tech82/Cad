"""
Natural-language parser for hex screw descriptions.
Uses the Claude API to extract structured parameters.
"""

# ── Anthropic API key ─────────────────────────────────────────────────────────
# Replace the value below with your key, or leave it and set the
# ANTHROPIC_API_KEY environment variable instead.
ANTHROPIC_API_KEY = "YOUR_API_KEY_HERE"
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import anthropic
from screw_specs import FRACTION_MAP, get_spec, largest_screw_that_fits


SYSTEM_PROMPT = """You are a mechanical-engineering assistant that extracts hex-screw
specifications from natural language.

Return ONLY a compact JSON object (no markdown, no explanation) with these fields:

{
  "nominal_fraction": "<fraction string, e.g. '3/8', '1/2', '1/4'>",
  "nominal_decimal":  <decimal inches, e.g. 0.375>,
  "shaft_length_in":  <decimal inches or null if not stated>,
  "hole_diameter_in": <decimal inches of the hole mentioned, or null>,
  "thread_type":      "coarse" or "fine"  (default "coarse"),
  "screw_type":       "hex_bolt" or "hex_cap_screw" (default "hex_bolt"),
  "notes":            "<any ambiguity or assumption worth flagging>"
}

Rules:
- Convert fractions like 3/8 → 0.375, 3/4 → 0.75, 1/2 → 0.5, etc.
- If no shaft length is given, set shaft_length_in to null.
- If the user mentions a hole the screw should fit in, capture its diameter.
- If the user says "fits in a 3/4 hole", interpret hole_diameter_in = 0.75.
"""


def parse_request(user_message: str) -> dict:
    """
    Use Claude to extract screw parameters from a natural-language string.
    Returns a dict with keys: nominal_fraction, nominal_decimal, shaft_length_in,
    hole_diameter_in, thread_type, screw_type, notes.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract the text block (thinking blocks come first)
    text = next(
        (b.text for b in response.content if b.type == "text"), ""
    ).strip()

    # Strip possible ```json fences
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to salvage by grabbing the first {...}
        start = text.find("{")
        end = text.rfind("}") + 1
        parsed = json.loads(text[start:end]) if start >= 0 else {}

    # Normalise fraction key
    frac = str(parsed.get("nominal_fraction", "")).strip('"').strip()
    if frac in FRACTION_MAP:
        parsed["nominal_decimal"] = FRACTION_MAP[frac]

    return parsed


def resolve_spec(parsed: dict) -> tuple[dict | None, list[str]]:
    """
    Given a parsed dict, return (spec, warnings).
    spec  – full ANSI spec dict or None if not found.
    warnings – list of advisory strings.
    """
    warnings = []
    nominal = parsed.get("nominal_decimal")

    if nominal is None:
        return None, ["Could not determine nominal screw size."]

    spec = get_spec(nominal)
    if spec is None:
        return None, [f"No ANSI spec found for {nominal:.4f}\" nominal diameter."]

    hole = parsed.get("hole_diameter_in")
    if hole:
        circ_dia = 2 * (spec["W"] / 2) / __import__("math").cos(__import__("math").pi / 6)
        if circ_dia <= hole:
            warnings.append(
                f"Head fits in {hole}\" hole "
                f"(head circumscribed dia = {circ_dia:.4f}\")."
            )
        else:
            largest = largest_screw_that_fits(hole)
            warnings.append(
                f"WARNING: {spec['fraction']}\" head does NOT fit in {hole}\" hole "
                f"(needs {circ_dia:.4f}\" min). "
                + (f"Largest screw that fits: {largest}\"" if largest else "No standard screw fits.")
            )

    notes = parsed.get("notes", "")
    if notes:
        warnings.append(f"Note: {notes}")

    return spec, warnings
