"""
main_use.py — SolidWorks Hex Screw Generator (all-in-one)
==========================================================
Describe a hex screw in plain English and this script creates
the 3-D model directly in SolidWorks via Python COM automation.

Requirements
------------
  pip install anthropic pywin32

  (pywin32 is Windows-only; required for SolidWorks COM)

Run
---
  python main_use.py
  python main_use.py "I want a 3/8 hex screw that fits in a 3/4 hole"
"""

# ── YOUR ANTHROPIC API KEY ────────────────────────────────────────────────────
ANTHROPIC_API_KEY = "YOUR_API_KEY_HERE"
# ─────────────────────────────────────────────────────────────────────────────

import json
import math
import os
import sys

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI/ASME B18.2.1 Hex Bolt Standard Dimensions (inches)
# ═══════════════════════════════════════════════════════════════════════════════

ANSI_HEX_SPECS = {
    0.1900: {"fraction": "#10", "W": 0.3125, "H": 0.1563, "tpi": 24, "tpif": 32},
    0.2500: {"fraction": "1/4",  "W": 0.4375, "H": 0.1719, "tpi": 20, "tpif": 28},
    0.3125: {"fraction": "5/16", "W": 0.5000, "H": 0.2188, "tpi": 18, "tpif": 24},
    0.3750: {"fraction": "3/8",  "W": 0.5625, "H": 0.2344, "tpi": 16, "tpif": 24},
    0.4375: {"fraction": "7/16", "W": 0.6250, "H": 0.2813, "tpi": 14, "tpif": 20},
    0.5000: {"fraction": "1/2",  "W": 0.7500, "H": 0.3125, "tpi": 13, "tpif": 20},
    0.5625: {"fraction": "9/16", "W": 0.8750, "H": 0.3594, "tpi": 12, "tpif": 18},
    0.6250: {"fraction": "5/8",  "W": 0.9375, "H": 0.4063, "tpi": 11, "tpif": 18},
    0.7500: {"fraction": "3/4",  "W": 1.1250, "H": 0.4688, "tpi": 10, "tpif": 16},
    0.8750: {"fraction": "7/8",  "W": 1.3125, "H": 0.5469, "tpi":  9, "tpif": 14},
    1.0000: {"fraction": "1",    "W": 1.5000, "H": 0.6094, "tpi":  8, "tpif": 12},
    1.1250: {"fraction": "1-1/8","W": 1.6875, "H": 0.6875, "tpi":  7, "tpif": 12},
    1.2500: {"fraction": "1-1/4","W": 1.8750, "H": 0.7500, "tpi":  7, "tpif": 12},
    1.3750: {"fraction": "1-3/8","W": 2.0625, "H": 0.8438, "tpi":  6, "tpif": 12},
    1.5000: {"fraction": "1-1/2","W": 2.2500, "H": 0.9063, "tpi":  6, "tpif": 12},
}

FRACTION_MAP = {
    "10": 0.1900, "#10": 0.1900,
    "1/4": 0.2500, "5/16": 0.3125, "3/8": 0.3750, "7/16": 0.4375,
    "1/2": 0.5000, "9/16": 0.5625, "5/8": 0.6250, "3/4": 0.7500,
    "7/8": 0.8750, "1": 1.0000, "1-1/8": 1.1250, "1-1/4": 1.2500,
    "1-3/8": 1.3750, "1-1/2": 1.5000,
}


def _get_spec(nominal_dia_in):
    closest = min(ANSI_HEX_SPECS, key=lambda k: abs(k - nominal_dia_in))
    if abs(closest - nominal_dia_in) < 0.02:
        return {"nominal": closest, **ANSI_HEX_SPECS[closest]}
    return None


def _circ_radius(W):
    """Circumscribed radius (vertex to centre) from width-across-flats W."""
    return (W / 2.0) / math.cos(math.pi / 6)


def _fits_in_hole(W, hole_dia):
    return _circ_radius(W) * 2 <= hole_dia


def _largest_fitting(hole_dia):
    candidates = [n for n, s in ANSI_HEX_SPECS.items() if _fits_in_hole(s["W"], hole_dia)]
    return max(candidates) if candidates else None


