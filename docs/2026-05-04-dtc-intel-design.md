# DTC INTEL — Design Spec
**Date:** 2026-05-04
**Project:** OBD-REAPER hacker intelligence layer — Phase 1 of 3
**Feature:** Built-in DTC code database with severity classification, inline scan log enrichment, enriched .md reports

---

## 1. Overview

DTC INTEL adds a built-in diagnostic trouble code database to OBD-REAPER. Every DTC code seen during any scan is automatically decoded inline — in the live scan log and in the final `.md` report. The result: raw bytes like `43 01 33 03 01` become human-readable intelligence:

```
03 -> 43 01 33 03 01
  ► P0133  Upstream O2 Sensor B1S1 Response Slow    [WARNING]
  ► P0301  Cylinder 1 Misfire Detected              [CRITICAL]
```

Severity levels: `CRITICAL` (red) / `WARNING` (yellow) / `INFO` (green) / `UNKNOWN` (green).

---

## 2. File Map

| File | Change |
|------|--------|
| `core/dtc_db.py` | Create — database dict + `lookup()` + `parse_dtcs()` + `enrich_line()` |
| `core/reporter.py` | Modify `finish()` — enrich .chk lines before writing .md |
| `ui/tui.py` | Modify `_scan_screen` — color-code DTC lines in live log panel |
| `tests/test_dtc_db.py` | Create — 11 tests covering all three public functions |

---

## 3. core/dtc_db.py

### 3.1 Severity constants

```python
CRITICAL = "CRITICAL"
WARNING  = "WARNING"
INFO     = "INFO"
UNKNOWN  = "UNKNOWN"
```

### 3.2 Database format

