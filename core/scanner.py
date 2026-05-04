#!/usr/bin/env python3
import time as _time


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

        # Mode 02: freeze frame
        for cmd, label in FREEZE_PIDS:
            pct = int(done / total * 100)
            if done < skip:
                done += 1
                yield (pct, label, "")
                continue
            raw = self.elm.send(cmd, wait=1.5)
            done += 1
            yield (pct, label, "{} -> {}".format(cmd, raw))

        # Mode 06: OBD monitor test results
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

        if done < total:
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
