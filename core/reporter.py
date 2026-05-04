#!/usr/bin/env python3
import os
import datetime
import signal
import sys
from core import dtc_db

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(_ROOT, "reports")
CHECKPOINTS_DIR = os.path.join(REPORTS_DIR, ".checkpoints")

MODE_TOTALS = {
    "quick_scan":      4,
    "full_scan":      80,
    "cylinder_test":   8,
    "catalyst_test":   6,
    "evap_test":       3,
    "adapter_info":    5,
    "clear_codes":     1,
    "uds_scan":       16,
    "ecu_fingerprint": 16,
}


class Reporter:
    def __init__(self, scan_mode):
        self.mode = scan_mode
        self.ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.chk_path = os.path.join(
            CHECKPOINTS_DIR, "{}_{}.chk".format(self.ts, self.mode)
        )
        self._chk_file = None

    def start(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
        self._chk_file = open(self.chk_path, "w", buffering=1)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def start_append(self):
        """Open existing checkpoint for appending (resume mode)."""
        if not os.path.exists(self.chk_path):
            raise FileNotFoundError(
                "start_append() requires existing checkpoint: {}".format(self.chk_path)
            )
        self._chk_file = open(self.chk_path, "a", buffering=1)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def checkpoint(self, line):
        if self._chk_file:
            self._chk_file.write(line + "\n")
            self._chk_file.flush()

    def flush(self):
        if self._chk_file:
            self._chk_file.flush()

    def finish(self):
        if self._chk_file is None and not os.path.exists(self.chk_path):
            raise RuntimeError("finish() called before start() — no checkpoint file at {}".format(self.chk_path))
        if self._chk_file:
            self._chk_file.close()
            self._chk_file = None
        with open(self.chk_path) as f:
            raw_lines = f.readlines()
        raw_path = os.path.join(REPORTS_DIR, "{}_{}.raw".format(self.ts, self.mode))
        md_path = os.path.join(REPORTS_DIR, "{}_{}.md".format(self.ts, self.mode))
        md_lines = []
        for line in raw_lines:
            enriched, _ = dtc_db.enrich_line(line.rstrip())
            md_lines.append(enriched + "\n")
        with open(raw_path, "w") as f:
            f.writelines(raw_lines)
        with open(md_path, "w") as f:
            f.write("# OBD-REAPER — {}\n".format(
                self.mode.upper().replace("_", " ")
            ))
            f.write("**Scan Date:** {}\n\n".format(self.ts))
            f.write("```\n")
            f.writelines(md_lines)
            f.write("```\n")
        os.remove(self.chk_path)
        return md_path

    def _signal_handler(self, sig, frame):
        self.flush()
        sys.exit(0)

    @classmethod
    def from_checkpoint(cls, chk_path):
        """Load existing .chk — returns (reporter, skip_count).

        reporter.finish()       → salvage (convert partial data to .md)
        reporter.start_append() → resume  (append new data, then finish())
        """
        fname = os.path.basename(chk_path)   # 2026-05-01_143022_quick_scan.chk
        stem = fname[:-4]                      # strip .chk
        first_us = stem.index("_")
        second_us = stem.index("_", first_us + 1)
        ts = stem[:second_us]                  # "2026-05-01_143022"
        mode = stem[second_us + 1:]            # "quick_scan"
        with open(chk_path) as f:
            skip = sum(1 for line in f if line.strip())
        r = cls(mode)
        r.ts = ts
        r.chk_path = chk_path
        return r, skip

    @staticmethod
    def find_incomplete():
        if not os.path.isdir(CHECKPOINTS_DIR):
            return []
        return sorted(
            os.path.join(CHECKPOINTS_DIR, f)
            for f in os.listdir(CHECKPOINTS_DIR)
            if f.endswith(".chk")
        )

    @staticmethod
    def list_reports():
        if not os.path.isdir(REPORTS_DIR):
            return []
        entries = []
        for fname in sorted(os.listdir(REPORTS_DIR)):
            if fname.endswith(".md"):
                path = os.path.join(REPORTS_DIR, fname)
                entries.append((fname, path, os.path.getsize(path)))
        return entries