```python
DTC_DB = {
    "P0100": ("MAF Circuit Malfunction",               WARNING),
    "P0101": ("MAF Range/Performance Problem",         WARNING),
    "P0102": ("MAF Circuit Low Input",                 WARNING),
    "P0103": ("MAF Circuit High Input",                WARNING),
    "P0110": ("IAT Sensor Circuit Malfunction",        WARNING),
    "P0115": ("Engine Coolant Temp Circuit",           WARNING),
    "P0120": ("Throttle Position Sensor A Circuit",    WARNING),
    "P0121": ("TPS Range/Performance Problem",         WARNING),
    "P0130": ("O2 Sensor Circuit B1S1",                WARNING),
    "P0131": ("O2 Sensor Circuit Low Voltage B1S1",    WARNING),
    "P0132": ("O2 Sensor Circuit High Voltage B1S1",   WARNING),
    "P0133": ("O2 Sensor Slow Response B1S1",          WARNING),
    "P0134": ("O2 Sensor No Activity B1S1",            WARNING),
    "P0135": ("O2 Sensor Heater Circuit B1S1",         INFO),
    "P0136": ("O2 Sensor Circuit B1S2",                WARNING),
    "P0137": ("O2 Sensor Low Voltage B1S2",            WARNING),
    "P0138": ("O2 Sensor High Voltage B1S2",           WARNING),
    "P0139": ("O2 Sensor Slow Response B1S2",          WARNING),
    "P0140": ("O2 Sensor No Activity B1S2",            WARNING),
    "P0141": ("O2 Sensor Heater Circuit B1S2",         INFO),
    "P0150": ("O2 Sensor Circuit B2S1",                WARNING),
    "P0151": ("O2 Sensor Low Voltage B2S1",            WARNING),
    "P0152": ("O2 Sensor High Voltage B2S1",           WARNING),
    "P0153": ("O2 Sensor Slow Response B2S1",          WARNING),
    "P0155": ("O2 Sensor Heater Circuit B2S1",         INFO),
    "P0160": ("O2 Sensor Circuit B2S2",                WARNING),
    "P0161": ("O2 Sensor Heater Circuit B2S2",         INFO),
    "P0171": ("System Too Lean Bank 1",                WARNING),
    "P0172": ("System Too Rich Bank 1",                WARNING),
    "P0174": ("System Too Lean Bank 2",                WARNING),
    "P0175": ("System Too Rich Bank 2",                WARNING),
    "P0190": ("Fuel Rail Pressure Sensor Circuit",     WARNING),
    "P0191": ("Fuel Rail Pressure Range/Performance",  WARNING),
    "P0200": ("Injector Circuit Malfunction",          CRITICAL),
    "P0201": ("Injector Circuit Cylinder 1",           CRITICAL),
    "P0202": ("Injector Circuit Cylinder 2",           CRITICAL),
    "P0203": ("Injector Circuit Cylinder 3",           CRITICAL),
    "P0204": ("Injector Circuit Cylinder 4",           CRITICAL),
    "P0217": ("Engine Coolant Over Temperature",       CRITICAL),
    "P0219": ("Engine Over Speed",                     CRITICAL),
    "P0230": ("Fuel Pump Primary Circuit",             CRITICAL),
    "P0231": ("Fuel Pump Secondary Circuit Low",       CRITICAL),
    "P0232": ("Fuel Pump Secondary Circuit High",      CRITICAL),
    "P0261": ("Cylinder 1 Injector Circuit Low",       CRITICAL),
    "P0262": ("Cylinder 1 Injector Circuit High",      CRITICAL),
    "P0264": ("Cylinder 2 Injector Circuit Low",       CRITICAL),
    "P0265": ("Cylinder 2 Injector Circuit High",      CRITICAL),
    "P0267": ("Cylinder 3 Injector Circuit Low",       CRITICAL),
    "P0268": ("Cylinder 3 Injector Circuit High",      CRITICAL),
    "P0270": ("Cylinder 4 Injector Circuit Low",       CRITICAL),
    "P0271": ("Cylinder 4 Injector Circuit High",      CRITICAL),
    "P0300": ("Random/Multiple Cylinder Misfire",      CRITICAL),
    "P0301": ("Misfire Detected Cylinder 1",           CRITICAL),
    "P0302": ("Misfire Detected Cylinder 2",           CRITICAL),
    "P0303": ("Misfire Detected Cylinder 3",           CRITICAL),
    "P0304": ("Misfire Detected Cylinder 4",           CRITICAL),
    "P0305": ("Misfire Detected Cylinder 5",           CRITICAL),
    "P0306": ("Misfire Detected Cylinder 6",           CRITICAL),
    "P0320": ("Ignition/Distributor Engine Speed Input Circuit", WARNING),
    "P0325": ("Knock Sensor 1 Circuit Bank 1",         WARNING),
    "P0326": ("Knock Sensor 1 Range/Performance",      WARNING),
    "P0327": ("Knock Sensor 1 Circuit Low Bank 1",     WARNING),
    "P0328": ("Knock Sensor 1 Circuit High Bank 1",    WARNING),
    "P0330": ("Knock Sensor 2 Circuit Bank 2",         WARNING),
    "P0335": ("Crankshaft Position Sensor A Circuit",  CRITICAL),
    "P0336": ("CKP Sensor Range/Performance",          CRITICAL),
    "P0340": ("Camshaft Position Sensor A Circuit",    CRITICAL),
    "P0341": ("CMP Sensor Range/Performance",          CRITICAL),
    "P0351": ("Ignition Coil A Primary/Secondary Circuit", WARNING),
    "P0352": ("Ignition Coil B Primary/Secondary Circuit", WARNING),
    "P0353": ("Ignition Coil C Primary/Secondary Circuit", WARNING),
    "P0354": ("Ignition Coil D Primary/Secondary Circuit", WARNING),
    "P0380": ("Glow Plug/Heater Circuit A",            WARNING),
    "P0400": ("EGR Flow Malfunction",                  WARNING),
    "P0401": ("EGR Insufficient Flow",                 WARNING),
    "P0402": ("EGR Excessive Flow",                    WARNING),
    "P0411": ("Secondary Air Injection System Incorrect Flow", WARNING),
    "P0420": ("Catalyst System Efficiency Low Bank 1", WARNING),
    "P0421": ("Warm Up Catalyst Efficiency Low Bank 1", WARNING),
    "P0430": ("Catalyst System Efficiency Low Bank 2", WARNING),
    "P0440": ("EVAP Emission Control System Malfunction", WARNING),
    "P0441": ("EVAP Emission Control System Incorrect Purge Flow", WARNING),
    "P0442": ("EVAP System Small Leak Detected",       INFO),
    "P0443": ("EVAP Purge Control Valve Circuit",      WARNING),
    "P0444": ("EVAP Purge Control Valve Circuit Open", WARNING),
    "P0445": ("EVAP Purge Control Valve Circuit Shorted", WARNING),
    "P0446": ("EVAP Vent Control Circuit",             WARNING),
    "P0449": ("EVAP Vent Solenoid Control Circuit",    WARNING),
    "P0450": ("EVAP Pressure Sensor Malfunction",      INFO),
    "P0451": ("EVAP Pressure Sensor Range/Performance", INFO),
    "P0452": ("EVAP Pressure Sensor Low Input",        INFO),
    "P0453": ("EVAP Pressure Sensor High Input",       WARNING),
    "P0455": ("EVAP System Large Leak Detected",       WARNING),
    "P0456": ("EVAP System Very Small Leak",           INFO),
    "P0460": ("Fuel Level Sensor Circuit",             INFO),
    "P0480": ("Cooling Fan 1 Control Circuit",         WARNING),
    "P0481": ("Cooling Fan 2 Control Circuit",         WARNING),
    "P0500": ("Vehicle Speed Sensor Malfunction",      WARNING),
    "P0501": ("VSS Range/Performance",                 WARNING),
    "P0505": ("Idle Control System Malfunction",       WARNING),
    "P0506": ("Idle Control System RPM Too Low",       WARNING),
    "P0507": ("Idle Control System RPM Too High",      WARNING),
    "P0510": ("Closed Throttle Position Switch",       WARNING),
    "P0520": ("Engine Oil Pressure Sensor Circuit",    CRITICAL),
    "P0521": ("Engine Oil Pressure Sensor Range",      CRITICAL),
    "P0522": ("Engine Oil Pressure Sensor Low",        CRITICAL),
    "P0523": ("Engine Oil Pressure Sensor High",       CRITICAL),
    "P0530": ("A/C Refrigerant Pressure Sensor",       INFO),
    "P0532": ("A/C Refrigerant Pressure Sensor Low",   INFO),
    "P0533": ("A/C Refrigerant Pressure Sensor High",  INFO),
    "P0540": ("Intake Air Heater A Circuit",           INFO),
    "P0550": ("Power Steering Pressure Sensor Circuit", INFO),
    "P0560": ("System Voltage Malfunction",            WARNING),
    "P0562": ("System Voltage Low",                    WARNING),
    "P0563": ("System Voltage High",                   WARNING),
    "P0571": ("Cruise Control/Brake Switch A Circuit", INFO),
    "P0600": ("Serial Communication Link",             WARNING),
    "P0601": ("Internal Control Module Memory Check Sum Error", CRITICAL),
    "P0602": ("Control Module Programming Error",      CRITICAL),
    "P0603": ("Internal Control Module KAM Error",     CRITICAL),
    "P0604": ("Internal Control Module RAM Error",     CRITICAL),
    "P0605": ("Internal Control Module ROM Error",     CRITICAL),
    "P0606": ("PCM Processor Fault",                   CRITICAL),
    "P0620": ("Generator Control Circuit",             WARNING),
    "P0625": ("Generator Field Terminal Circuit Low",  WARNING),
    "P0626": ("Generator Field Terminal Circuit High", WARNING),
    "P0630": ("VIN Not Programmed",                    INFO),
    "P0641": ("Sensor Reference Voltage A Circuit Open", WARNING),
    "P0645": ("A/C Clutch Relay Control Circuit",      INFO),
    "P0650": ("MIL Control Circuit",                   WARNING),
    "P0660": ("Intake Manifold Tuning Valve Control",  WARNING),
    "P0700": ("Transmission Control System Malfunction", WARNING),
    "P0705": ("Transmission Range Sensor Circuit",     WARNING),
    "P0710": ("Transmission Fluid Temperature Sensor", WARNING),
    "P0715": ("Input/Turbine Speed Sensor Circuit",    WARNING),
    "P0720": ("Output Speed Sensor Circuit",           WARNING),
    "P0725": ("Engine Speed Input Circuit",            WARNING),
    "P0730": ("Incorrect Gear Ratio",                  WARNING),
    "P0740": ("Torque Converter Clutch Circuit",       WARNING),
    "P0748": ("Pressure Control Solenoid Electrical",  WARNING),
    "P0750": ("Shift Solenoid A",                      WARNING),
    "P0753": ("Shift Solenoid A Electrical",           WARNING),
    "P0755": ("Shift Solenoid B",                      WARNING),
    "P0758": ("Shift Solenoid B Electrical",           WARNING),
    "P0760": ("Shift Solenoid C",                      WARNING),
    "P0763": ("Shift Solenoid C Electrical",           WARNING),
    "P0770": ("Shift Solenoid E",                      WARNING),
    "P0773": ("Shift Solenoid E Electrical",           WARNING),
    "P0850": ("Park/Neutral Switch Input Circuit",     INFO),
    "P0A00": ("Motor Electronics Coolant Temp Sensor", WARNING),
    "P0A0F": ("Engine Failed To Start",                CRITICAL),
    "P0A80": ("Replace Hybrid Battery Pack",           CRITICAL),
    "P0A94": ("DC/DC Converter Performance",           WARNING),
    # Body codes
    "B0001": ("Deployment Loop Resistance Low",        CRITICAL),
    "B0020": ("Front Crash Sensor Feed Circuit",       CRITICAL),
    "B0051": ("Airbag System",                         CRITICAL),
    "B0100": ("SDM Internal",                          WARNING),
    # Chassis codes
    "C0035": ("Left Front Wheel Speed Sensor",         WARNING),
    "C0040": ("Right Front Wheel Speed Sensor",        WARNING),
    "C0045": ("Left Rear Wheel Speed Sensor",          WARNING),
    "C0050": ("Right Rear Wheel Speed Sensor",         WARNING),
    "C0110": ("Pump Motor Circuit",                    WARNING),
    "C0121": ("Valve Relay Circuit",                   WARNING),
    "C0161": ("ABS/TCS Brake Switch Circuit",          WARNING),
    "C0265": ("EBCM Relay Circuit",                    WARNING),
    # Network codes
    "U0001": ("High Speed CAN Communication Bus",      WARNING),
    "U0100": ("Lost Communication With ECM/PCM",       CRITICAL),
    "U0101": ("Lost Communication With TCM",           WARNING),
    "U0121": ("Lost Communication With ABS",           WARNING),
    "U0140": ("Lost Communication With BCM",           WARNING),
    "U0155": ("Lost Communication With Instrument Panel", WARNING),
    "U0300": ("Internal Control Module Software Incompatibility", WARNING),
    # Hyundai/Kia specific P1 codes
    "P1100": ("MAP Sensor Intermittent",               WARNING),
    "P1120": ("TPS Intermittent",                      WARNING),
    "P1140": ("Intake Air Temp Sensor 2 Circuit",      WARNING),
    "P1170": ("O2 Sensor Stuck Lean B1S1",             WARNING),
    "P1172": ("O2 Sensor Stuck Rich B1S1",             WARNING),
    "P1250": ("Pressure Regulator Control Solenoid",   WARNING),
    "P1259": ("VTEC System Malfunction",               WARNING),
    "P1300": ("Igniter Circuit Malfunction",           WARNING),
    "P1307": ("Chassis Acceleration Sensor",           WARNING),
    "P1326": ("KSDS Knock Sensor Detection System",    CRITICAL),
    "P1396": ("CKP Sensor Reluctor Ring Missing Tooth", CRITICAL),
    "P1402": ("EGR System",                            WARNING),
    "P1450": ("EVAP System",                           WARNING),
    "P1500": ("Starter Signal Circuit",                WARNING),
    "P1505": ("Idle Air Control System",               WARNING),
    "P1523": ("Throttle Body",                         WARNING),
    "P1529": ("A/C Request Signal",                    INFO),
    "P1600": ("PCM Serial Communications",             WARNING),
    "P1614": ("MIL Request Signal",                    WARNING),
    "P1618": ("Serial Peripheral Interface",           WARNING),
    "P1624": ("Customer Snapshot Request",             INFO),
    "P1693": ("DTC Detected In TCM",                   WARNING),
    "P1696": ("PCM Failure EEPROM Write Denied",       WARNING),
    "P1740": ("Torque Reduction Signal Circuit",       WARNING),
    "P1743": ("Torque Converter Clutch",               WARNING),
    "P1794": ("Speed Sensor Ground Circuit",           WARNING),
    "P1899": ("P/N Switch Stuck In Park",              WARNING),
}
```

