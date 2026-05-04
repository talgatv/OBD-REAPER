#!/usr/bin/env python3
"""OBD-REAPER — Hacker-style terminal vehicle diagnostic scanner v1.0"""
import argparse
import curses
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.tui import run


def main():
    parser = argparse.ArgumentParser(
        prog="reaper",
        description="OBD-REAPER: terminal OBD2 scanner for ELM327 adapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 reaper.py
  sudo python3 reaper.py --port /dev/ttyACM0
  sudo python3 reaper.py --no-usb-reset
        """,
    )
    parser.add_argument(
        "--port", default=None,
        help="Serial port (e.g. /dev/ttyACM0). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--no-usb-reset", action="store_true",
        help="Skip USB reset on startup (faster, but may fail if adapter is asleep).",
    )
    args = parser.parse_args()

    try:
        curses.wrapper(run, port=args.port, usb_reset=not args.no_usb_reset)
    except KeyboardInterrupt:
        print("\n[REAPER] Interrupted. Partial scan data saved to reports/")
        sys.exit(0)
    except Exception as e:
        print("\n[REAPER] Fatal error: {}".format(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
