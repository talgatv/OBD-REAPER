import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import load_plugins


class TestLoadPlugins(unittest.TestCase):
    def setUp(self):
        self.plugins = load_plugins()

    def test_finds_hyundai_plugin(self):
        self.assertIn("Hyundai Sonata Hybrid 2016", self.plugins)

    def test_finds_toyota_plugin(self):
        self.assertIn("Toyota Prius Gen3 (stub)", self.plugins)

    def test_all_plugins_have_required_attributes(self):
        for name, plugin in self.plugins.items():
            self.assertTrue(hasattr(plugin, "NAME"), "{} missing NAME".format(name))
            self.assertTrue(hasattr(plugin, "VEHICLE_ID"), "{} missing VEHICLE_ID".format(name))
            self.assertTrue(hasattr(plugin, "COMMANDS"), "{} missing COMMANDS".format(name))
            self.assertTrue(callable(plugin.interpret), "{} missing interpret()".format(name))

    def test_commands_are_list_of_pairs(self):
        for name, plugin in self.plugins.items():
            for entry in plugin.COMMANDS:
                self.assertEqual(len(entry), 2, "{} command not a pair".format(name))
                pid, label = entry
                self.assertIsInstance(pid, str)
                self.assertIsInstance(label, str)

    def test_interpret_returns_string_or_none(self):
        plugin = self.plugins["Hyundai Sonata Hybrid 2016"]
        result = plugin.interpret("22C001", "62 C0 01 00 00")
        self.assertTrue(result is None or isinstance(result, str))

    def test_hyundai_has_ksds_commands(self):
        plugin = self.plugins["Hyundai Sonata Hybrid 2016"]
        pids = [cmd for cmd, _ in plugin.COMMANDS]
        self.assertIn("22C001", pids)
        self.assertIn("22D100", pids)


if __name__ == "__main__":
    unittest.main()