### 3.3 DTC byte parser

OBD2 DTC encoding (SAE J1979): each DTC = 2 bytes.
- Byte 1 bits[7:6]: system type (00=P, 01=C, 10=B, 11=U)
- Byte 1 bits[5:4]: first digit (0-3)
- Byte 1 bits[3:0]: second digit (0-F)
- Byte 2 bits[7:4]: third digit (0-F)
- Byte 2 bits[3:0]: fourth digit (0-F)

```python
_TYPE = {0: "P", 1: "C", 2: "B", 3: "U"}

def parse_dtcs(raw):
    """Parse ELM327 response string into list of DTC code strings.
    
    '43 01 33 03 01 00 00' -> ['P0133', 'P0301']
    '43 00 00'             -> []
    'NO DATA'              -> []
    """
    parts = raw.upper().split()
    # Strip response mode byte (43=mode03, 47=mode07, 4A=mode0A)
    if parts and parts[0] in ("43", "47", "4A"):
        parts = parts[1:]
    dtcs = []
    for i in range(0, len(parts) - 1, 2):
        try:
            b1 = int(parts[i], 16)
            b2 = int(parts[i + 1], 16)
        except (ValueError, IndexError):
            break
        if b1 == 0 and b2 == 0:
            continue
        type_bits = (b1 >> 6) & 0x03
        d1 = (b1 >> 4) & 0x03
        d2 = b1 & 0x0F
        d3 = (b2 >> 4) & 0x0F
        d4 = b2 & 0x0F
        dtcs.append("{}{}{}{:X}{:X}".format(_TYPE[type_bits], d1, d2, d3, d4))
    return dtcs
```

