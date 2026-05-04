class HyundaiSonataPlugin:
    NAME = "Hyundai Sonata Hybrid 2016"
    VEHICLE_ID = "hyundai_sonata_2016"
    COMMANDS = [
        ("22F190", "VIN (UDS)"),
        ("22F191", "Hardware PN"),
        ("22F193", "Software PN"),
        ("22F40D", "Speed (UDS)"),
        ("22F40E", "RPM (UDS)"),
        ("22B001", "Engine Data 1"),
        ("22B002", "Engine Data 2"),
        ("22C001", "KSDS Counter 1"),
        ("22C002", "KSDS Counter 2"),
        ("22C003", "KSDS Counter 3"),
        ("22D001", "Misfire Data 1"),
        ("22D002", "Misfire Data 2"),
        ("22D100", "Cylinder 1 Data"),
        ("22D101", "Cylinder 2 Data"),
        ("22D102", "Cylinder 3 Data"),
        ("22D103", "Cylinder 4 Data"),
    ]

    def interpret(self, pid, raw):
        if pid == "22F190":
            try:
                parts = raw.split()
                data = [int(b, 16) for b in parts if len(b) == 2]
                import re
                raw_chars = "".join(chr(b) for b in data[3:] if chr(b).isalnum())
                m = re.search(r'[A-Z0-9]{17}', raw_chars)
                if m:
                    return "VIN: {}".format(m.group())
            except Exception:
                pass
        return None
