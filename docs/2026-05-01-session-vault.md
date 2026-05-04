# SESSION VAULT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SESSION VAULT — a hacker-aesthetic recovery terminal that lets users salvage partial scan data or resume an interrupted scan from the exact command where it stopped.

**Architecture:** Three changes: (1) `Reporter` gains `from_checkpoint()` classmethod + `start_append()` method + `MODE_TOTALS` dict; (2) All 8 scan generators in `Scanner` gain a `skip=0` parameter — skipped steps yield empty log lines without sending OBD commands; (3) `tui.py` gains `_session_vault_screen()` function replacing the existing `_show_incomplete_notice()`, plus a new `[R]` main menu item.

**Tech Stack:** Python 3 stdlib — `curses`, `signal`, `os`, `importlib`; no new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `core/reporter.py` | Add `MODE_TOTALS` dict, `from_checkpoint()` classmethod, `start_append()` method |
| `core/scanner.py` | Add `skip=0` to 8 generators (`live_data` excluded) |
| `ui/tui.py` | Replace `_show_incomplete_notice()` with `_session_vault_screen()` + helpers; add `[R]` menu item; update import |
| `tests/test_reporter.py` | 4 new tests for `from_checkpoint` + `start_append` |
| `tests/test_scanner.py` | 5 new tests for skip parameter |

---

## Task 1: Reporter — MODE_TOTALS + from_checkpoint + start_append

**Files:**
- Modify: `core/reporter.py`
- Test: `tests/test_reporter.py`

- [ ] **Step 1: Write 4 failing tests**

Add to `tests/test_reporter.py` after the existing `TestReporter` class:

```python
class TestFromCheckpoint(unittest.TestCase):
    def test_parses_ts_mode_and_skip_count(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("03 -> 43 01 13")
        r.checkpoint("07 -> 47 00")
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        self.assertEqual(r2.ts, r.ts)
        self.assertEqual(r2.mode, "quick_scan")
        self.assertEqual(skip, 2)

    def test_empty_checkpoint_gives_skip_zero(self):
        r = make_reporter("full_scan")
        r.start()
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        self.assertEqual(skip, 0)

    def test_start_append_preserves_existing_lines(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("line1")
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        r2.start_append()
        r2.checkpoint("line2")
        r2._chk_file.close()
        with open(r2.chk_path) as f:
            content = f.read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)

    def test_salvage_produces_md_from_existing_chk(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("03 -> 43 01 13")
        r._chk_file.close()
        r2, _ = reporter_module.Reporter.from_checkpoint(r.chk_path)
        md_path = r2.finish()
        self.assertTrue(os.path.exists(md_path))
        self.assertFalse(os.path.exists(r2.chk_path))
        with open(md_path) as f:
            self.assertIn("43 01 13", f.read())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/test_reporter.py::TestFromCheckpoint -v
```

Expected: 4 errors — `AttributeError: type object 'Reporter' has no attribute 'from_checkpoint'`

- [ ] **Step 3: Add MODE_TOTALS, from_checkpoint, start_append to reporter.py**

Replace the entire `core/reporter.py` with:

```python
#!/usr/bin/env python3
import os
import datetime
import signal
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(_ROOT, "reports")
CHECKPOINTS_DIR = os.path.join(REPORTS_DIR, ".checkpoints")

MODE_TOTALS = {
    "quick_scan":    4,
    "full_scan":    64,
    "cylinder_test": 8,
    "catalyst_test": 6,
    "evap_test":     3,
    "adapter_info":  5,
    "clear_codes":   1,
    "uds_scan":     16,
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
            lines = f.readlines()
        raw_path = os.path.join(REPORTS_DIR, "{}_{}.raw".format(self.ts, self.mode))
        md_path = os.path.join(REPORTS_DIR, "{}_{}.md".format(self.ts, self.mode))
        with open(raw_path, "w") as f:
            f.writelines(lines)
        with open(md_path, "w") as f:
            f.write("# OBD-REAPER — {}\n".format(
                self.mode.upper().replace("_", " ")
            ))
            f.write("**Scan Date:** {}\n\n".format(self.ts))
            f.write("```\n")
            f.writelines(lines)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/test_reporter.py -v
