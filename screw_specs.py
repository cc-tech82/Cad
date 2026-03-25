"""
ANSI/ASME B18.2.1 Hex Bolt Standard Dimensions (inches)
Covers sizes 1/4" through 1-1/2".
"""

# key = nominal diameter (decimal inches)
# W    = width across flats (inches)
# H    = head height (inches)
# tpi  = threads per inch (coarse / UNC)
# tpif = threads per inch (fine  / UNF)
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

# Common fraction-to-decimal mappings for parsing
FRACTION_MAP = {
    "10":    0.1900,
    "#10":   0.1900,
    "1/4":   0.2500,
    "5/16":  0.3125,
    "3/8":   0.3750,
    "7/16":  0.4375,
    "1/2":   0.5000,
    "9/16":  0.5625,
    "5/8":   0.6250,
    "3/4":   0.7500,
    "7/8":   0.8750,
    "1":     1.0000,
    "1-1/8": 1.1250,
    "1-1/4": 1.2500,
    "1-3/8": 1.3750,
    "1-1/2": 1.5000,
}


def get_spec(nominal_dia_in: float) -> dict | None:
    """Return spec dict for the closest matching nominal diameter."""
    closest = min(ANSI_HEX_SPECS.keys(), key=lambda k: abs(k - nominal_dia_in))
    if abs(closest - nominal_dia_in) < 0.02:          # within 0.02" tolerance
        return {"nominal": closest, **ANSI_HEX_SPECS[closest]}
    return None


def circumscribed_radius(W: float) -> float:
    """Return circumscribed circle radius (vertex to center) from width-across-flats."""
    import math
    return (W / 2.0) / math.cos(math.pi / 6)


def fits_in_hole(W: float, hole_dia: float) -> bool:
    """Check whether the hex head fits through a round hole of the given diameter."""
    return circumscribed_radius(W) * 2 <= hole_dia


def largest_screw_that_fits(hole_dia: float) -> float | None:
    """Return the largest nominal diameter whose head fits through hole_dia."""
    candidates = [
        nom for nom, spec in ANSI_HEX_SPECS.items()
        if fits_in_hole(spec["W"], hole_dia)
    ]
    return max(candidates) if candidates else None


def format_spec(spec: dict) -> str:
    """Human-readable summary of a spec dict."""
    return (
        f"  Size          : {spec['fraction']}\" ({spec['nominal']:.4f}\")\n"
        f"  Across flats  : {spec['W']:.4f}\"  ({spec['W'] * 25.4:.2f} mm)\n"
        f"  Head height   : {spec['H']:.4f}\"  ({spec['H'] * 25.4:.2f} mm)\n"
        f"  Thread (UNC)  : {spec['fraction']}-{spec['tpi']} (coarse)\n"
        f"  Thread (UNF)  : {spec['fraction']}-{spec['tpif']} (fine)\n"
        f"  Circ. dia     : {circumscribed_radius(spec['W']) * 2:.4f}\"  "
        f"(min hole to pass head)"
    )
