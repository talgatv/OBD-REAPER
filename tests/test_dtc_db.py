import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.dtc_db as dtc_db


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
        # 43=mode03 response, 01 33 = P0133
        self.assertEqual(dtc_db.parse_dtcs("43 01 33"), ["P0133"])

    def test_multiple_dtcs(self):
        # 01 33 = P0133, 03 01 = P0301
        result = dtc_db.parse_dtcs("43 01 33 03 01")
        self.assertEqual(result, ["P0133", "P0301"])

    def test_null_dtc_filtered(self):
        # 00 00 pairs are "no DTC" padding — must be excluded
        self.assertEqual(dtc_db.parse_dtcs("43 00 00"), [])

    def test_no_data_returns_empty(self):
        self.assertEqual(dtc_db.parse_dtcs("NO DATA"), [])

    def test_hybrid_code_high_nibble(self):
        # b1=0x0A: d2=A (hex), must use {:X} not {} in format string
        # 43 0A 80 = mode03 response with P0A80 (Replace Hybrid Battery Pack)
        result = dtc_db.parse_dtcs("43 0A 80")
        self.assertEqual(result, ["P0A80"])


class TestEnrichLine(unittest.TestCase):
    def test_dtc_line_enriched(self):
        # 03 -> 43 03 01  means mode03 response with P0301
        enriched, sev = dtc_db.enrich_line("03 -> 43 03 01")
        self.assertIn("P0301", enriched)
        self.assertEqual(sev, dtc_db.CRITICAL)

    def test_non_dtc_line_unchanged(self):
        line = "0101 -> 41 01 00 07 E0 00"
        enriched, sev = dtc_db.enrich_line(line)
        self.assertEqual(enriched, line)
        self.assertIsNone(sev)

    def test_no_dtcs_in_response_returns_none_severity(self):
        # 43 00 00 is a valid mode03 response but contains no DTCs
        enriched, sev = dtc_db.enrich_line("03 -> 43 00 00")
        self.assertIsNone(sev)


if __name__ == "__main__":
    unittest.main()
