# SESSION VAULT — Design Spec
**Date:** 2026-05-01
**Project:** OBD-REAPER session recovery system
**Feature:** Interrupt-resilient scan resume + partial data salvage

---

## 1. Overview

SESSION VAULT is a hacker-aesthetic recovery terminal built into OBD-REAPER. Every scan already writes data to a `.chk` checkpoint file on every yield. If the scan is interrupted (power loss, serial disconnect, SIGINT), all data up to that point is preserved on disk. SESSION VAULT lets the user:

1. **Salvage** — convert partial `.chk` data into a finalized `.md` + `.raw` report
2. **Resume** — reconnect to the vehicle and continue the scan from the exact command where it stopped, appending new data to the existing checkpoint

SESSION VAULT is accessible two ways:
- **Automatic**: on startup, if any `.chk` files exist, SESSION VAULT opens immediately instead of the plain notice
- **Manual**: main menu item `[R] SESSION VAULT` — always accessible

---

## 2. File Changes

| File | Change |
|------|--------|
| `core/reporter.py` | Add `Reporter.from_checkpoint(chk_path)` classmethod |
| `core/scanner.py` | Add `skip=0` parameter to all 9 scan generators |
| `ui/tui.py` | Replace `_show_incomplete_notice()` with `_session_vault_screen()`; add `[R]` to main menu |
| `tests/test_reporter.py` | Tests for `from_checkpoint()` |
| `tests/test_scanner.py` | Tests for `skip` parameter on each generator |

---

## 3. SESSION VAULT UI

### 3.1 Trigger

On startup in `run()`:
```python
incomplete = Reporter.find_incomplete()
if incomplete:
    _session_vault_screen(stdscr, scanner, incomplete)
```

Also added to main menu as item `[R] SESSION VAULT — recover interrupted scans`.

### 3.2 Screen Layout

```
╔══════════════════════════════════════════════════════════════════╗
║         [ REAPER SESSION VAULT — FIELD RECOVERY MODE ]          ║
╠══════════════════════════════════════════════════════════════════╣
║  ⚠  INTERRUPTED MISSIONS DETECTED — ALL DATA PRESERVED          ║
║                                                                  ║
║  [1]  2026-05-01_143022  QUICK_SCAN    [████████░░]  47 ln  67% ║
║  [2]  2026-05-01_161145  FULL_SCAN     [███░░░░░░░]  31 ln  28% ║
║  [3]  2026-05-01_182301  UDS_HYUNDAI   [█░░░░░░░░░]  12 ln  11% ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  [S]  SALVAGE REPORT  — dump partial data to .md now            ║
║  [R]  RESUME MISSION  — reconnect to vehicle + continue         ║
║  [D]  DISCARD         — delete checkpoint, abort mission        ║
║  [Q]  BACK TO MENU                                              ║
╚══════════════════════════════════════════════════════════════════╝
```

Navigation: `[↑↓]` select session, then `[S]` / `[R]` / `[D]` act on selected session.

### 3.3 Progress bar per session

Each `.chk` entry shows a mini progress bar. Width = 10 chars. Fill = `lines_saved / total_for_mode`. `total_for_mode` is a constant dict in `reporter.py`:

```python
MODE_TOTALS = {
    "quick_scan": 7,
    "full_scan": 60,          # approximate
    "cylinder_test": 12,
    "catalyst_test": 8,
    "evap_test": 5,
    "adapter_info": 5,
    "uds_scan": 16,           # plugin-dependent, use 16 as default
}
```

If mode not in dict, show bar at unknown state (all `░`).

### 3.4 Salvage flow

1. User presses `[S]` on selected session
2. `Reporter.from_checkpoint(path)` called — does NOT open for append, just reads and calls `finish()`
3. Show `SALVAGING DATA...` flash message (800ms)
4. Show `REPORT SAVED: filename.md` (1500ms)
5. Remove from list, refresh screen

### 3.5 Resume flow