```

Expected: 12 passed (8 existing + 4 new)

- [ ] **Step 5: Commit**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
git add core/reporter.py tests/test_reporter.py
git commit -m "feat: Reporter.from_checkpoint, start_append, MODE_TOTALS for session recovery"
```

---

## Task 2: Scanner — skip=0 on all 8 generators

**Files:**
- Modify: `core/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write 5 failing tests**

Add after the existing `TestLiveData` class in `tests/test_scanner.py`:

```python
class TestSkipParameter(unittest.TestCase):
    def test_quick_scan_skip_2_sends_2_commands(self):
        s = make_scanner()
        results = list(s.quick_scan(skip=2))
        self.assertEqual(len(results), 5)           # 4 steps + 1 final = always 5
        non_empty = [r for r in results if r[2]]
        self.assertEqual(len(non_empty), 2)          # only last 2 steps have data
        self.assertEqual(s.elm.send.call_count, 2)   # ELM called only for real steps

    def test_quick_scan_skip_0_unchanged(self):
        s = make_scanner()
        results = list(s.quick_scan(skip=0))
        self.assertEqual(len(results), 5)
        non_empty = [r for r in results if r[2]]
        self.assertEqual(len(non_empty), 4)
        self.assertEqual(s.elm.send.call_count, 4)

    def test_catalyst_test_skip_3_sends_3_commands(self):
        s = make_scanner()
        results = list(s.catalyst_test(skip=3))
        non_empty = [r for r in results if r[2]]
        self.assertEqual(len(non_empty), 3)
        # 3 real sends (steps 3,4,5 — 0-indexed)
        self.assertEqual(s.elm.send.call_count, 3)

    def test_clear_codes_skip_1_no_send(self):
        s = make_scanner()
        results = list(s.clear_codes(skip=1))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][2], "")          # empty line — no OBD command
        self.assertEqual(s.elm.send.call_count, 0)

    def test_adapter_info_skip_5_no_data_sends(self):
        s = make_scanner()
        results = list(s.adapter_info(skip=5))
        non_empty = [r for r in results if r[2]]
        self.assertEqual(len(non_empty), 0)
        # Only the final (100, "ADAPTER INFO COMPLETE", "") yield remains
        self.assertEqual(results[-1][0], 100)
        self.assertEqual(s.elm.send.call_count, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/test_scanner.py::TestSkipParameter -v
```

Expected: 5 errors — `TypeError: quick_scan() got an unexpected keyword argument 'skip'`

- [ ] **Step 3: Replace core/scanner.py with skip=0 on all 8 generators**

Replace `core/scanner.py` entirely:

```python
#!/usr/bin/env python3

LIVE_PIDS = [
    ("010C", "RPM"),
    ("010D", "Speed km/h"),
    ("0105", "Coolant C"),
    ("010F", "IAT C"),
    ("0110", "MAF g/s"),
    ("0111", "Throttle %"),
    ("0115", "O2 B1S1 V"),
]

FULL_PIDS = [
    ("0101", "MIL/Status"),   ("0103", "Fuel System"),
    ("0104", "Engine Load"),  ("0105", "Coolant Temp"),
    ("0106", "STFT Bank1"),   ("0107", "LTFT Bank1"),
    ("010B", "MAP kPa"),      ("010C", "RPM"),
    ("010D", "Speed km/h"),   ("010E", "Timing Adv"),
    ("010F", "IAT C"),        ("0110", "MAF g/s"),
    ("0111", "Throttle %"),   ("0113", "O2 Sensors"),
    ("0115", "O2 V B1S1"),    ("011C", "OBD Standard"),
    ("011F", "Runtime sec"),  ("0121", "Dist MIL km"),
    ("012C", "EGR Cmd %"),    ("012F", "Fuel Level %"),
    ("0130", "Warmups"),      ("0131", "Dist Cleared km"),
    ("0132", "EVAP Press"),   ("0133", "Baro kPa"),
    ("013C", "Cat Tmp B1S1"), ("013E", "Cat Tmp B1S2"),
    ("0141", "Mon Status"),   ("0142", "Ctrl Voltage"),
    ("0143", "Abs Load %"),   ("0145", "Rel Throttle %"),
    ("0146", "Ambient Temp"), ("014D", "Time MIL min"),
    ("014E", "Time Cleared"), ("015B", "HV Batt SOC %"),
]

UDS_ECUS = [
    ("7E0", "ECM"), ("7E1", "TCM"), ("7E2", "ABS"),
    ("7E3", "HCU"), ("7E4", "MCU"), ("7E5", "BCM"), ("7E6", "MISC"),
]

FREEZE_PIDS = [
    ("0202", "FF DTC"), ("0204", "FF Load"), ("0205", "FF Coolant"),
    ("0206", "FF STFT"), ("020B", "FF MAP"), ("020C", "FF RPM"),
    ("020D", "FF Speed"), ("020E", "FF Timing"),
]

MODE06_PIDS = [
    ("0681", "Misfire General"),
    ("0682", "Misfire Cyl 1"), ("0683", "Misfire Cyl 2"),
    ("0684", "Misfire Cyl 3"), ("0685", "Misfire Cyl 4"),
    ("0621", "Catalyst B1"),   ("0622", "Catalyst B2"),
    ("0631", "EVAP"),
]


class Scanner:
    def __init__(self, elm):
        self.elm = elm

    def quick_scan(self, skip=0):
        steps = [
            ("03",   "Active DTCs",    3.0),
            ("07",   "Pending DTCs",   3.0),
            ("0A",   "Permanent DTCs", 3.0),
            ("0101", "MIL Status",     2.0),
        ]
        for i, (cmd, label, wait) in enumerate(steps):
            pct = int(i / len(steps) * 100)
            if i < skip:
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            yield (pct, label, "{} -> {}".format(cmd, raw))
        yield (100, "SCAN COMPLETE", "")

    def full_scan(self, skip=0):
        dtc_steps = [
            ("0A", "Permanent DTCs", 3.0),
            ("03", "Active DTCs",    3.0),
            ("07", "Pending DTCs",   3.0),
            ("0101", "MIL Status",   2.0),
        ]
        total = len(dtc_steps) + len(UDS_ECUS) + len(FULL_PIDS) + len(FREEZE_PIDS) + len(MODE06_PIDS) + 3
        done = 0

        for cmd, label, wait in dtc_steps:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        for addr, name in UDS_ECUS:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, "UDS {}".format(name), "")
                continue
            self.elm.send("ATSH {}".format(addr), wait=1.0)
            raw = self.elm.send("1902 FF", wait=4.0)
            done += 1
            yield (pct, "UDS {}".format(name),
                   "ATSH {} | 1902 FF -> {}".format(addr, raw))
        self.elm.send("ATSH 7DF", wait=1.0)

        for cmd, label in FULL_PIDS:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=1.5)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        for cmd, label in FREEZE_PIDS:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=1.5)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        for cmd, label in MODE06_PIDS:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=2.0)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        for pid in ["0902", "0904", "0906"]:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, "Vehicle Info", "")
                continue
            raw = self.elm.send(pid, wait=2.0)
            done += 1
            yield (pct, "Vehicle Info", "{} -> {}".format(pid, raw))

        yield (100, "FULL SCAN COMPLETE", "")

    def live_data(self):
        while True:
            readings = {}
            for cmd, name in LIVE_PIDS:
                readings[name] = self.elm.send(cmd, wait=0.5)
            yield readings

    def clear_codes(self, skip=0):
        if skip >= 1:
            yield (100, "CODES CLEARED", "")
            return
        raw = self.elm.send("04", wait=3.0)
        yield (100, "CODES CLEARED", "04 -> {}".format(raw))

    def cylinder_test(self, skip=0):
        mode06 = [
            ("0682", "Misfire Cyl 1", 2.0),
            ("0683", "Misfire Cyl 2", 2.0),
            ("0684", "Misfire Cyl 3", 2.0),
            ("0685", "Misfire Cyl 4", 2.0),
        ]
        mode22 = [
            ("22D100", "Cyl 1 Data", 2.0),
            ("22D101", "Cyl 2 Data", 2.0),
            ("22D102", "Cyl 3 Data", 2.0),
            ("22D103", "Cyl 4 Data", 2.0),
        ]
        total = len(mode06) + len(mode22)
        done = 0

        for cmd, label, wait in mode06:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        self.elm.send("ATSH 7E0", wait=1.0)
        for cmd, label, wait in mode22:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))
        self.elm.send("ATSH 7DF", wait=1.0)
        yield (100, "CYLINDER TEST COMPLETE", "")

    def catalyst_test(self, skip=0):
        steps = [
            ("013C", "Cat Temp B1S1",  2.0),
            ("013E", "Cat Temp B1S2",  2.0),
            ("0621", "Catalyst B1",    2.0),
            ("0622", "Catalyst B2",    2.0),
            ("0601", "O2 Sensor B1S1", 2.0),
            ("0602", "O2 Sensor B1S2", 2.0),
        ]
        for i, (cmd, label, wait) in enumerate(steps):
            pct = int(i / len(steps) * 100)
            if i < skip:
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            yield (pct, label, "{} -> {}".format(cmd, raw))
        yield (100, "CATALYST TEST COMPLETE", "")

    def evap_test(self, skip=0):
        steps = [
            ("012E", "Cmd EVAP Purge",  2.0),
            ("0132", "EVAP Pressure",   2.0),
            ("0631", "EVAP System",     2.0),
        ]
        for i, (cmd, label, wait) in enumerate(steps):
            pct = int(i / len(steps) * 100)
            if i < skip:
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            yield (pct, label, "{} -> {}".format(cmd, raw))
        yield (100, "EVAP TEST COMPLETE", "")

    def uds_scan(self, plugin, skip=0):
        cmds = plugin.COMMANDS
        self.elm.send("ATSH 7E0", wait=1.0)
        for i, (cmd, label) in enumerate(cmds):
            pct = int(i / len(cmds) * 100)
            if i < skip:
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=2.0)
            interpreted = plugin.interpret(cmd, raw)
            yield (pct, label,
                   "{} -> {}".format(cmd, interpreted if interpreted else raw))
        self.elm.send("ATSH 7DF", wait=1.0)
        yield (100, "UDS SCAN COMPLETE", "")

    def adapter_info(self, skip=0):
        cmds = [
            ("ATI",   "Firmware Version", 1.0),
            ("ATRV",  "Battery Voltage",  1.0),
            ("ATDP",  "Protocol Name",    1.0),
            ("ATDPN", "Protocol Number",  1.0),
            ("ATIGN", "Ignition Signal",  1.0),
        ]
        for i, (cmd, label, wait) in enumerate(cmds):
            pct = int(i / len(cmds) * 100)
            if i < skip:
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=wait)
            yield (pct, label, "{} -> {}".format(cmd, raw))
        yield (100, "ADAPTER INFO COMPLETE", "")
