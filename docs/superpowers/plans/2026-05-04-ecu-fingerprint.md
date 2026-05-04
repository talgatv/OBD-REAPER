# ECU FINGERPRINT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Probe all 16 UDS addresses (7E0–7EF) with `10 01`, display a live-updating hacker ECU map as a standalone menu item `[E]`, and prepend the same 16-step block to `full_scan()`.

**Architecture:** `ecu_fingerprint()` is a new generator on `Scanner` following the identical `yield (pct, label, line)` / `skip=0` contract as every other generator. A custom TUI screen builds a 16-slot results array in real time. `full_scan()` gains 16 steps at the front (no timing measurement). `reporter.py` gets two `MODE_TOTALS` updates. `_vault_resume` adds `"ecu_fingerprint"` to `simple_modes`.

**Tech Stack:** Python 3 stdlib (`time`, `curses`); `unittest.mock.MagicMock`

---

### Task 1: scanner.py — constants + `ecu_fingerprint()` generator

**Files:**
- Modify: `core/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_scanner.py` (after the existing `TestSkipParameter` class):

```python
class TestEcuFingerprint(unittest.TestCase):
    def _make_scanner(self, responses):
        elm = MagicMock()
        elm.send.side_effect = responses
        return Scanner(elm)

    def test_yields_16_probe_steps_plus_complete(self):
        responses = []
        for _ in range(16):
            responses.append("OK")       # ATSH
            responses.append("NO DATA")  # 10 01
        responses.append("OK")           # ATSH 7DF reset
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        data_steps = [st for st in steps if st[1] != "ECU FINGERPRINT COMPLETE"]
        complete   = [st for st in steps if st[1] == "ECU FINGERPRINT COMPLETE"]
        self.assertEqual(len(data_steps), 16)
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0][0], 100)

    def test_active_response_produces_active_line(self):
        responses = ["OK", "50 01 00 19 01 F4"] + ["OK", "NO DATA"] * 15 + ["OK"]
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        self.assertIn("ACTIVE", steps[0][2])
        self.assertIn("7E0",    steps[0][2])

    def test_no_data_response_produces_silent_line(self):
        responses = ["OK", "NO DATA"] * 16 + ["OK"]
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        self.assertIn("SILENT", steps[0][2])

    def test_skip_skips_elm_calls(self):
        # skip=8: steps 0-7 yield empty, steps 8-15 probe for real + reset
        # ELM calls: 8 probes × 2 (ATSH + 10 01) + 1 reset = 17
        responses = ["OK", "50 01 00 19 01 F4"] * 8 + ["OK"]
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint(skip=8))
        probe_steps = [st for st in steps if st[1] != "ECU FINGERPRINT COMPLETE"]
        skipped = [st for st in probe_steps if st[2] == ""]
        self.assertEqual(len(skipped), 8)
        self.assertEqual(s.elm.send.call_count, 17)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/home/denim/Projects/AI shorts progs/OBD-REAPER"
python -m pytest tests/test_scanner.py::TestEcuFingerprint -v
```

Expected: 4 errors — `AttributeError: 'Scanner' object has no attribute 'ecu_fingerprint'`

- [ ] **Step 3: Add `import time as _time` at top of core/scanner.py**

Insert after the shebang line (`#!/usr/bin/env python3`):

```
Old:
#!/usr/bin/env python3

LIVE_PIDS = [

New:
#!/usr/bin/env python3
import time as _time

LIVE_PIDS = [
```

- [ ] **Step 4: Add constants before the Scanner class**

Insert after the `MODE06_PIDS` block and before `class Scanner:`:

```python
FINGERPRINT_ADDRS = [
    "7E0", "7E1", "7E2", "7E3", "7E4", "7E5", "7E6", "7E7",
    "7E8", "7E9", "7EA", "7EB", "7EC", "7ED", "7EE", "7EF",
]

ECU_NAMES = {
    "7E0": "ECM",   "7E1": "TCM",   "7E2": "ABS",   "7E3": "HCU",
    "7E4": "MCU",   "7E5": "BCM",   "7E6": "MISC",  "7E7": "SCM",
    "7E8": "ECM-R", "7E9": "TCM-R", "7EA": "ABS-R", "7EB": "HCU-R",
    "7EC": "MCU-R", "7ED": "BCM-R", "7EE": "MSC-R", "7EF": "SCM-R",
}
```