1. User presses `[R]` on selected session
2. Show `[RECONNECTING TO TARGET VEHICLE...]` (attempts ELM connect)
3. If connect fails: show `CONNECTION FAILED — salvage or discard?` with `[S]` / `[D]` fallback
4. If connect succeeds: parse mode from filename, call `scanner.<mode>(skip=N)`
5. Run standard `_scan_screen()` — appends to existing `.chk`
6. On complete: `reporter.finish()` → full report, show `MISSION COMPLETE`

### 3.6 Discard flow

1. User presses `[D]` on selected session
2. Confirm: `DISCARD checkpoint? All partial data will be lost.  [Y] Yes  [N] No`
3. On confirm: `os.remove(chk_path)`, remove from list

---

## 4. Reporter Changes

### 4.1 `Reporter.from_checkpoint(chk_path)`

```python
@classmethod
def from_checkpoint(cls, chk_path):
    """Load an existing .chk for resume (append mode) or salvage (read-only)."""
    fname = os.path.basename(chk_path)        # 2026-05-01_143022_quick_scan.chk
    stem = fname[:-4]                          # strip .chk
    # ts = first two underscore-separated tokens: date + time
    # mode = everything after second underscore
    first_us = stem.index("_")
    second_us = stem.index("_", first_us + 1)
    ts = stem[:second_us]                      # 2026-05-01_143022
    mode = stem[second_us + 1:]               # quick_scan
    with open(chk_path) as f:
        skip = sum(1 for line in f if line.strip())
    r = cls(mode)
    r.ts = ts
    r.chk_path = chk_path
    return r, skip
```

**Salvage** calls `r.finish()` directly — `finish()` already reads `.chk` and converts it.

**Resume** calls `r.start_append()` — new method that opens `.chk` in append mode and re-registers signal handlers:

```python
def start_append(self):
    """Open existing checkpoint for appending (resume mode)."""
    self._chk_file = open(self.chk_path, "a", buffering=1)
    signal.signal(signal.SIGINT, self._signal_handler)
    signal.signal(signal.SIGTERM, self._signal_handler)
```

### 4.2 `MODE_TOTALS` dict

Added as module-level constant in `reporter.py` for progress bar estimation in SESSION VAULT.

---

## 5. Scanner Changes

All 9 generators get `skip=0` parameter. Skip logic:

```python
def quick_scan(self, skip=0):
    steps = [("03", "CURRENT DTCs"), ("07", "PENDING DTCs"), ...]
    total = len(steps)
    for i, (cmd, label) in enumerate(steps):
        pct = i * 100 // total
        if i < skip:
            yield (pct, label, "")   # yield progress update, no OBD command sent
            continue
        raw = self.elm.send(cmd)
        yield (pct, label, "> {} -> {}".format(cmd, raw))
```

Key: skipped steps still yield `(pct, label, "")` so the progress bar shows correct position when resume begins. Empty `line` means `reporter.checkpoint()` is a no-op (already guarded by `if line:`).

Generators affected: `quick_scan`, `full_scan`, `cylinder_test`, `catalyst_test`, `evap_test`, `adapter_info`, `uds_scan`, `clear_codes`.

`live_data` is excluded — it's an infinite stream with no natural resume point.

---

## 6. Resume mode → UDS/plugin scans

For `uds_scan`, mode name in `.chk` filename is `uds_<vehicle_id>` (e.g. `uds_hyundai_sonata_2016`). On resume, `_session_vault_screen` strips the `uds_` prefix and looks up the plugin by `VEHICLE_ID`. If plugin not found, falls back to salvage-only.

---

## 7. Tests

**`test_reporter.py` additions:**
- `from_checkpoint()` returns correct `ts`, `mode`, `skip` count
- `from_checkpoint()` on file with 5 lines → skip=5
- `start_append()` opens file in append mode, signal handlers registered
- Salvage via `from_checkpoint()` + `finish()` produces `.md` with correct content

**`test_scanner.py` additions:**
- Each generator with `skip=N` yields exactly `(total - N)` non-empty lines
- Skipped steps yield empty `line` strings (no ELM commands sent)
- `skip=0` produces same output as before (no regression)

---

## 8. Out of Scope

- Merging two partial scans of the same mode
- Resume for `live_data` (infinite stream, no meaningful resume point)
- Network/remote checkpoint transfer
- Encrypting checkpoint files