```

- [ ] **Step 4: Run all scanner tests to verify pass**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/test_scanner.py -v
```

Expected: 18 passed (13 existing + 5 new)

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/ -v
```

Expected: 30 passed total

- [ ] **Step 6: Commit**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
git add core/scanner.py tests/test_scanner.py
git commit -m "feat: skip=0 parameter on all 8 scan generators for session resume"
```

---

## Task 3: TUI — SESSION VAULT screen + menu integration

**Files:**
- Modify: `ui/tui.py`

- [ ] **Step 1: Update import line at top of tui.py**

Find line 13 (the Reporter import):
```python
from core.reporter import Reporter
```

Replace with:
```python
from core.reporter import Reporter, MODE_TOTALS
```

- [ ] **Step 2: Add SESSION VAULT to MENU_ITEMS and MENU_ACTIONS**

Find `MENU_ITEMS` (lines 20-31) and replace:
```python
MENU_ITEMS = [
    ("1", "QUICK SCAN",    "DTCs + status"),
    ("2", "FULL SCAN",     "all systems"),
    ("3", "LIVE DATA",     "realtime stream"),
    ("4", "CLEAR CODES",   "erase DTCs — CAUTION"),
    ("5", "CYLINDER TEST", "misfire per cylinder"),
    ("6", "CATALYST TEST", "O2 + catalyst temps"),
    ("7", "EVAP TEST",     "fuel vapor system"),
    ("8", "UDS / VEHICLE", "manufacturer data"),
    ("9", "SAVED REPORTS", "browse logs"),
    ("0", "ADAPTER INFO",  "ELM327 status"),
    ("R", "SESSION VAULT", "recover interrupted scans"),
]
```

