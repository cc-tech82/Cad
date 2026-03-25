"""
example_direct.py — Option B demo
==================================
Creates a 3/8"-16 UNC hex bolt (1" shaft) directly in SolidWorks
via Python COM automation.  No chat interface, no API calls.

Requirements
------------
- Windows
- SolidWorks installed (any version 2018+)
- pywin32:  pip install pywin32

Run
---
  python example_direct.py

SolidWorks will open (or attach to a running instance) and the part
will appear on screen.  You will be prompted to save it.
"""

import math
import os
import sys

# ── Guard: must be Windows with pywin32 ──────────────────────────────────────
try:
    import win32com.client
except ImportError:
    sys.exit(
        "pywin32 not found.\n"
        "Install it with:  pip install pywin32\n"
        "(Windows only)"
    )

# ── Screw parameters (ANSI/ASME B18.2.1) ─────────────────────────────────────
NOM_IN   = 0.3750   # 3/8"  nominal shaft diameter
W_IN     = 0.5625   # 9/16" across flats
H_IN     = 0.2344   # 15/64" head height
L_IN     = 1.0000   # 1"    shaft length
TPI      = 16       # 3/8-16 UNC (coarse)
LABEL    = '3/8"-16 UNC Hex Bolt  L=1"'

M        = 0.0254   # conversion: inches → meters (SolidWorks internal unit)

# Derived geometry
NOM_M    = NOM_IN * M
W_M      = W_IN   * M
H_M      = H_IN   * M
L_M      = L_IN   * M
# Circumscribed radius: distance from centre to vertex = (W/2) / cos(30°)
R_HEX_M  = (W_M / 2.0) / math.cos(math.pi / 6)


# ── Helpers ───────────────────────────────────────────────────────────────────

def connect():
    """Attach to a running SolidWorks or launch it."""
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        print("  Attached to existing SolidWorks instance.")
    except Exception:
        print("  SolidWorks not running — launching…")
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True
    return sw


def new_part(sw):
    """Open a blank Part document using the user's default template."""
    template = sw.GetUserPreferenceStringValue(9)   # swDefaultTemplatePart = 9

    # Fallback: search standard install paths
    if not template or not os.path.exists(template):
        for year in range(2026, 2017, -1):
            candidate = (
                rf"C:\ProgramData\SolidWorks\SOLIDWORKS {year}\templates\Part.prtdot"
            )
            if os.path.exists(candidate):
                template = candidate
                break

    part = sw.NewDocument(template, 0, 0, 0)
    if part is None:
        raise RuntimeError(
            "SolidWorks returned None for NewDocument.\n"
            "Make sure a Part template exists at:\n"
            f"  {template}"
        )
    return part


def open_sketch_on_top_plane(part):
    part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)


def close_sketch(part):
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)


def extrude(part, sketch_name: str, depth_m: float, flip: bool = False):
    """Select sketch_name and extrude it blindly by depth_m metres."""
    part.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 4, None, 0)
    feat = part.FeatureManager.FeatureExtrusion2(
        True,           # single direction
        flip,           # True  → extrude in −Z (downward from Top Plane)
        False,          # second-direction flag — N/A
        0, 0,           # end condition: Blind for both directions
        depth_m, 0.0,   # depth dir1, depth dir2
        False, False,   # no draft dir1, dir2
        False, False,   # draft outward dir1, dir2
        0.0174533,      # draft angle dir1 (1° — unused)
        0.0174533,      # draft angle dir2
        False, False,   # offset reverse dir1, dir2
        False,          # translate surface
        True,           # merge bodies
        False,          # use feature scope
        True,           # auto-select bodies
    )
    part.ClearSelection2(True)
    return feat


# ── Main build sequence ───────────────────────────────────────────────────────

def build():
    print("\n=== SolidWorks Hex Screw — Option B (direct COM) ===\n")
    print(f"  Nominal  : 3/8\"  ({NOM_IN}\")")
    print(f"  Flats    : 9/16\" ({W_IN}\")")
    print(f"  Head ht  : {H_IN}\"")
    print(f"  Shaft L  : {L_IN}\"")
    print(f"  Thread   : {TPI} TPI (UNC coarse)\n")

    # ── 1. Connect to SolidWorks ──────────────────────────────────────────
    sw   = connect()
    part = new_part(sw)
    sk   = part.SketchManager

    # ── 2. Hex head ───────────────────────────────────────────────────────
    # Sketch a regular hexagon on the Top Plane, then extrude it upward (+Z).
    # Flat-to-flat orientation: first vertex placed at 30° so top/bottom
    # faces are flat (standard bolt presentation).
    print("  Step 1/4 : sketching hexagon…")
    open_sketch_on_top_plane(part)

    pi = math.pi
    for i in range(6):
        a1 = (pi / 6) + i * (pi / 3)
        a2 = (pi / 6) + (i + 1) * (pi / 3)
        x1, y1 = R_HEX_M * math.cos(a1), R_HEX_M * math.sin(a1)
        x2, y2 = R_HEX_M * math.cos(a2), R_HEX_M * math.sin(a2)
        sk.CreateLine(x1, y1, 0.0, x2, y2, 0.0)

    close_sketch(part)

    print("  Step 2/4 : extruding hex head upward…")
    feat_head = extrude(part, "Sketch1", H_M, flip=False)
    if feat_head is None:
        print("  [!] Head extrusion returned None — continuing anyway.")

    # ── 3. Shaft ──────────────────────────────────────────────────────────
    # Sketch a circle (nominal diameter) on the same Top Plane, then
    # extrude it downward (−Z) for the shaft length.
    print("  Step 3/4 : sketching shaft circle…")
    open_sketch_on_top_plane(part)
    sk.CreateCircle(0.0, 0.0, 0.0,   NOM_M / 2, 0.0, 0.0)
    close_sketch(part)

    print("  Step 4/4 : extruding shaft downward…")
    feat_shaft = extrude(part, "Sketch2", L_M, flip=True)
    if feat_shaft is None:
        print("  [!] Shaft extrusion returned None — continuing anyway.")

    # ── 4. Tip chamfer (45°) ──────────────────────────────────────────────
    # Select the bottom circular edge of the shaft by its 3-D position
    # (x=NOM_M/2, y=0, z=−L_M) rather than a brittle "Edge<1>" string.
    chamfer = NOM_M * 0.075     # ~7.5% of shaft diameter
    try:
        found = part.Extension.SelectByID2(
            "", "EDGE",
            NOM_M / 2, 0.0, -L_M,   # point on the bottom circular edge
            False, 0, None, 0
        )
        if found:
            part.FeatureManager.InsertFeatureChamfer(
                4,          # swChamferType: Distance-Distance
                1,          # propagate
                False,      # flip direction
                chamfer,    # distance 1
                0.7854,     # 45° in radians
                0, 0, 0,
            )
            part.ClearSelection2(True)
    except Exception as e:
        print(f"  [!] Chamfer skipped ({e})")

    # ── 5. Finish ─────────────────────────────────────────────────────────
    part.SetTitle2(LABEL)
    part.ShowNamedView2("*Isometric", -1)
    part.ViewZoomtofit2()
    part.GraphicsRedraw2()

    print(f"\n  ✓ Model '{LABEL}' is open in SolidWorks.\n")

    # ── 6. Optional save ──────────────────────────────────────────────────
    save = input("  Save the part? [Y/n]: ").strip().lower()
    if save not in ("n", "no"):
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, "hex_screw_3_8_1in.sldprt")
        part.SaveAs(save_path)
        print(f"  Saved → {save_path}")

    return part


if __name__ == "__main__":
    build()
