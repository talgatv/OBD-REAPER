# OBD-REAPER

```
  ██████╗ ██████╗ ██████╗    ██████╗ ███████╗ █████╗ ██████╗ ███████╗██████╗
 ██╔═══██╗██╔══██╗██╔══██╗   ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗
 ██║   ██║██████╔╝██║  ██║   ██████╔╝█████╗  ███████║██████╔╝█████╗  ██████╔╝
 ╚██████╔╝██╔══██╗██████╔╝   ██║  ██║██╔══╝  ██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗
  ╚═════╝ ╚═╝  ╚═╝╚═════╝    ╚═╝  ╚═╝███████╗██║  ██║██║     ███████╗██║  ██║
```

**Hacker-grade terminal OBD2 diagnostic scanner for Linux.**  
Plug in a $10 ELM327 adapter, run one command, own your car's data.

> Python 3 · stdlib-only · 70 tests · zero configuration · no cloud

---

## Table of Contents

1. [What is OBD-REAPER?](#what-is-obd-reaper)
2. [Feature Overview](#feature-overview)
3. [Hardware Requirements](#hardware-requirements)
4. [Connection Setup](#connection-setup)
5. [Quick Start](#quick-start)
6. [Menu Reference](#menu-reference)
7. [ECU Fingerprint](#ecu-fingerprint)
8. [DTC Intelligence](#dtc-intelligence)
9. [Session Vault — Crash Recovery](#session-vault--crash-recovery)
10. [Reports and Data Format](#reports-and-data-format)
11. [Understanding Your Output](#understanding-your-output)
12. [Troubleshooting](#troubleshooting)
13. [Adding Your Car — Plugin Guide](#adding-your-car--plugin-guide)
14. [Project Architecture](#project-architecture)
15. [Running Tests](#running-tests)
16. [License](#license)

---

## What is OBD-REAPER?

OBD-REAPER is a terminal application that reads everything your car's ECUs are willing to tell you — error codes, live sensor data, freeze frames, OBD2 monitor status, UDS fault records, and manufacturer-specific data — and displays it in a hacker-green curses interface.

It communicates through a USB ELM327 adapter using the OBD2 and UDS protocols. **No installation, no account, no cloud.** Data stays local and is saved to disk after every single response — so nothing is ever lost, even on a hard crash.

**Tested against:** Hyundai Sonata Hybrid 2016 (primary development target).  
**Works with:** Any OBD2-compliant car (1996+ USA, 2004+ EU) + any ELM327 USB adapter.

---

## Feature Overview

| Feature | Description |
|---------|-------------|
| **Quick Scan** | Active / pending / permanent DTCs + MIL status in ~15 seconds |
| **Full Scan** | 80-step deep scan: ECU map + DTCs + 34 PIDs + freeze frame + Mode 06 monitors + vehicle info |
| **ECU Fingerprint** | Probe all 16 UDS CAN addresses (7E0–7EF), live map shows which ECUs respond and how fast |
| **Live Data** | 7 sensors streaming at 0.5 Hz: RPM, speed, coolant, IAT, MAF, throttle, O2 |
| **DTC Intelligence** | Built-in database: ~200 codes with descriptions and severity (CRITICAL / WARNING / INFO) |
| **Clear Codes** | Erase all DTCs and reset MIL with confirmation prompt |
| **Cylinder Test** | Per-cylinder misfire counters (Mode 06) + manufacturer cylinder data (Mode 22) |
| **Catalyst Test** | Catalyst temperatures (B1S1, B1S2) + catalyst monitor results |
| **EVAP Test** | EVAP commanded purge, system pressure, monitor result |
| **UDS / Vehicle** | Manufacturer-specific commands via plugins: VIN decode, calibration IDs, proprietary data |
| **Session Vault** | Detect, resume, or salvage any scan interrupted by power loss or Ctrl+C |
| **Saved Reports** | Scrollable browser for all past scans; view any report in-terminal |
| **Adapter Info** | ELM327 firmware version, battery voltage, protocol, ignition state |

---

## Hardware Requirements

### Required

| Item | Notes |
|------|-------|
| **ELM327 USB adapter** | Any USB OBD2 scanner labelled "ELM327" — $5–15 on Amazon or AliExpress |
| **OBD2 cable** | 16-pin trapezoidal connector; usually comes with the adapter |
| **A car with an OBD2 port** | All cars sold in the USA after 1996, EU after 2004 |
| **Linux PC** | Tested on Ubuntu 22.04 / 24.04, Python 3.10+ |

### Software Dependencies

| Package | Purpose | How to get |
|---------|---------|------------|
| **Python 3.6+** | Runtime | `sudo apt install python3` |
| **pyserial** | Serial port communication | `sudo apt install python3-serial` |
| **pytest** | Running tests (optional) | `sudo apt install python3-pytest` |

Everything else (`curses`, `signal`, `datetime`, `os`, `sys`) is Python stdlib.

---

## Connection Setup

```
                     YOUR CAR
                 ┌───────────────┐
  OBD2 PORT  ─► │ 16-pin socket │  under the dashboard, driver's side
                 │  near pedals  │  trapezoidal plastic connector
                 └───────┬───────┘
                         │  plug in ELM327 adapter
                 ┌───────▼───────┐
                 │  ELM327 USB   │
                 │   ADAPTER     │
                 └───────┬───────┘
                         │  USB-A cable to laptop
                 ┌───────▼───────┐
                 │  YOUR LAPTOP  │  runs OBD-REAPER
                 └───────────────┘
```

**Step by step:**

1. Park the car. Engine can be off — **ignition must be ON** (key to position II, dashboard lights on).
2. Plug the ELM327 adapter into the OBD2 port under your dashboard.
3. Connect the USB end to your laptop.
4. Wait 3 seconds for the device to enumerate.
5. Run `sudo python3 reaper.py`.

> **Why `sudo`?**  
> The USB serial device `/dev/ttyACM0` requires root access by default on most Linux systems.  
> To avoid `sudo` permanently: `sudo usermod -aG dialout $USER` — then log out and back in.

---

## Quick Start

```bash
git clone <repo>
cd OBD-REAPER
sudo python3 reaper.py
```

OBD-REAPER auto-detects the ELM327 adapter on `/dev/ttyACM*`. No configuration needed.

**Optional arguments:**

```
sudo python3 reaper.py --port /dev/ttyUSB0    # force a specific port
sudo python3 reaper.py --no-usb-reset          # skip USB reset (faster startup)
```

On first launch, OBD-REAPER checks for any incomplete scans from previous sessions and presents the Session Vault if any are found.

---

## Menu Reference

Navigate with arrow keys or type the key shown in brackets. Press **Q** to quit.

| Key | Mode | Duration | What it does |
|-----|------|----------|-------------|
| `1` | **QUICK SCAN** | ~15 s | Active DTCs, pending DTCs, permanent DTCs, MIL status. Good starting point. |
| `2` | **FULL SCAN** | 3–5 min | 80 data steps: ECU fingerprint → DTCs → 7 UDS ECUs → 34 OBD2 PIDs → freeze frame → Mode 06 monitors → vehicle info. |
| `3` | **LIVE DATA** | continuous | Streams RPM, speed, coolant temp, IAT, MAF, throttle %, O2 voltage every 0.5 seconds. Press **Q** to stop. |
| `4` | **CLEAR CODES** | ~5 s | Sends Mode 04 to erase all stored DTCs and reset the MIL. **Irreversible.** Requires confirmation. |
| `5` | **CYLINDER TEST** | ~30 s | Mode 06 misfire counters for cylinders 1–4 + manufacturer Mode 22 cylinder data (7E0). |
| `6` | **CATALYST TEST** | ~20 s | Cat temps (B1S1, B1S2) via PIDs 013C/013E + catalyst monitor results (0621, 0622) + O2 sensor monitors. |
| `7` | **EVAP TEST** | ~15 s | EVAP commanded purge (012E), system pressure (0132), EVAP monitor result (0631). |
| `8` | **UDS / VEHICLE** | ~30 s | Plugin-based manufacturer data. Select your vehicle. Currently: Hyundai Sonata Hybrid 2016 (VIN, HW/SW PN, KSDS counters, misfire data, cylinder data). |
| `9` | **SAVED REPORTS** | — | Browse all `.md` scan reports. Arrow keys to navigate, Enter to view, Page Up/Down to scroll. |
| `0` | **ADAPTER INFO** | ~5 s | ELM327 firmware (ATI), battery voltage (ATRV), protocol name/number (ATDP/ATDPN), ignition state (ATIGN). |
| `R` | **SESSION VAULT** | — | Lists all interrupted scans. **[R]** resume, **[S]** salvage to `.md`, **[D]** discard. |
| `E` | **ECU FINGERPRINT** | ~20 s | Probes all 16 UDS CAN addresses (7E0–7EF). Live map shows ACTIVE/SILENT per ECU and response time in ms. |
| `Q` | **EXIT** | — | Close the program. |

---

## ECU Fingerprint

ECU Fingerprint is a low-level intelligence tool. It sends a UDS `DiagnosticSessionControl` request (`10 01`) to each of the 16 standard UDS CAN addresses (7E0–7EF) and records which ECUs respond.

### The Live Map

While probing, a custom 16-row screen updates in real time:

```
╔══════════════════ ECU FINGERPRINT — SYSTEM MAP ══════════════════╗
║ [████████████████░░░░] 75%                                       ║
║                                                                   ║
║ ADDR   NAME   STATUS    TIME     RESPONSE                        ║
║ 7E0    ECM    ● ACTIVE  142ms    50 01 00 19 01 F4               ║
║ 7E1    TCM    ● ACTIVE  211ms    50 01 00 19 01 F4               ║
║ 7E2    ABS    ○ SILENT  —                                        ║
║ 7E3    HCU    ● ACTIVE  189ms    50 01 00 19 01 F4               ║
║ 7E4    MCU    ░ PROBING                                          ║
║ 7E5    BCM    · · ·                                              ║
║ ...                                                               ║
╚══════════════════════════════════════════════════════════════════╝
```

### Address Map

| Address | Name | Role |
|---------|------|------|
| 7E0 | ECM | Engine Control Module |
| 7E1 | TCM | Transmission Control Module |
| 7E2 | ABS | Anti-lock Brake System |
| 7E3 | HCU | Hydraulic Control Unit (hybrid) |
| 7E4 | MCU | Motor Control Unit (hybrid) |
| 7E5 | BCM | Body Control Module |
| 7E6 | MISC | Miscellaneous |
| 7E7 | SCM | Steering Column Module |
| 7E8–7EF | *-R | Response-side addresses — will always be SILENT |

**ACTIVE** = ECU acknowledged the `10 01` request (response starts with `50`).  
**SILENT** = No response within 600 ms — ECU absent, asleep, or unsupported at that address.

### Integration with Full Scan

ECU Fingerprint runs automatically as the **first 16 steps** of Full Scan, before any DTC queries. The results appear in the live log and are saved to the report. Full Scan's total is 80 data steps:

```
Full Scan breakdown (80 steps):
  16  ECU Fingerprint (7E0–7EF)
   4  DTC queries (permanent, active, pending, MIL)
   7  UDS ECUs via Mode 19 (1902 FF)
  34  OBD2 PIDs (Mode 01)
   8  Freeze frame PIDs (Mode 02)
   8  Mode 06 OBD monitor results
   3  Vehicle info (Mode 09: VIN, cal ID, cal CVN)
```

---

## DTC Intelligence

OBD-REAPER includes a built-in DTC database (`core/dtc_db.py`) with approximately 200 codes. Every DTC seen during a scan — in any mode — is looked up automatically.

### Severity Levels

| Level | Color | Meaning |
|-------|-------|---------|
| `CRITICAL` | Red + bold | Stop driving. Injector failure, engine over-temp, HV battery fault, fuel pump |
| `WARNING` | Yellow | Investigate soon. Sensor faults, catalyst issues, O2 sensor problems |
| `INFO` | Green | Advisory. Heater circuits, maintenance reminders |
| `UNKNOWN` | Green | Code not in database — raw code shown without description |

### Color Coding in Live Log

During any scan, the right-side log panel colors DTC responses automatically:

```
> 43 01 13 00 00 00 00
  ► P0113   IAT Sensor Circuit High Input            [WARNING]

> 43 0A 80
  ► P0A80   HV Battery Cell Voltage Variation        [CRITICAL]
```

CRITICAL lines flash red. WARNING lines show yellow. All other lines remain green.

### DTC Database Coverage

| Category | Codes |
|----------|-------|
| Airflow / MAF | P0100–P0123 |
| Oxygen sensors | P0130–P0161 |
| Fuel trim | P0171–P0191 |
| Injectors | P0200–P0219 |
| Fuel pump | P0230–P0232 |
| Misfire | P0300–P0309 |
| Knock sensor | P0325–P0335 |
| EGR / EVAP | P0400–P0455 |
| Catalytic converter | P0420–P0432 |
| Transmission | P0700–P0882 |
| ABS / Traction | C0035–C0300 |
| Hybrid / HV battery | P0A00–P0A9F |
| Hyundai-specific | P1326, P1326, others |

### Enriched Reports

All `.md` report files include DTC descriptions inline:

```markdown
43 01 13 26
  ► P0113   IAT Sensor Circuit High Input            [WARNING]
  ► P1326   Knock Sensor Detection System Fault      [CRITICAL]
```

The `.raw` file always contains unmodified OBD2 responses for archival.

---

## Session Vault — Crash Recovery

**OBD-REAPER never loses data.** Every OBD2 response is written to a checkpoint file immediately as it arrives, before the next command is sent. If a scan is interrupted — Ctrl+C, USB disconnect, laptop power loss — the data already collected is preserved.

### How it Works

```
During a scan:
  reports/.checkpoints/2026-05-04_143022_full_scan.chk   ← live file, grows with every response

After successful completion:
  reports/2026-05-04_143022_full_scan.md                 ← formatted report
  reports/2026-05-04_143022_full_scan.raw                ← raw responses
  (checkpoint deleted)
```

On startup, OBD-REAPER checks for `.chk` files. If any exist, the **Session Vault** screen appears automatically.

### Session Vault Options

| Key | Action |
|-----|--------|
| `R` | **Resume** — reconnect to vehicle and continue the scan from the last checkpoint |
| `S` | **Salvage** — convert partial data to a `.md` report right now (no vehicle needed) |
| `D` | **Discard** — permanently delete the checkpoint |

The vault also shows a progress bar for each interrupted session (how many steps were completed before interruption).

**Resume is available for:** quick_scan, full_scan, cylinder_test, catalyst_test, evap_test, adapter_info, clear_codes, ecu_fingerprint, and all UDS plugin scans.

---

## Reports and Data Format

All scan results are saved to the `reports/` directory automatically. No action required.

### File Naming

```
reports/
├── 2026-05-04_143022_quick_scan.md       ← formatted, enriched report
├── 2026-05-04_143022_quick_scan.raw      ← raw OBD2 responses (archival)
├── 2026-05-04_151800_full_scan.md
├── 2026-05-04_151800_full_scan.raw
└── .checkpoints/                          ← in-progress scans (auto-cleaned)
    └── 2026-05-04_160000_full_scan.chk
```

### Report Format

`.md` files are valid Markdown with a header and a fenced code block:

```markdown
# OBD-REAPER — FULL SCAN
**Scan Date:** 2026-05-04_151800

\`\`\`
FINGERPRINT 7E0 ECM ACTIVE 142ms 50 01 00 19 01 F4
FINGERPRINT 7E1 TCM ACTIVE 211ms 50 01 00 19 01 F4
0A -> 43 01 13 26
  ► P0113   IAT Sensor Circuit High Input            [WARNING]
  ► P1326   Knock Sensor Detection System Fault      [CRITICAL]
010C -> 41 0C 0F A0
...
\`\`\`
```

`.raw` files contain unmodified responses, one per line, for feeding into other tools.

---

## Understanding Your Output

### OBD2 Protocol Basics

OBD-REAPER communicates using:

| Protocol layer | What it does |
|---------------|-------------|
| **ELM327 AT commands** | Configure the adapter (baud rate, CAN header, protocol) |
| **OBD2 Mode 01–09** | Standardized diagnostics defined in SAE J1979 |
| **UDS (ISO 14229)** | Extended diagnostics: session control, DTC readout by ECU, data by ID |

### OBD2 Modes Used

| Mode | Hex | Name | Used by |
|------|-----|------|---------|
| 01 | 0x01 | Current data (PIDs) | Live Data, Full Scan |
| 02 | 0x02 | Freeze frame data | Full Scan |
| 03 | 0x03 | Stored DTCs | Quick Scan, Full Scan |
| 04 | 0x04 | Clear DTCs | Clear Codes |
| 06 | 0x06 | OBD monitor test results | Cylinder Test, Catalyst Test, EVAP Test, Full Scan |
| 07 | 0x07 | Pending DTCs | Quick Scan, Full Scan |
| 09 | 0x09 | Vehicle information (VIN) | Full Scan |
| 0A | 0x0A | Permanent DTCs | Quick Scan, Full Scan |

### UDS Services Used

| Service | Hex | Name | Used by |
|---------|-----|------|---------|
| DiagnosticSessionControl | 0x10 | Open default session | ECU Fingerprint |
| ReadDTCInformation | 0x19 | Read all ECU fault codes | Full Scan (per-ECU) |
| ReadDataByIdentifier | 0x22 | Read proprietary sensor data | Cylinder Test, UDS plugins |

### What is a DTC?

**DTC = Diagnostic Trouble Code.** A 5-character code stored when your car detects a fault.

| First character | System |
|----------------|--------|
| `P` | Powertrain (engine, transmission, fuel) |
| `B` | Body (airbags, AC, power windows) |
| `C` | Chassis (ABS, brakes, steering) |
| `U` | Network (communication between modules) |

| State | Meaning |
|-------|---------|
| **Active** | Problem is happening right now |
| **Pending** | Happened once; needs one more occurrence to become active |
| **Permanent** | Confirmed and cannot be erased by a scan tool |

### What is MIL?

**MIL = Malfunction Indicator Lamp** = the Check Engine light. It illuminates when there is at least one active DTC. Clearing codes with Mode 04 turns it off.

### What is `NO DATA`?

The ECU does not support that particular PID or service. Normal — no car implements every OBD2 PID. Not an error.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No OBD adapter found on /dev/ttyACM*` | Adapter not detected | Run `lsusb` — confirm adapter appears. Try unplugging and replugging. |
| `ELM327 did not respond after 5 attempts` | Adapter not initializing | Make sure ignition is ON (position II). Try `--no-usb-reset`. |
| Everything shows `NO DATA` | Ignition not on | Key must be at position II — dashboard lights on. Some cars need engine running. |
| `Permission denied: /dev/ttyACM0` | Missing dialout group | Run with `sudo`, or: `sudo usermod -aG dialout $USER` then log out and back in. |
| Screen too narrow, display garbled | Terminal too small | Resize terminal window to at least 80×24. Most screens work best at 120×40+. |
| Scan stops mid-way | USB drop / power loss | Data is saved. Check `reports/` for `.md` and `reports/.checkpoints/` for the checkpoint. Use Session Vault to resume. |
| ECU Fingerprint shows all SILENT | Wrong protocol / no CAN | Not all adapters support CAN bus at 11-bit 500kbps. Try `sudo python3 reaper.py` with adapter in port and ignition on. |
| UDS plugin shows all `NO DATA` | Engine must be running | Some UDS services require the engine to be running, not just ignition on. |

---

## Adding Your Car — Plugin Guide

OBD-REAPER supports manufacturer-specific UDS commands via a drop-in plugin system. Each plugin is a single `.py` file in the `plugins/` directory that is auto-discovered on startup.

### Plugin Structure

```python
# plugins/my_car_2020.py

class MyCar2020Plugin:
    NAME = "My Car Model 2020"           # shown in the UDS / VEHICLE menu
    VEHICLE_ID = "my_car_2020"           # used in report filenames (no spaces)
    COMMANDS = [
        ("22F190", "VIN"),               # (OBD command string, human-readable label)
        ("22F191", "Hardware Part Number"),
        ("22B001", "Engine Data"),
        ("22D100", "Cylinder 1 Data"),
    ]

    def interpret(self, pid, raw):
        """Return a human-readable string, or None to show raw hex bytes."""
        if pid == "22F190":
            # decode VIN from response bytes
            try:
                parts = raw.split()
                data = [int(b, 16) for b in parts if len(b) == 2]
                vin_chars = "".join(chr(b) for b in data[3:] if chr(b).isalnum())
                import re
                m = re.search(r'[A-Z0-9]{17}', vin_chars)
                if m:
                    return "VIN: {}".format(m.group())
            except Exception:
                pass
        return None   # fall back to raw hex display
```

### Plugin Rules

- Class name must end in `Plugin`.
- `NAME`, `VEHICLE_ID`, `COMMANDS` are required.
- `interpret(pid, raw)` is called for every response. Return `None` to show raw bytes.
- Commands are sent with the CAN header set to `7E0` (ECM).
- The plugin file must be directly inside `plugins/` — no subdirectories.

### Currently Included Plugins

| Plugin | Vehicle | Commands |
|--------|---------|----------|
| `hyundai_sonata.py` | Hyundai Sonata Hybrid 2016 | VIN, HW/SW part numbers, engine data, KSDS counters, misfire data, per-cylinder data |
| `toyota_prius.py` | Toyota Prius Gen3 | Stub — ready to fill in |

---

## Project Architecture

```
OBD-REAPER/
│
├── reaper.py               Entry point. Parses args, calls curses.wrapper(run)
│
├── core/
│   ├── elm327.py           ELM327 serial adapter: connect, send, USB reset, port auto-detect
│   ├── scanner.py          10 scan mode generators + FINGERPRINT_ADDRS + ECU_NAMES
│   ├── reporter.py         Checkpoint persistence, .md/.raw report writer, MODE_TOTALS
│   └── dtc_db.py           ~200 DTC definitions, severity constants, parse_dtcs(), enrich_line()
│
├── ui/
│   ├── banner.py           Startup ASCII art banner
│   └── tui.py              Full curses TUI: main menu, all scan screens, live data,
│                           report browser, session vault, ECU fingerprint screen
│
├── plugins/
│   ├── __init__.py         load_plugins() — scans plugins/ and imports *Plugin classes
│   ├── hyundai_sonata.py   Hyundai Sonata Hybrid 2016
│   └── toyota_prius.py     Toyota Prius Gen3 (stub)
│
├── tests/
│   ├── test_elm327.py      ELM327 serial layer (11 tests)
│   ├── test_scanner.py     All scan generators including ecu_fingerprint (26 tests)
│   ├── test_dtc_db.py      DTC lookup, parse_dtcs, enrich_line (12 tests)
│   ├── test_reporter.py    Checkpoint write/read/finish, DTC enrichment (13 tests)
│   └── test_plugins.py     Plugin discovery and interface (8 tests)
│
└── reports/                Created at runtime — not committed
    ├── *.md                Formatted scan reports
    ├── *.raw               Raw OBD2 response archives
    └── .checkpoints/       In-progress scan data (auto-cleaned on completion)
```

### Scanner Design

Every scan mode in `scanner.py` is a Python **generator** that yields `(pct, label, line)` tuples:

```python
(int, str, str)
  │     │     └─ OBD2 log line, or "" for skipped steps
  │     └─────── short label ("Coolant Temp", "7E0 ECM", …)
  └───────────── percent complete 0–100
```

This uniform contract means:
- The TUI's progress bar and log panel work identically for every scan mode.
- The `skip=N` parameter on each generator allows the Session Vault to resume mid-scan by replaying the first N yields without re-sending ELM327 commands.
- Adding a new scan mode requires only a new generator method — no TUI changes needed (for standard two-panel display).

### Checkpoint Design

```
emit response → reporter.checkpoint(line) → write line to .chk file (unbuffered)
                                          → only then send next ELM327 command
```

The checkpoint file is opened with `buffering=1` (line-buffered). Each `checkpoint()` call also calls `flush()`. There is no in-memory buffer to lose. The `.chk` file is deleted only after `finish()` successfully writes both `.md` and `.raw`.

---

## Running Tests

```bash
cd OBD-REAPER
python3 -m pytest tests/ -v
```

**70 tests. No hardware required.** All ELM327 interactions are mocked with `unittest.mock.MagicMock`.

```
tests/test_elm327.py     11 tests  — port discovery, connect, send, USB reset
tests/test_scanner.py    26 tests  — all generators, skip parameter, ecu_fingerprint
tests/test_dtc_db.py     12 tests  — DTC lookup, byte parsing, enrich_line severity
tests/test_reporter.py   13 tests  — checkpoint lifecycle, .md enrichment, salvage/resume
tests/test_plugins.py     8 tests  — plugin discovery, interface validation
```

Run a specific test file:
```bash
python3 -m pytest tests/test_scanner.py -v
```

Run a specific test:
```bash
python3 -m pytest tests/test_scanner.py::TestEcuFingerprint -v
```

---

## License

MIT — use it, fork it, add your car.