Find `MENU_ACTIONS` (lines 33-37) and replace:
```python
MENU_ACTIONS = [
    "quick_scan", "full_scan", "live_data", "clear_codes",
    "cylinder_test", "catalyst_test", "evap_test", "uds_scan",
    "report_browser", "adapter_info", "session_vault",
]
```

- [ ] **Step 3: Update run() to call _session_vault_screen instead of _show_incomplete_notice**

Find in `run()` (lines 51-53):
```python
    incomplete = Reporter.find_incomplete()
    if incomplete:
        _show_incomplete_notice(stdscr, incomplete)
```

Replace with:
```python
    incomplete = Reporter.find_incomplete()
    if incomplete:
        _session_vault_screen(stdscr, incomplete, port=port, usb_reset=usb_reset)
```

- [ ] **Step 4: Add session_vault branch to _dispatch()**

Find `_dispatch()` — after the line `if action == "report_browser":` block (around line 158), add a new branch. Insert before `if action == "clear_codes":`:

```python
    if action == "session_vault":
        incomplete = Reporter.find_incomplete()
        _session_vault_screen(stdscr, incomplete,
                               scanner=scanner, plugins=plugins)
        return
```

- [ ] **Step 5: Replace _show_incomplete_notice with _session_vault_screen and helpers**

