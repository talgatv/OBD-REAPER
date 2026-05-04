# ECU FINGERPRINT — Design Spec
**Date:** 2026-05-04
**Project:** OBD-REAPER hacker intelligence layer — Phase 2 of 3
**Feature:** Probe all 16 UDS addresses (7E0–7EF), display live ECU map with ACTIVE/SILENT status and response times

---

## 1. Overview

ECU FINGERPRINT sends a UDS DiagnosticSessionControl ping (`10 01`) to each of the 16 CAN addresses 7E0–7EF and maps which ECUs respond. Results appear two ways:

1. **Standalone mode** — new menu item `[E] ECU FINGERPRINT` that shows a custom live-updating hacker map screen while probing, then saves to `.md` report.
2. **Full scan integration** — the same 16-step probe block runs at the start of `full_scan()`, yielding log lines through the standard scan screen.

Addresses 7E0–7E7 are the UDS request side (ECM, TCM, ABS, etc.). Addresses 7E8–7EF are response-side addresses — they will show SILENT, correctly marking the CAN address space boundary.

---

## 2. File Map

| File | Change |
|------|--------|
| `core/scanner.py` | Add `ECU_NAMES` dict + `FINGERPRINT_ADDRS` list + `ecu_fingerprint(skip=0)` generator; add 16-step probe block at start of `full_scan()` |
| `ui/tui.py` | Add `[E] ECU FINGERPRINT` to menu; add `_ecu_fingerprint_screen()`; update `_dispatch()` |
| `tests/test_scanner.py` | 5 new tests for `ecu_fingerprint()` and `full_scan()` step count |

No new files. `reporter.py`, `dtc_db.py`, `elm327.py` untouched.

---

## 3. core/scanner.py changes

### 3.1 ECU_NAMES and FINGERPRINT_ADDRS

```python
FINGERPRINT_ADDRS = [
    "7E0", "7E1", "7E2", "7E3", "7E4", "7E5", "7E6", "7E7",
    "7E8", "7E9", "7EA", "7EB", "7EC", "7ED", "7EE", "7EF",
]

ECU_NAMES = {
    "7E0": "ECM",   # Engine Control Module
    "7E1": "TCM",   # Transmission Control Module
    "7E2": "ABS",   # Anti-lock Brake System
    "7E3": "HCU",   # Hydraulic Control Unit (hybrid)
    "7E4": "MCU",   # Motor Control Unit (hybrid)
    "7E5": "BCM",   # Body Control Module
    "7E6": "MISC",  # Miscellaneous
    "7E7": "SCM",   # Steering Column Module
    "7E8": "ECM-R", # ECM response address (silent as request target)
    "7E9": "TCM-R",
    "7EA": "ABS-R",
    "7EB": "HCU-R",
    "7EC": "MCU-R",
    "7ED": "BCM-R",
    "7EE": "MSC-R",
    "7EF": "SCM-R",
}
```

### 3.2 ecu_fingerprint() generator

```python
import time as _time

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

**Key details:**
- `wait=0.3` for header set (fast AT command, no vehicle response needed)
- `wait=0.6` for the `10 01` probe (short enough to fail fast on silent addresses)
- Response check: `raw.upper().startswith("50")` — positive response to service `10` is `50`
- `raw[:24]` captures the first 24 chars of the response (enough for the session PDU bytes)
- `skip=0` follows the exact same pattern as all other generators — safe for SESSION VAULT resume
- Reset to functional address `7DF` after all probes (same as `uds_scan` and `full_scan`)

### 3.3 full_scan() integration

Add the 16-address fingerprint probe as the **first block** of `full_scan()`, before the DTC steps. The `total` step count increases by 16:

```python
def full_scan(self, skip=0):
    dtc_steps = [...]       # 4 steps
    total = 16 + len(dtc_steps) + len(UDS_ECUS) + len(FULL_PIDS) + \
            len(FREEZE_PIDS) + len(MODE06_PIDS) + 3
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

    # DTC steps (4 steps)
    for cmd, label, wait in dtc_steps:
        ...  # unchanged
```

Note: In `full_scan`, response time is omitted (no `time.time()` measurement) to keep the integration simple. The standalone generator includes timing.

---

## 4. ui/tui.py changes

### 4.1 Menu

Add entry after `SESSION VAULT` (index 11):

```python
MENU_ITEMS = [
    ...
    ("R", "SESSION VAULT",     "recover interrupted scans"),
    ("E", "ECU FINGERPRINT",   "probe all ECU addresses"),
]

