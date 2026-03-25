"""
Hex Screw Generator — natural language → SolidWorks 3-D model

Usage
-----
  python main.py

Then type descriptions like:
  "I want a 3/8 hex screw that fits in a 3/4 hole"
  "Create a 1/2-13 hex bolt, 2 inches long"
  "Make me a 1/4 inch hex cap screw fine thread"

Two output modes
----------------
  1. Macro file  (.swb)  — always generated; run it inside SolidWorks via
                           Tools → Macro → Run
  2. Direct COM  (Windows) — if SolidWorks is running and pywin32 is installed,
                             the model is created live.

Commands
--------
  quit / exit   — exit the program
  help          — show usage
"""

import os
import sys

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import anthropic  # noqa: F401
except ImportError:
    sys.exit(
        "anthropic package not found.\n"
        "Install with:  pip install anthropic"
    )

from parser import parse_request, resolve_spec
from screw_specs import format_spec, get_spec
from solidworks_macro import generate_macro

# Optional direct COM (Windows only)
_DIRECT_AVAILABLE = False
try:
    import win32com.client  # noqa: F401
    _DIRECT_AVAILABLE = True
except ImportError:
    pass


# ── Banner ────────────────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════════════╗
║          SolidWorks Hex Screw Generator                  ║
║  Describe a hex screw in plain English and this tool     ║
║  creates a 3-D SolidWorks model for you.                 ║
╚══════════════════════════════════════════════════════════╝
Examples:
  "I want a 3/8 hex screw that fits in a 3/4 hole"
  "Create a 1/2-13 hex bolt, 2 inches long"
  "Make a 1/4 inch fine-thread hex cap screw, 1.5 inches"

Type  help  for more info, or  quit  to exit.
"""


def run_chat():
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

        if user_input.lower() in ("help", "?", "h"):
            print(__doc__)
            continue

        print("\nParsing your request…")
        try:
            parsed = parse_request(user_input)
        except Exception as exc:
            print(f"  [Error] Could not parse request: {exc}\n")
            continue

        spec, warnings = resolve_spec(parsed)

        if spec is None:
            print("  Could not identify a standard hex screw from your description.")
            for w in warnings:
                print(f"  ! {w}")
            print()
            continue

        # ── Print resolved spec ───────────────────────────────────────────
        shaft_in = parsed.get("shaft_length_in") or 1.0
        print(f"\nResolved ANSI spec:\n{format_spec(spec)}")
        print(f"  Shaft length  : {shaft_in}\"")
        for w in warnings:
            print(f"  > {w}")

        # ── Confirm ───────────────────────────────────────────────────────
        print()
        confirm = input("Generate model? [Y/n]: ").strip().lower()
        if confirm in ("n", "no"):
            print("Skipped.\n")
            continue

        # ── Generate macro file ───────────────────────────────────────────
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        macro_path = generate_macro(spec, shaft_length_in=shaft_in, output_dir=output_dir)
        print(f"\n[✓] SolidWorks macro generated:\n    {macro_path}")
        print(
            "\n    To use it in SolidWorks:\n"
            "      Tools → Macro → Run → select the .swb file above\n"
        )

        # ── Attempt direct COM creation ───────────────────────────────────
        if _DIRECT_AVAILABLE:
            do_direct = input(
                "SolidWorks COM detected. Create model directly now? [Y/n]: "
            ).strip().lower()
            if do_direct not in ("n", "no"):
                try:
                    from solidworks_direct import create_hex_screw
                    safe_name = (
                        spec["fraction"].replace("/", "_").replace("-", "_")
                        + f"_L{shaft_in}in"
                    )
                    save_path = os.path.join(output_dir, f"hex_screw_{safe_name}.sldprt")
                    create_hex_screw(spec, shaft_length_in=shaft_in, save_path=save_path)
                    print(f"[✓] Part saved → {save_path}\n")
                except Exception as exc:
                    print(f"[!] Direct COM creation failed: {exc}")
                    print("    Use the .swb macro file instead.\n")
        else:
            print(
                "    (pywin32 / SolidWorks COM not found — macro file only)\n"
                "    Install pywin32 on Windows to enable live model creation.\n"
            )

        print("-" * 58)


if __name__ == "__main__":
    # Quick single-shot mode: python main.py "3/8 hex screw fits in 3/4 hole"
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"Request: {user_input}\n")
        parsed = parse_request(user_input)
        spec, warnings = resolve_spec(parsed)
        if spec:
            shaft_in = parsed.get("shaft_length_in") or 1.0
            print(format_spec(spec))
            print(f"  Shaft length  : {shaft_in}\"")
            for w in warnings:
                print(f"  > {w}")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            path = generate_macro(spec, shaft_length_in=shaft_in, output_dir=output_dir)
            print(f"\n[✓] Macro file: {path}")
        else:
            print("Could not resolve spec.")
            for w in warnings:
                print(f"  ! {w}")
    else:
        run_chat()