Delete the existing `_show_incomplete_notice` function (lines 425-441) and replace with the following four functions. Insert them in the `# ── UI helpers ──` section just before `_confirm`:

```python
def _session_vault_screen(stdscr, incomplete, scanner=None, plugins=None,
                           port=None, usb_reset=True):
    sessions = _vault_parse_sessions(incomplete)
    if not sessions:
        _show_message(stdscr, "NO INTERRUPTED SESSIONS FOUND", 1500)
        return

    sel = 0
    while sessions:
        _vault_draw(stdscr, sessions, sel)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_UP:
            sel = max(0, sel - 1)
        elif key == curses.KEY_DOWN:
            sel = min(len(sessions) - 1, sel + 1)
        elif key in (ord("s"), ord("S")):
            _vault_salvage(stdscr, sessions[sel])
            sessions.pop(sel)
            sel = min(sel, max(0, len(sessions) - 1))
        elif key in (ord("r"), ord("R")):
            active_scanner = scanner
            active_plugins = plugins or {}
            if active_scanner is None:
                elm = _vault_connect(stdscr, port, usb_reset)
                if elm is None:
                    _show_message(stdscr,
                        "CONNECTION FAILED — press [S] to salvage or [D] to discard",
                        2500)
                    continue
                active_scanner = Scanner(elm)
                active_plugins = load_plugins()
                try:
                    _vault_resume(stdscr, sessions[sel], active_scanner, active_plugins)
                finally:
                    elm.close()
            else:
                _vault_resume(stdscr, sessions[sel], active_scanner, active_plugins)
            sessions.pop(sel)
            sel = min(sel, max(0, len(sessions) - 1))
        elif key in (ord("d"), ord("D")):
            if _confirm(stdscr,
                        "DISCARD checkpoint? All partial data will be lost.",
                        "[Y] Yes   [N] No"):
                os.remove(sessions[sel]["path"])
                sessions.pop(sel)
                sel = min(sel, max(0, len(sessions) - 1))


def _vault_parse_sessions(incomplete):
    sessions = []
    for path in incomplete:
        fname = os.path.basename(path)
        stem = fname[:-4]
        try:
            first_us = stem.index("_")
            second_us = stem.index("_", first_us + 1)
            ts = stem[:second_us]
            mode = stem[second_us + 1:]
        except ValueError:
            continue
        with open(path) as f:
            line_count = sum(1 for ln in f if ln.strip())
        sessions.append({"path": path, "ts": ts, "mode": mode, "lines": line_count})
    return sessions


def _vault_draw(stdscr, sessions, sel):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)
    warn   = curses.color_pair(C_WARN)  | curses.A_BOLD

    box_w = min(74, w - 2)
    box_h = len(sessions) + 12
    by = max(0, (h - box_h) // 2)
    bx = max(0, (w - box_w) // 2)

    _draw_box(stdscr, by, bx, box_h, box_w,
              "REAPER SESSION VAULT — FIELD RECOVERY MODE", bright)
    _addstr_safe(stdscr, by + 2, bx + 3,
                 "!  INTERRUPTED MISSIONS DETECTED — ALL DATA PRESERVED", warn)

    for i, sess in enumerate(sessions):
        row = by + 4 + i
        mode_disp = sess["mode"].upper()[:14]
        ts_disp   = sess["ts"]
        lines     = sess["lines"]
        total     = MODE_TOTALS.get(sess["mode"])
        if total is None and sess["mode"].startswith("uds_"):
            total = MODE_TOTALS.get("uds_scan", 16)
        total = total or 20
        pct    = min(100, int(lines / max(1, total) * 100))
        filled = int(10 * pct / 100)
        bar    = "[" + "█" * filled + "░" * (10 - filled) + "]"
        line   = "  [{:1d}]  {:19}  {:14}  {}  {:3d} ln  {:3d}%".format(
            i + 1, ts_disp, mode_disp, bar, lines, pct)
        attr = curses.A_REVERSE | bright if i == sel else green
        try:
            stdscr.addstr(row, bx + 1, line[:box_w - 2].ljust(box_w - 2), attr)
        except curses.error:
            pass

    sep_row = by + 4 + len(sessions) + 1
    _addstr_safe(stdscr, sep_row,     bx + 2,
                 "─" * (box_w - 4), green)
    _addstr_safe(stdscr, sep_row + 1, bx + 3,
                 "[S]  SALVAGE REPORT  — convert partial data to .md now", green)
    _addstr_safe(stdscr, sep_row + 2, bx + 3,
                 "[R]  RESUME MISSION  — reconnect to vehicle + continue", green)
    _addstr_safe(stdscr, sep_row + 3, bx + 3,
                 "[D]  DISCARD         — delete checkpoint, abort mission", green)
    _addstr_safe(stdscr, sep_row + 4, bx + 3,
                 "[Q]  BACK TO MENU    — [↑↓] navigate sessions", green)
    stdscr.refresh()


def _vault_salvage(stdscr, session):
    _show_message(stdscr, "SALVAGING DATA...", 800)
    reporter, _ = Reporter.from_checkpoint(session["path"])
    md_path = reporter.finish()
    _show_message(stdscr,
                  "REPORT SAVED: {}".format(os.path.basename(md_path)), 1500)


def _vault_connect(stdscr, port, usb_reset):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    _addstr_safe(stdscr, h // 2,
                 max(0, (w - 38) // 2),
                 "[ RECONNECTING TO TARGET VEHICLE... ]", bright)
    stdscr.refresh()
    elm = ELM327(port=port)
    try:
        elm.connect(usb_reset=usb_reset)
        return elm
    except ELMConnectionError:
        return None


def _vault_resume(stdscr, session, scanner, plugins):
    mode = session["mode"]
    skip = session["lines"]
    reporter, _ = Reporter.from_checkpoint(session["path"])
    reporter.start_append()

    simple_modes = {
        "quick_scan", "full_scan", "cylinder_test", "catalyst_test",
        "evap_test", "adapter_info", "clear_codes",
    }
    if mode in simple_modes:
        gen   = getattr(scanner, mode)(skip=skip)
        title = "RESUME: " + mode.upper().replace("_", " ")[:18]
    elif mode.startswith("uds_"):
        vehicle_id = mode[4:]
        plugin = next(
            (p for p in plugins.values() if p.VEHICLE_ID == vehicle_id), None)
        if plugin is None:
            reporter._chk_file.close()
            reporter._chk_file = None
            _show_message(stdscr, "PLUGIN NOT FOUND — SALVAGING DATA...", 1000)
            r2, _ = Reporter.from_checkpoint(session["path"])
            r2.finish()
            return
        gen   = scanner.uds_scan(plugin, skip=skip)
        title = "RESUME UDS: " + vehicle_id[:14].upper()
    else:
        reporter._chk_file.close()
        reporter._chk_file = None
        _show_message(stdscr, "UNKNOWN MODE — SALVAGING DATA...", 1000)
        r2, _ = Reporter.from_checkpoint(session["path"])
        r2.finish()
        return

    _scan_screen(stdscr, title, gen, reporter)
    try:
        md_path = reporter.finish()
        _show_message(stdscr,
                      "MISSION COMPLETE: {}".format(os.path.basename(md_path)),
                      2000)
    except Exception as e:
        _show_message(stdscr, "Save error: {}".format(e), 2000)
```

