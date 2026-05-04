class ToyotaPriusPlugin:
    NAME = "Toyota Prius Gen3 (stub)"
    VEHICLE_ID = "toyota_prius_gen3"
    COMMANDS = [
        ("21F1", "HV Battery Voltage"),
        ("21F2", "HV Battery Current"),
        ("21BC", "Inverter Temperature"),
        ("21B0", "MG1 RPM"),
        ("21B1", "MG2 RPM"),
        ("21B4", "HV Battery SOC"),
    ]

    def interpret(self, pid, raw):
        return None  # stub — raw hex shown as-is
