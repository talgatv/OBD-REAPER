import unittest
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.reporter as reporter_module


def make_reporter(mode="quick_scan"):
    tmpdir = tempfile.mkdtemp()
    reporter_module.REPORTS_DIR = os.path.join(tmpdir, "reports")
    reporter_module.CHECKPOINTS_DIR = os.path.join(
        reporter_module.REPORTS_DIR, ".checkpoints"
    )
    return reporter_module.Reporter(mode)


class TestReporter(unittest.TestCase):
    def test_start_creates_checkpoint_file(self):
        r = make_reporter()
        r.start()
        self.assertTrue(os.path.exists(r.chk_path))
        r._chk_file.close()

    def test_checkpoint_writes_line(self):
        r = make_reporter()
        r.start()
        r.checkpoint("03 -> 43 01 13 26")
        r._chk_file.close()
        with open(r.chk_path) as f:
            self.assertIn("03 -> 43 01 13 26", f.read())

    def test_finish_creates_md_file(self):
        r = make_reporter()
        r.start()
        r.checkpoint("03 -> 43 01 13 26")
        md_path = r.finish()
        self.assertTrue(os.path.exists(md_path))
        self.assertTrue(md_path.endswith(".md"))

    def test_finish_creates_raw_file(self):
        r = make_reporter()
        r.start()
        r.checkpoint("test line")
        md_path = r.finish()
        raw_path = md_path.replace(".md", ".raw")
        self.assertTrue(os.path.exists(raw_path))

    def test_finish_deletes_checkpoint(self):
        r = make_reporter()
        r.start()
        r.checkpoint("test")
        chk_path = r.chk_path
        r.finish()
        self.assertFalse(os.path.exists(chk_path))

    def test_finish_md_contains_scan_data(self):
        r = make_reporter()
        r.start()
        r.checkpoint("03 -> 43 01 13 26")
        md_path = r.finish()
        with open(md_path) as f:
            content = f.read()
        self.assertIn("OBD-REAPER", content)
        self.assertIn("43 01 13 26", content)

    def test_find_incomplete_returns_chk_files(self):
        r = make_reporter()
        r.start()
        r._chk_file.close()
        incomplete = reporter_module.Reporter.find_incomplete()
        self.assertEqual(len(incomplete), 1)
        self.assertTrue(incomplete[0].endswith(".chk"))

    def test_list_reports_returns_md_files(self):
        r = make_reporter()
        r.start()
        r.checkpoint("test")
        r.finish()
        reports = reporter_module.Reporter.list_reports()
        self.assertEqual(len(reports), 1)
        fname, path, size = reports[0]
        self.assertTrue(fname.endswith(".md"))
        self.assertGreater(size, 0)


class TestFromCheckpoint(unittest.TestCase):
    def test_parses_ts_mode_and_skip_count(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("03 -> 43 01 13")
        r.checkpoint("07 -> 47 00")
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        self.assertEqual(r2.ts, r.ts)
        self.assertEqual(r2.mode, "quick_scan")
        self.assertEqual(skip, 2)

    def test_empty_checkpoint_gives_skip_zero(self):
        r = make_reporter("full_scan")
        r.start()
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        self.assertEqual(skip, 0)

    def test_start_append_preserves_existing_lines(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("line1")
        r._chk_file.close()
        r2, skip = reporter_module.Reporter.from_checkpoint(r.chk_path)
        r2.start_append()
        r2.checkpoint("line2")
        r2._chk_file.close()
        with open(r2.chk_path) as f:
            content = f.read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)

    def test_salvage_produces_md_from_existing_chk(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("03 -> 43 01 13")
        r._chk_file.close()
        r2, _ = reporter_module.Reporter.from_checkpoint(r.chk_path)
        md_path = r2.finish()
        self.assertTrue(os.path.exists(md_path))
        self.assertFalse(os.path.exists(r2.chk_path))
        with open(md_path) as f:
            self.assertIn("43 01 13", f.read())

    def test_start_append_raises_if_chk_missing(self):
        r = make_reporter("quick_scan")
        r.chk_path = "/tmp/nonexistent_sentinel_file_obd_reaper.chk"
        with self.assertRaises(FileNotFoundError):
            r.start_append()


class TestReporterDtcEnrichment(unittest.TestCase):
    def test_finish_md_enriches_dtc_lines(self):
        r = make_reporter("quick_scan")
        r.start()
        # 43 03 01 = mode03 response containing P0301 (Misfire Detected Cylinder 1)
        r.checkpoint("03 -> 43 03 01")
        md_path = r.finish()
        with open(md_path) as f:
            content = f.read()
        self.assertIn("P0301", content)
        self.assertIn("Misfire", content)

    def test_finish_raw_stays_unmodified(self):
        r = make_reporter("quick_scan")
        r.start()
        r.checkpoint("03 -> 43 03 01")
        md_path = r.finish()
        raw_path = md_path.replace(".md", ".raw")
        with open(raw_path) as f:
            content = f.read()
        # .raw must contain the original bytes, NOT the decoded description
        self.assertIn("43 03 01", content)
        self.assertNotIn("P0301", content)


if __name__ == "__main__":
    unittest.main()
