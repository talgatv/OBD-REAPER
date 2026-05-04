import unittest
from unittest.mock import MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scanner import Scanner


def make_scanner(response="41 04 3C"):
    mock_elm = MagicMock()
    mock_elm.send.return_value = response
    return Scanner(mock_elm)


class TestQuickScan(unittest.TestCase):
    def test_yields_four_steps_plus_complete(self):
        results = list(make_scanner().quick_scan())
        self.assertEqual(len(results), 5)

    def test_last_yield_is_100_complete(self):
        pct, label, _ = list(make_scanner().quick_scan())[-1]
        self.assertEqual(pct, 100)
        self.assertIn("COMPLETE", label)

    def test_all_yields_are_int_str_str_tuples(self):
        for pct, label, line in make_scanner().quick_scan():
            self.assertIsInstance(pct, int)
            self.assertIsInstance(label, str)
            self.assertIsInstance(line, str)

    def test_log_line_contains_command_and_response(self):
        s = make_scanner(response="43 01 13 26")
        pct, _, line = list(s.quick_scan())[0]
        self.assertIn("03", line)
        self.assertIn("43 01 13 26", line)


class TestAdapterInfo(unittest.TestCase):
    def test_yields_five_steps_plus_complete(self):
        self.assertEqual(len(list(make_scanner().adapter_info())), 6)

    def test_sends_ati_atrv_atdp(self):
        s = make_scanner()
        list(s.adapter_info())
        sent = [c[0][0] for c in s.elm.send.call_args_list]
        for cmd in ["ATI", "ATRV", "ATDP", "ATDPN", "ATIGN"]:
            self.assertIn(cmd, sent)


class TestCylinderTest(unittest.TestCase):
    def test_yields_eight_steps_plus_complete(self):
        self.assertEqual(len(list(make_scanner().cylinder_test())), 9)

    def test_sets_ecu_header_for_mode22(self):
        s = make_scanner()
        list(s.cylinder_test())
        sent = [c[0][0] for c in s.elm.send.call_args_list]
        self.assertIn("ATSH 7E0", sent)
        self.assertIn("ATSH 7DF", sent)


class TestClearCodes(unittest.TestCase):
    def test_yields_single_100_complete(self):
        results = list(make_scanner().clear_codes())
        self.assertEqual(len(results), 1)
        pct, _, _ = results[0]
        self.assertEqual(pct, 100)

    def test_sends_mode_04(self):
        s = make_scanner()
        list(s.clear_codes())
        sent = [c[0][0] for c in s.elm.send.call_args_list]
        self.assertIn("04", sent)


class TestUdsScan(unittest.TestCase):
    def test_runs_plugin_commands_plus_complete(self):
        s = make_scanner()
        mock_plugin = MagicMock()
        mock_plugin.COMMANDS = [("22C001", "KSDS"), ("22D100", "Cyl1")]
        mock_plugin.interpret.return_value = None
        self.assertEqual(len(list(s.uds_scan(mock_plugin))), 3)

    def test_uses_interpret_result_when_not_none(self):
        s = make_scanner(response="62 C0 01 AA")
        mock_plugin = MagicMock()
        mock_plugin.COMMANDS = [("22C001", "KSDS")]
        mock_plugin.interpret.return_value = "KSDS: 42"
        _, _, line = list(s.uds_scan(mock_plugin))[0]
        self.assertIn("KSDS: 42", line)


class TestLiveData(unittest.TestCase):
    def test_yields_dict_with_pid_names(self):
        s = make_scanner()
        gen = s.live_data()
        readings = next(gen)
        self.assertIsInstance(readings, dict)
        self.assertIn("RPM", readings)
        self.assertIn("Speed km/h", readings)


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
        self.assertEqual(results[-1][0], 100)
        self.assertEqual(s.elm.send.call_count, 0)

    def test_full_scan_skip_past_uds_boundary(self):
        # skip=27 means: 16 fingerprint + 4 dtc_steps + 7 UDS_ECUS all done, first FULL_PID is next
        s = make_scanner()
        results = list(s.full_scan(skip=27))
        non_empty = [r for r in results if r[2]]
        # 80 total data steps, 27 skipped = 53 real data lines
        self.assertEqual(len(non_empty), 53)

    def test_full_scan_yields_81_steps(self):
        s = make_scanner()
        steps = list(s.full_scan())
        # 16 fingerprint + 4 dtc + 7 uds + 34 pids + 8 freeze + 8 mode06 + 3 vehicle = 80 data
        # + 1 FULL SCAN COMPLETE = 81 total
        self.assertEqual(len(steps), 81)

    def test_cylinder_test_skip_at_mode22_boundary(self):
        # skip=4 means all 4 mode06 steps done, mode22 starts fresh
        s = make_scanner()
        results = list(s.cylinder_test(skip=4))
        non_empty = [r for r in results if r[2]]
        # 4 mode06 skipped + 4 mode22 real = 4 non-empty
        self.assertEqual(len(non_empty), 4)

    def test_quick_scan_skip_beyond_total_no_crash(self):
        # skip > total_steps: all yields empty, no ELM sends
        s = make_scanner()
        results = list(s.quick_scan(skip=100))
        non_empty = [r for r in results if r[2]]
        self.assertEqual(len(non_empty), 0)
        self.assertEqual(s.elm.send.call_count, 0)


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


if __name__ == "__main__":
    unittest.main()