- [ ] **Step 5: Add `ecu_fingerprint()` method to the Scanner class**

Append after the `adapter_info` method (before the final empty line at end of file):

```python
    def ecu_fingerprint(self, skip=0):
        total = len(FINGERPRINT_ADDRS)
        for i, addr in enumerate(FINGERPRINT_ADDRS):
            pct = int(i / total * 100)
            name = ECU_NAMES.get(addr, "???")
            label = "{} {}".format(addr, name)
            if i < skip:
                yield (pct, label, "")
                continue
            self.elm.send("ATSH {}".format(addr), wait=0.3)
            t0 = _time.time()
            raw = self.elm.send("10 01", wait=0.6)
            elapsed_ms = int((_time.time() - t0) * 1000)
            if raw.upper().startswith("50"):
                line = "FINGERPRINT {} {} ACTIVE {}ms {}".format(
                    addr, name, elapsed_ms, raw[:24])
            else:
                line = "FINGERPRINT {} {} SILENT —".format(addr, name)
            yield (pct, label, line)
        self.elm.send("ATSH 7DF", wait=0.3)
        yield (100, "ECU FINGERPRINT COMPLETE", "")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_scanner.py::TestEcuFingerprint -v
```

Expected: 4 PASSED

- [ ] **Step 7: Run full test suite for regressions**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: all existing tests pass (no regressions)

- [ ] **Step 8: Commit**

```bash
git add core/scanner.py tests/test_scanner.py
git commit -m "feat: add FINGERPRINT_ADDRS, ECU_NAMES, and ecu_fingerprint() generator"
```

---

### Task 2: scanner.py + reporter.py — full_scan integration

**Files:**
- Modify: `core/scanner.py` (`full_scan` method only)
- Modify: `core/reporter.py` (`MODE_TOTALS` only)
- Test: `tests/test_scanner.py` (update 1 existing test + add 1 new test)

- [ ] **Step 1: Update the broken test and add a new test**

In `tests/test_scanner.py`, inside `class TestSkipParameter`, replace `test_full_scan_skip_past_uds_boundary`:

```python
    def test_full_scan_skip_past_uds_boundary(self):
        # skip=27 means: 16 fingerprint + 4 dtc_steps + 7 UDS_ECUS all done, first FULL_PID is next
        s = make_scanner()
        results = list(s.full_scan(skip=27))
        non_empty = [r for r in results if r[2]]
        # 80 total data steps, 27 skipped = 53 real data lines
        self.assertEqual(len(non_empty), 53)
```

Add directly after that test:

```python
    def test_full_scan_yields_81_steps(self):
        s = make_scanner()
        steps = list(s.full_scan())
        # 16 fingerprint + 4 dtc + 7 uds + 34 pids + 8 freeze + 8 mode06 + 3 vehicle = 80 data
        # + 1 FULL SCAN COMPLETE = 81 total
        self.assertEqual(len(steps), 81)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scanner.py::TestSkipParameter::test_full_scan_skip_past_uds_boundary tests/test_scanner.py::TestSkipParameter::test_full_scan_yields_81_steps -v
```

Expected: both FAIL — `test_full_scan_skip_past_uds_boundary` gets 42 non-empty (expected 53); `test_full_scan_yields_81_steps` gets 65 (expected 81)

- [ ] **Step 3: Update `full_scan()` in core/scanner.py**

Replace the `total = ...` line and the function body up to (but not including) the dtc_steps loop. The old code (lines 80–92):

```python
        total = len(dtc_steps) + len(UDS_ECUS) + len(FULL_PIDS) + len(FREEZE_PIDS) + len(MODE06_PIDS) + 3
        done = 0

        for cmd, label, wait in dtc_steps:
```

Replace with:

```python
        total = len(FINGERPRINT_ADDRS) + len(dtc_steps) + len(UDS_ECUS) + \
                len(FULL_PIDS) + len(FREEZE_PIDS) + len(MODE06_PIDS) + 3
        done = 0

        # ECU Fingerprint probe (16 steps)
        for addr in FINGERPRINT_ADDRS:
            pct = int(done / total * 100)
            name = ECU_NAMES.get(addr, "???")
            label = "FP {}".format(addr)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            self.elm.send("ATSH {}".format(addr), wait=0.3)
            raw = self.elm.send("10 01", wait=0.6)
            done += 1
            if raw.upper().startswith("50"):
                yield (pct, label,
                       "FINGERPRINT {} {} ACTIVE {}".format(addr, name, raw[:24]))
            else:
                yield (pct, label,
                       "FINGERPRINT {} {} SILENT —".format(addr, name))
        self.elm.send("ATSH 7DF", wait=0.3)

        for cmd, label, wait in dtc_steps:
```

- [ ] **Step 4: Update `MODE_TOTALS` in core/reporter.py**

Replace the `MODE_TOTALS` dict:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_scanner.py::TestSkipParameter::test_full_scan_skip_past_uds_boundary tests/test_scanner.py::TestSkipParameter::test_full_scan_yields_81_steps -v
```

Expected: 2 PASSED

- [ ] **Step 6: Run full test suite for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add core/scanner.py core/reporter.py tests/test_scanner.py
git commit -m "feat: prepend 16-step ECU fingerprint block to full_scan(); update MODE_TOTALS"
```

---

### Task 3: tui.py — import, menu, dispatch, `_ecu_fingerprint_screen()`

**Files:**
- Modify: `ui/tui.py`

No new unit tests — curses TUI functions require hardware-level mocking that isn't in the existing test suite and is out of scope for this feature.

- [ ] **Step 1: Update import line in ui/tui.py**

Replace:

```python
from core.scanner import Scanner
```

With:

```python
from core.scanner import Scanner, FINGERPRINT_ADDRS, ECU_NAMES
```

- [ ] **Step 2: Add menu entry to MENU_ITEMS and MENU_ACTIONS**

Replace:

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

MENU_ACTIONS = [
    "quick_scan", "full_scan", "live_data", "clear_codes",
    "cylinder_test", "catalyst_test", "evap_test", "uds_scan",
    "report_browser", "adapter_info", "session_vault",
]
```

With:

```python
MENU_ITEMS = [
    ("1", "QUICK SCAN",      "DTCs + status"),
    ("2", "FULL SCAN",       "all systems"),
    ("3", "LIVE DATA",       "realtime stream"),
    ("4", "CLEAR CODES",     "erase DTCs — CAUTION"),
    ("5", "CYLINDER TEST",   "misfire per cylinder"),
    ("6", "CATALYST TEST",   "O2 + catalyst temps"),
    ("7", "EVAP TEST",       "fuel vapor system"),
    ("8", "UDS / VEHICLE",   "manufacturer data"),
    ("9", "SAVED REPORTS",   "browse logs"),
    ("0", "ADAPTER INFO",    "ELM327 status"),
    ("R", "SESSION VAULT",   "recover interrupted scans"),
    ("E", "ECU FINGERPRINT", "probe all ECU addresses"),
]

MENU_ACTIONS = [
    "quick_scan", "full_scan", "live_data", "clear_codes",
    "cylinder_test", "catalyst_test", "evap_test", "uds_scan",
    "report_browser", "adapter_info", "session_vault", "ecu_fingerprint",
]
```

- [ ] **Step 3: Add dispatch branch in `_dispatch()`**

In the `_dispatch` function, insert the `ecu_fingerprint` branch after the `uds_scan` block (before the `clear_codes` check), i.e. replace:

```python
    if action == "uds_scan":
        _uds_plugin_menu(stdscr, scanner, plugins)
        return
    if action == "clear_codes":
```

With:

```python
    if action == "uds_scan":
        _uds_plugin_menu(stdscr, scanner, plugins)
        return
    if action == "ecu_fingerprint":
        reporter = Reporter("ecu_fingerprint")
        reporter.start()
        _ecu_fingerprint_screen(stdscr, scanner, reporter)
        try:
            md_path = reporter.finish()
            _show_message(stdscr, "REPORT SAVED: {}".format(os.path.basename(md_path)), 1500)
        except Exception as e:
            _show_message(stdscr, "Save error: {}".format(e), 2000)
        return
    if action == "clear_codes":