def _format_spec(spec):
    return (
        f"  Size          : {spec['fraction']}\" ({spec['nominal']:.4f}\")\n"
        f"  Across flats  : {spec['W']:.4f}\"  ({spec['W']*25.4:.2f} mm)\n"
        f"  Head height   : {spec['H']:.4f}\"  ({spec['H']*25.4:.2f} mm)\n"
        f"  Thread (UNC)  : {spec['fraction']}-{spec['tpi']} coarse\n"
        f"  Thread (UNF)  : {spec['fraction']}-{spec['tpif']} fine\n"
        f"  Circ. dia     : {_circ_radius(spec['W'])*2:.4f}\"  (min hole to pass head)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Claude API — natural language parser
# ═══════════════════════════════════════════════════════════════════════════════

_PARSE_SYSTEM = """You are a mechanical-engineering assistant that extracts hex-screw
specifications from natural language.

Return ONLY a compact JSON object (no markdown, no explanation) with these fields:
{
  "nominal_fraction": "<e.g. '3/8', '1/2'>",
  "nominal_decimal":  <decimal inches, e.g. 0.375>,
  "shaft_length_in":  <decimal inches or null>,
  "hole_diameter_in": <decimal inches of any mentioned hole, or null>,
  "thread_type":      "coarse" or "fine",
  "notes":            "<any assumptions>"
}
Convert fractions: 3/8→0.375, 3/4→0.75, 1/2→0.5, etc."""


def parse_request(user_message):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        thinking={"type": "adaptive"},
        system=_PARSE_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}") + 1
        parsed = json.loads(text[s:e]) if s >= 0 else {}

    frac = str(parsed.get("nominal_fraction", "")).strip('"').strip()
    if frac in FRACTION_MAP:
        parsed["nominal_decimal"] = FRACTION_MAP[frac]
    return parsed


def resolve_spec(parsed):
    warnings = []
    nominal = parsed.get("nominal_decimal")
    if nominal is None:
        return None, ["Could not determine nominal screw size."]
    spec = _get_spec(nominal)
    if spec is None:
        return None, [f"No ANSI spec found for {nominal:.4f}\"."]

    hole = parsed.get("hole_diameter_in")
    if hole:
        circ = _circ_radius(spec["W"]) * 2
        if circ <= hole:
            warnings.append(f"Head fits in {hole}\" hole (circ. dia = {circ:.4f}\").")
        else:
            lg = _largest_fitting(hole)
            warnings.append(
                f"WARNING: {spec['fraction']}\" head does NOT fit in {hole}\" hole "
                f"(needs {circ:.4f}\" min). "
                + (f"Largest that fits: {lg}\"" if lg else "No standard screw fits.")
            )
    if parsed.get("notes"):
        warnings.append(f"Note: {parsed['notes']}")
    return spec, warnings


# ═══════════════════════════════════════════════════════════════════════════════
# SolidWorks COM automation
# ═══════════════════════════════════════════════════════════════════════════════

M = 0.0254   # inches → meters


def _sw_connect():
    try:
        import win32com.client
    except ImportError:
        raise ImportError("pywin32 not installed. Run:  pip install pywin32")
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        print("  [SW] Attached to existing SolidWorks instance.")
    except Exception:
        print("  [SW] Launching SolidWorks…")
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True
    return sw


def _new_part(sw):
    template = sw.GetUserPreferenceStringValue(9)
    if not template or not os.path.exists(template):
        for year in range(2026, 2017, -1):
            t = rf"C:\ProgramData\SolidWorks\SOLIDWORKS {year}\templates\Part.prtdot"
            if os.path.exists(t):
                template = t
                break
    part = sw.NewDocument(template, 0, 0, 0)
    if part is None:
        raise RuntimeError("SolidWorks returned None for NewDocument.")
    return part


def _extrude(part, sketch_name, depth_m, flip=False):
    part.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 4, None, 0)
    feat = part.FeatureManager.FeatureExtrusion2(
        True, flip, False,
        0, 0,
        depth_m, 0.0,
        False, False, False, False,
        0.0174533, 0.0174533,
        False, False, False,
        True, False, True,
    )
    part.ClearSelection2(True)
    return feat


def build_in_solidworks(spec, shaft_length_in=1.0, save_path=None):
    """Create the hex screw model live in SolidWorks via COM."""
    nom   = spec["nominal"]
    W     = spec["W"]
    H     = spec["H"]
    frac  = spec["fraction"]
    tpi   = spec["tpi"]

    d_m     = nom * M
    H_m     = H   * M
    L_m     = shaft_length_in * M
    R_hex_m = _circ_radius(W) * M

    sw   = _sw_connect()
    part = _new_part(sw)
    sk   = part.SketchManager

    label = f"{frac}-{tpi} Hex Bolt  L={shaft_length_in}\""
    print(f"  [SW] Building: {label}")

    # ── Step 1: Hex head ──────────────────────────────────────────────────
    # Sketch hexagon on Top Plane, extrude upward (+Z)
    part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    sk.InsertSketch(True)
    part.ClearSelection2(True)

    pi = math.pi
    for i in range(6):
        a1 = (pi / 6) + i * (pi / 3)
        a2 = (pi / 6) + (i + 1) * (pi / 3)
        sk.CreateLine(
            R_hex_m * math.cos(a1), R_hex_m * math.sin(a1), 0.0,
            R_hex_m * math.cos(a2), R_hex_m * math.sin(a2), 0.0,
        )

    sk.InsertSketch(True)
    part.ClearSelection2(True)

    if _extrude(part, "Sketch1", H_m, flip=False) is None:
        print("  [SW] Warning: head extrusion returned None.")

    # ── Step 2: Shaft ─────────────────────────────────────────────────────
    # Sketch circle on Top Plane, extrude downward (−Z)
    part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    sk.InsertSketch(True)
    part.ClearSelection2(True)

    sk.CreateCircle(0.0, 0.0, 0.0,  d_m / 2, 0.0, 0.0)

    sk.InsertSketch(True)
    part.ClearSelection2(True)

    if _extrude(part, "Sketch2", L_m, flip=True) is None:
        print("  [SW] Warning: shaft extrusion returned None.")

    # ── Step 3: Tip chamfer (45°) ─────────────────────────────────────────
    try:
        found = part.Extension.SelectByID2(
            "", "EDGE", d_m / 2, 0.0, -L_m, False, 0, None, 0
        )
        if found:
            part.FeatureManager.InsertFeatureChamfer(
                4, 1, False, d_m * 0.075, 0.7854, 0, 0, 0
            )
            part.ClearSelection2(True)
    except Exception:
        pass   # cosmetic only — skip on error

    # ── Finish ────────────────────────────────────────────────────────────
    part.SetTitle2(label)
    part.ShowNamedView2("*Isometric", -1)
    part.ViewZoomtofit2()
    part.GraphicsRedraw2()

    if save_path:
        if not save_path.lower().endswith(".sldprt"):
            save_path += ".sldprt"
        part.SaveAs(save_path)
        print(f"  [SW] Saved → {save_path}")

    print(f"  [SW] Done. '{label}' is open in SolidWorks.")
    return part