- [ ] **Step 6: Run full test suite**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -m pytest tests/ -v
```

Expected: 30 passed — no regressions

- [ ] **Step 7: Smoke-test tui.py imports cleanly**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python3 -c "from ui.tui import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
git add ui/tui.py
git commit -m "feat: SESSION VAULT — hacker recovery terminal with salvage + resume"
```

---

## Self-Review

**Spec coverage:**
- ✅ Salvage: `_vault_salvage()` → `from_checkpoint()` + `finish()`
- ✅ Resume: `_vault_resume()` → `from_checkpoint()` + `start_append()` + `scanner.<mode>(skip=N)`
- ✅ Discard: `os.remove(path)` with confirm prompt
- ✅ Auto-open on startup: `run()` calls `_session_vault_screen` if incomplete
- ✅ Manual menu item `[R]` always accessible
- ✅ Progress bar per session in `_vault_draw` using `MODE_TOTALS`
- ✅ Connection failed fallback: message shown, session stays in list
- ✅ UDS plugin lookup by `VEHICLE_ID`
- ✅ `live_data` excluded from skip (no `skip=0` added)
- ✅ `MODE_TOTALS` dict with all 8 modes

**Type consistency:**
- `from_checkpoint()` returns `(Reporter, int)` — used as `reporter, skip = ...` in both `_vault_salvage` and `_vault_resume` ✓
- `start_append()` on reporter — called only in `_vault_resume` ✓
- `scanner.<mode>(skip=skip)` — all 8 generators accept `skip=0` ✓
- `MODE_TOTALS` imported from `core.reporter` in `tui.py` ✓