### 3.4 Line enrichment

```python
# Response prefixes that indicate DTC data
_DTC_PREFIXES = {"43", "47", "4A"}

def enrich_line(line):
    """Enrich a raw scan log line if it contains DTC response data.

    Returns (enriched_text, highest_severity) where enriched_text appends
    decoded DTC entries and highest_severity is CRITICAL/WARNING/INFO/UNKNOWN.
    If no DTCs found, returns (line, None).
    """
    if "->" not in line:
        return line, None
    _, response = line.split("->", 1)
    parts = response.strip().upper().split()
    if not parts or parts[0] not in _DTC_PREFIXES:
        return line, None
    dtcs = parse_dtcs(response.strip())
    if not dtcs:
        return line, None
    decoded = []
    highest = INFO
    for code in dtcs:
        desc, sev = lookup(code)
        decoded.append((code, desc or "Unknown code", sev))
        if sev == CRITICAL:
            highest = CRITICAL
        elif sev == WARNING and highest != CRITICAL:
            highest = WARNING
    suffix = "".join(
        "\n  ► {:<8} {:<42} [{}]".format(c, d, s)
        for c, d, s in decoded
    )
    return line + suffix, highest
```

---

## 4. reporter.py changes

In `finish()`, after reading `.chk` lines and before writing `.md`, run DTC enrichment:

```python
from core import dtc_db

def finish(self):
    ...
    with open(self.chk_path) as f:
        raw_lines = f.readlines()
    # Enrich lines with DTC descriptions for the .md report
    md_lines = []
    for line in raw_lines:
        enriched, _ = dtc_db.enrich_line(line.rstrip())
        md_lines.append(enriched + "\n")
    # Write .raw (unmodified) and .md (enriched)
    with open(raw_path, "w") as f:
        f.writelines(raw_lines)
    with open(md_path, "w") as f:
        f.write("# OBD-REAPER — {}\n".format(self.mode.upper().replace("_", " ")))
        f.write("**Scan Date:** {}\n\n".format(self.ts))
        f.write("```\n")
        f.writelines(md_lines)
        f.write("```\n")
    ...
```

The `.raw` file always keeps unmodified bytes. The `.md` file gets the enriched version.

---

## 5. tui.py changes

In `_scan_screen`, the right panel log display gets DTC color coding. Currently:

```python
right_win.addstr(2 + i, 2, ("> " + log_line)[:right_w - 4], green)
```

Change to call `dtc_db.enrich_line(log_line)` and pick color by severity:

```python
from core import dtc_db as _dtc_db

# In _scan_screen right panel loop:
enriched, severity = _dtc_db.enrich_line(log_line)
if severity == _dtc_db.CRITICAL:
    line_attr = curses.color_pair(C_ERR) | curses.A_BOLD