```

- [ ] **Step 4: Add `"ecu_fingerprint"` to `simple_modes` in `_vault_resume()`**

Replace:

```python
    simple_modes = {
        "quick_scan", "full_scan", "cylinder_test", "catalyst_test",
        "evap_test", "adapter_info", "clear_codes",
    }
```

With:

```python
    simple_modes = {
        "quick_scan", "full_scan", "cylinder_test", "catalyst_test",
        "evap_test", "adapter_info", "clear_codes", "ecu_fingerprint",
    }
```

- [ ] **Step 5: Add `_ecu_fingerprint_screen()` function**

Insert before the `# ── UI helpers ──` comment block (i.e., before the `_session_vault_screen` definition):

```python
# ── ECU Fingerprint screen ────────────────────────────────────────────────────

def _ecu_fingerprint_screen(stdscr, scanner, reporter):
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)
    warn   = curses.color_pair(C_WARN)

    results = [None] * 16  # None = not yet probed; dict = {"status", "ms", "raw"}

    def redraw(current_i, pct):
        stdscr.erase()
        box_w = min(68, w - 2)
        box_h = 16 + 8
        by = max(0, (h - box_h) // 2)
        bx = max(0, (w - box_w) // 2)

        _draw_box(stdscr, by, bx, box_h, box_w,
                  "ECU FINGERPRINT — SYSTEM MAP", bright)
        _draw_progress_bar(stdscr, by + 2, bx + 3, box_w - 8, pct, bright)
        _addstr_safe(stdscr, by + 4, bx + 3,
                     "{:<6} {:<6} {:<9} {:<8} {}".format(
                         "ADDR", "NAME", "STATUS", "TIME", "RESPONSE"),
                     bright)

        for j, addr in enumerate(FINGERPRINT_ADDRS):
            row = by + 5 + j
            name = ECU_NAMES.get(addr, "???")
            res  = results[j]
            if res is None:
                if j == current_i:
                    line = "{:<6} {:<6} ░ PROBING".format(addr, name)
                    attr = warn
                else:
                    line = "{:<6} {:<6} · · ·".format(addr, name)
                    attr = green
            elif res["status"] == "ACTIVE":
                t = "{}ms".format(res["ms"])
                line = "{:<6} {:<6} {:<9} {:<8} {}".format(
                    addr, name, "● ACTIVE", t, res["raw"])
                attr = bright
            else:
                line = "{:<6} {:<6} ○ SILENT   —".format(addr, name)
                attr = green
            try:
                stdscr.addstr(row, bx + 3, line[:box_w - 6], attr)
            except curses.error:
                pass

        stdscr.refresh()

    try:
        gen = scanner.ecu_fingerprint()
        for pct, label, line in gen:
            if line:
                reporter.checkpoint(line)
                parts = line.split()
                # "FINGERPRINT 7E0 ECM ACTIVE 142ms 50 01 ..."
                # "FINGERPRINT 7E0 ECM SILENT —"
                if len(parts) >= 4 and parts[0] == "FINGERPRINT":
                    addr   = parts[1]
                    status = parts[3]
                    idx = FINGERPRINT_ADDRS.index(addr) if addr in FINGERPRINT_ADDRS else -1
                    if idx >= 0:
                        if status == "ACTIVE":
                            ms  = int(parts[4].rstrip("ms")) if len(parts) > 4 else 0
                            raw = " ".join(parts[5:]) if len(parts) > 5 else ""
                            results[idx] = {"status": "ACTIVE", "ms": ms, "raw": raw}
                        else:
                            results[idx] = {"status": "SILENT", "ms": 0, "raw": ""}
            current_i = min(pct * 16 // 100, 15)
            redraw(current_i, pct)
    except Exception:
        if reporter._chk_file:
            reporter._chk_file.close()
            reporter._chk_file = None
        _show_message(stdscr, "CONNECTION ERROR — partial data saved", 2000)
        return

    redraw(16, 100)
    curses.napms(800)

```

- [ ] **Step 6: Run scanner tests to confirm no regressions**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add ui/tui.py
git commit -m "feat: add ECU FINGERPRINT menu item, dispatch, and live map screen"
```