# ═══════════════════════════════════════════════════════════════════════════════
# Main chat loop
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════════════════════╗
║        SolidWorks Hex Screw Generator                    ║
║  Describe a screw in plain English → 3-D model created   ║
╚══════════════════════════════════════════════════════════╝
Examples:
  I want a 3/8 hex screw that fits in a 3/4 hole
  Create a 1/2-13 hex bolt, 2 inches long
  Make a 1/4 inch fine-thread hex cap screw, 1.5 inches

Type  quit  to exit.
"""


def run():
    # Check anthropic is installed
    try:
        import anthropic  # noqa: F401
    except ImportError:
        sys.exit("anthropic not installed.  Run:  pip install anthropic")

    # Check pywin32 (warn but don't abort — user may still want to see the spec)
    try:
        import win32com.client  # noqa: F401
        have_com = True
    except ImportError:
        have_com = False
        print(
            "\n[!] pywin32 not found — cannot create models directly.\n"
            "    Install with:  pip install pywin32   (Windows only)\n"
        )

    print(BANNER)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        print("\nParsing your request…")
        try:
            parsed = parse_request(user_input)
        except Exception as exc:
            print(f"  [Error] {exc}\n")
            continue

        spec, warnings = resolve_spec(parsed)

        if spec is None:
            print("  Could not identify a standard hex screw from your description.")
            for w in warnings:
                print(f"  ! {w}")
            print()
            continue

        shaft_in = parsed.get("shaft_length_in") or 1.0

        print(f"\nResolved ANSI spec:\n{_format_spec(spec)}")
        print(f"  Shaft length  : {shaft_in}\"")
        for w in warnings:
            print(f"  > {w}")
        print()

        confirm = input("Create model in SolidWorks? [Y/n]: ").strip().lower()
        if confirm in ("n", "no"):
            print("Skipped.\n")
            continue

        if not have_com:
            print("  [!] pywin32 not available — cannot create model.\n")
            continue

        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        safe = spec["fraction"].replace("/", "_").replace("-", "_")
        save_path = os.path.join(output_dir, f"hex_screw_{safe}_L{shaft_in}in.sldprt")

        try:
            build_in_solidworks(spec, shaft_length_in=shaft_in, save_path=save_path)
        except Exception as exc:
            print(f"  [!] SolidWorks error: {exc}\n")

        print("-" * 58)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Quick single-shot: python main_use.py "3/8 screw fits in 3/4 hole"
        user_input = " ".join(sys.argv[1:])
        print(f"Request: {user_input}\n")
        try:
            import anthropic  # noqa: F401
        except ImportError:
            sys.exit("anthropic not installed.  Run:  pip install anthropic")
        parsed = parse_request(user_input)
        spec, warnings = resolve_spec(parsed)
        if spec:
            shaft_in = parsed.get("shaft_length_in") or 1.0
            print(_format_spec(spec))
            print(f"  Shaft length  : {shaft_in}\"")
            for w in warnings:
                print(f"  > {w}")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            safe = spec["fraction"].replace("/", "_").replace("-", "_")
            save_path = os.path.join(output_dir, f"hex_screw_{safe}_L{shaft_in}in.sldprt")
            try:
                build_in_solidworks(spec, shaft_length_in=shaft_in, save_path=save_path)
            except Exception as exc:
                print(f"  [!] SolidWorks error: {exc}")
        else:
            print("Could not resolve spec.")
            for w in warnings:
                print(f"  ! {w}")
    else:
        run()