MENU_ACTIONS = [
    ..., "session_vault", "ecu_fingerprint",
]
```

### 4.2 _dispatch() branch

```python
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
```

### 4.3 _ecu_fingerprint_screen()

Custom screen that shows the live-updating ECU map as each address is probed:

```python
def _ecu_fingerprint_screen(stdscr, scanner, reporter):
    h, w = stdscr.getmaxyx()
    bright = curses.color_pair(C_GREEN) | curses.A_BOLD
    green  = curses.color_pair(C_GREEN)
    warn   = curses.color_pair(C_WARN)

    # 16 result slots: None = not yet probed, "ACTIVE"/"SILENT" = done
    results = [None] * 16

    def redraw(current_i, pct):
        stdscr.erase()
        box_w = min(68, w - 2)
        box_h = 16 + 8
        by = max(0, (h - box_h) // 2)
        bx = max(0, (w - box_w) // 2)

        _draw_box(stdscr, by, bx, box_h, box_w,
                  "ECU FINGERPRINT — SYSTEM MAP", bright)

        # Progress bar row
        _draw_progress_bar(stdscr, by + 2, bx + 3, box_w - 8, pct, bright)

        # Header row
        _addstr_safe(stdscr, by + 4, bx + 3,
                     "{:<6} {:<6} {:<9} {:<8} {}".format(
                         "ADDR", "NAME", "STATUS", "TIME", "RESPONSE"),
                     bright)

        for j, addr in enumerate(FINGERPRINT_ADDRS):
            row = by + 5 + j
            name = ECU_NAMES.get(addr, "???")
            res = results[j]
            if res is None:
                if j == current_i:
                    status_str = "░ PROBING"
                    attr = warn
                else:
                    status_str = "· · ·"
                    attr = green
                line = "{:<6} {:<6} {}".format(addr, name, status_str)
            elif res["status"] == "ACTIVE":
                status_str = "● ACTIVE"
                t = "{}ms".format(res["ms"])
                line = "{:<6} {:<6} {:<9} {:<8} {}".format(
                    addr, name, status_str, t, res["raw"])
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
                # Parse result back into results list
                parts = line.split()
                # "FINGERPRINT 7E0 ECM ACTIVE 142ms 50 01 ..."
                # "FINGERPRINT 7E0 ECM SILENT —"
                if len(parts) >= 4 and parts[0] == "FINGERPRINT":
                    addr = parts[1]
                    status = parts[3]
                    idx = FINGERPRINT_ADDRS.index(addr) if addr in FINGERPRINT_ADDRS else -1
                    if idx >= 0:
                        if status == "ACTIVE":
                            ms = int(parts[4].rstrip("ms")) if len(parts) > 4 else 0
                            raw = " ".join(parts[5:]) if len(parts) > 5 else ""
                            results[idx] = {"status": "ACTIVE", "ms": ms, "raw": raw}
                        else:
                            results[idx] = {"status": "SILENT", "ms": 0, "raw": ""}
            # Determine current probe index from pct
            current_i = min(pct * 16 // 100, 15)
            redraw(current_i, pct)
    except Exception:
        if reporter._chk_file:
            reporter._chk_file.close()
            reporter._chk_file = None
        _show_message(stdscr, "CONNECTION ERROR — partial data saved", 2000)
        return

    # Final draw at 100%
    redraw(16, 100)
    curses.napms(800)
```

**Key detail:** `FINGERPRINT_ADDRS` and `ECU_NAMES` are imported from `core.scanner` so the TUI does not duplicate them:

```python
from core.scanner import Scanner, FINGERPRINT_ADDRS, ECU_NAMES
```

---

## 5. Tests — tests/test_scanner.py additions

```python
class TestEcuFingerprint(unittest.TestCase):
    def _make_scanner(self, responses):
        """responses: list of strings returned by elm.send() in order."""
        elm = MagicMock()
        elm.send.side_effect = responses
        return Scanner(elm)

    def test_yields_16_probe_steps_plus_complete(self):
        # 16 addresses × 2 sends each (ATSH + 10 01) + 1 reset = 33 calls
        # responses: alternating ATSH ack and 10 01 response, then reset
        responses = []
        for _ in range(16):
            responses.append("OK")           # ATSH
            responses.append("NO DATA")      # 10 01
        responses.append("OK")               # ATSH 7DF reset
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        # 16 data steps + 1 COMPLETE
        data_steps = [st for st in steps if st[1] != "ECU FINGERPRINT COMPLETE"]
        self.assertEqual(len(data_steps), 16)
        complete = [st for st in steps if st[1] == "ECU FINGERPRINT COMPLETE"]
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0][0], 100)

    def test_active_response_produces_active_line(self):
        responses = ["OK", "50 01 00 19 01 F4"] + ["OK", "NO DATA"] * 15 + ["OK"]
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        first_line = steps[0][2]
        self.assertIn("ACTIVE", first_line)
        self.assertIn("7E0", first_line)

    def test_no_data_response_produces_silent_line(self):
        responses = ["OK", "NO DATA"] * 16 + ["OK"]
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint())
        first_line = steps[0][2]
        self.assertIn("SILENT", first_line)

    def test_skip_skips_elm_calls(self):
        responses = ["OK", "50 01 00 19 01 F4"] * 8 + ["OK"]  # only 8 real probes + reset
        s = self._make_scanner(responses)
        steps = list(s.ecu_fingerprint(skip=8))
        skipped = [st for st in steps if st[2] == ""]
        self.assertEqual(len(skipped), 8)
        # ELM called for: 8 real probes × 2 (ATSH + 10 01) + 1 reset = 17 calls
        self.assertEqual(s.elm.send.call_count, 17)

    def test_full_scan_step_count_includes_fingerprint(self):
        # full_scan total = 16 (fingerprint) + 4 (dtc) + 7 (uds) + 34 (pids)
        # + 8 (freeze) + 8 (mode06) + 3 (vehicle info) = 80 data steps + 1 COMPLETE
        elm = MagicMock()
        elm.send.return_value = "NO DATA"
        s = Scanner(elm)
        steps = list(s.full_scan())
        # 80 data steps + 1 FULL SCAN COMPLETE = 81 total yields
        self.assertEqual(len(steps), 81)
```

---

## 6. Out of Scope

- Response time measurement in `full_scan` fingerprint block (standalone only)
- Identifier readback (`22 F1 8A`, `22 F1 80`) — Phase 2 shallow only
- Probing addresses outside 7E0–7EF
- Saving the ECU map as a dedicated section in the `.md` (lines write naturally via reporter)
- THREAT LEVEL (Phase 3)
