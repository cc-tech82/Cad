"""
Direct SolidWorks COM automation (Windows only — requires SolidWorks installed).

Uses pywin32 to connect to SolidWorks and build the model without needing
to run a separate macro file.
"""

import math
import os

M = 0.0254  # inches → meters


def _sw_connect():
    """Attach to a running SolidWorks instance, or launch one."""
    try:
        import win32com.client
    except ImportError:
        raise ImportError(
            "pywin32 is required for direct COM automation.\n"
            "Install it with:  pip install pywin32"
        )

    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        print("[SW] Connected to existing SolidWorks instance.")
    except Exception:
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True
        print("[SW] Launched SolidWorks.")

    return sw


def _new_part(sw):
    """Create a new empty Part document."""
    template = sw.GetUserPreferenceStringValue(9)   # swDefaultTemplatePart = 9
    if not template or not os.path.exists(template):
        # Fallback: search common template directories
        for year in range(2026, 2018, -1):
            t = rf"C:\ProgramData\SolidWorks\SOLIDWORKS {year}\templates\Part.prtdot"
            if os.path.exists(t):
                template = t
                break

    part = sw.NewDocument(template, 0, 0, 0)
    if part is None:
        raise RuntimeError(
            "SolidWorks returned None for NewDocument. "
            "Check that the part template path is valid."
        )
    return part


def _draw_hexagon(sk_mgr, R_hex: float):
    """Draw a closed hexagon (6 lines) centred at origin with circumscribed radius R_hex."""
    pi = math.pi
    angle_offset = pi / 6          # 30° so a flat edge is at the top/bottom

    vertices = [
        (R_hex * math.cos(angle_offset + i * pi / 3),
         R_hex * math.sin(angle_offset + i * pi / 3))
        for i in range(6)
    ]
    for i in range(6):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % 6]
        sk_mgr.CreateLine(x1, y1, 0.0, x2, y2, 0.0)


def _extrude(part, sketch_name: str, depth: float, flip: bool = False):
    """Select a sketch by name and extrude it (blind, single direction)."""
    part.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 4, None, 0)
    feat = part.FeatureManager.FeatureExtrusion2(
        True,              # sd   : single direction
        flip,              # flip : reverse direction when True
        False,             # dir  : N/A for single direction
        0, 0,              # t1, t2 : both Blind
        depth, 0.0,        # d1, d2
        False, False,      # dchk1, dchk2 (no draft)
        False, False,      # ddir1, ddir2
        0.0174533,         # dang1 (1° — unused)
        0.0174533,         # dang2
        False, False,      # offsetReverse1, offsetReverse2
        False,             # translateSurface
        True,              # mergeResult
        False,             # useFeatScope
        True,              # useAutoSelect
    )
    part.ClearSelection2(True)
    return feat


def create_hex_screw(
    spec: dict,
    shaft_length_in: float = 1.0,
    save_path: str | None = None,
) -> object:
    """
    Build a 3-D hex-screw model directly in SolidWorks via COM.

    Parameters
    ----------
    spec            : dict from screw_specs.get_spec()
    shaft_length_in : shaft length in inches
    save_path       : if given, save the new part to this path (.sldprt)

    Returns
    -------
    The SolidWorks ModelDoc2 COM object for the new part.
    """
    from screw_specs import circumscribed_radius

    nom   = spec["nominal"]
    W     = spec["W"]
    H     = spec["H"]
    frac  = spec["fraction"]
    tpi   = spec["tpi"]

    # Convert to meters
    d_m     = nom * M
    W_m     = W   * M
    H_m     = H   * M
    L_m     = shaft_length_in * M
    R_hex_m = circumscribed_radius(W) * M

    # ── Connect & create document ─────────────────────────────────────────
    sw   = _sw_connect()
    part = _new_part(sw)
    sk   = part.SketchManager

    print(f"[SW] Creating {frac}-{tpi} UNC hex bolt, shaft = {shaft_length_in}\"")

    # ── Sketch 1 : hexagon on Top Plane → extrude head upward ────────────
    part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    sk.InsertSketch(True)
    part.ClearSelection2(True)

    _draw_hexagon(sk, R_hex_m)

    sk.InsertSketch(True)          # close sketch
    part.ClearSelection2(True)

    feat_head = _extrude(part, "Sketch1", H_m, flip=False)
    if feat_head is None:
        print("[SW] Warning: head extrusion returned None — check SolidWorks log.")

    # ── Sketch 2 : circle on Top Plane → extrude shaft downward ──────────
    part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
    sk.InsertSketch(True)
    part.ClearSelection2(True)

    sk.CreateCircle(0.0, 0.0, 0.0,   d_m / 2, 0.0, 0.0)

    sk.InsertSketch(True)
    part.ClearSelection2(True)

    feat_shaft = _extrude(part, "Sketch2", L_m, flip=True)
    if feat_shaft is None:
        print("[SW] Warning: shaft extrusion returned None — check SolidWorks log.")

    # ── Tip chamfer (optional) ─────────────────────────────────────────────
    chamfer_size = d_m * 0.075
    try:
        # The bottom circular edge of the shaft sits at Z = -L_m
        found = part.Extension.SelectByID2(
            "Edge<1>", "EDGE", 0.0, -L_m, 0.0, False, 0, None, 0
        )
        if found:
            part.FeatureManager.InsertFeatureChamfer(4, 1, False, chamfer_size, 0.7854, 0, 0, 0)
            part.ClearSelection2(True)
    except Exception:
        pass   # Chamfer is cosmetic — skip silently on error

    # ── Set view & rename ─────────────────────────────────────────────────
    label = f"{frac}-{tpi} Hex Bolt L={shaft_length_in}\""
    part.SetTitle2(label)
    part.ShowNamedView2("*Isometric", -1)
    part.ViewZoomtofit2()
    part.GraphicsRedraw2()

    # ── Save ──────────────────────────────────────────────────────────────
    if save_path:
        if not save_path.lower().endswith(".sldprt"):
            save_path += ".sldprt"
        part.SaveAs(save_path)
        print(f"[SW] Part saved → {save_path}")

    print(f"[SW] Done. Model '{label}' is open in SolidWorks.")
    return part