elif severity == _dtc_db.WARNING:
    line_attr = curses.color_pair(C_WARN)
else:
    line_attr = green

# Display enriched text — may be multi-line (split on \n).
# Use a cumulative row_offset rather than bare `i` to handle extra DTC lines.
display_lines = ("> " + enriched).split("\n")
for j, dl in enumerate(display_lines):
    row = 2 + row_offset + j
    if row < log_win_h - 1:
        try:
            right_win.addstr(row, 2, dl[:right_w - 4], line_attr)
        except curses.error:
            pass
row_offset += len(display_lines)  # advance by actual lines consumed
```

**Important:** `log_lines` list still stores raw `line` strings (not enriched), because enrichment happens at display time only. The `.chk` file always gets raw data.

---

## 6. Tests — tests/test_dtc_db.py

```python
class TestLookup(unittest.TestCase):
    def test_known_critical_code(self):
        desc, sev = dtc_db.lookup("P0301")
        self.assertIn("Misfire", desc)
        self.assertEqual(sev, dtc_db.CRITICAL)

    def test_unknown_code_returns_none_unknown(self):
        desc, sev = dtc_db.lookup("P9999")
        self.assertIsNone(desc)
        self.assertEqual(sev, dtc_db.UNKNOWN)

    def test_case_insensitive(self):
        desc1, sev1 = dtc_db.lookup("p0301")
        desc2, sev2 = dtc_db.lookup("P0301")
        self.assertEqual(desc1, desc2)
        self.assertEqual(sev1, sev2)

    def test_hyundai_p1326(self):
        desc, sev = dtc_db.lookup("P1326")
        self.assertIn("KSDS", desc)
        self.assertEqual(sev, dtc_db.CRITICAL)

class TestParseDtcs(unittest.TestCase):
    def test_single_dtc(self):
        self.assertEqual(dtc_db.parse_dtcs("43 01 33"), ["P0133"])

    def test_multiple_dtcs(self):
        result = dtc_db.parse_dtcs("43 01 33 03 01")
        self.assertEqual(result, ["P0133", "P0301"])

    def test_null_dtc_filtered(self):
        self.assertEqual(dtc_db.parse_dtcs("43 00 00"), [])

    def test_no_data_returns_empty(self):
        self.assertEqual(dtc_db.parse_dtcs("NO DATA"), [])

class TestEnrichLine(unittest.TestCase):
    def test_dtc_line_enriched(self):
        enriched, sev = dtc_db.enrich_line("03 -> 43 03 01")
        self.assertIn("P0301", enriched)
        self.assertEqual(sev, dtc_db.CRITICAL)

    def test_non_dtc_line_unchanged(self):
        line = "0101 -> 41 01 00 07 E0 00"
        enriched, sev = dtc_db.enrich_line(line)
        self.assertEqual(enriched, line)
        self.assertIsNone(sev)

    def test_no_dtcs_in_response_returns_none_severity(self):
        enriched, sev = dtc_db.enrich_line("03 -> 43 00 00")
        self.assertIsNone(sev)
```

---

## 7. Out of Scope

- Interactive DTC decoder screen (menu item)
- Network lookup of DTC descriptions
- Manufacturer-specific codes beyond Hyundai/Kia P1xxx
- DTC freeze frame correlation
- ECU FINGERPRINT and THREAT LEVEL (Phase 2 and 3)
