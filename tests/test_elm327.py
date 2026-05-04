import unittest
from unittest.mock import MagicMock, patch
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial

from core.elm327 import ELM327, ELMConnectionError


class TestFindPort(unittest.TestCase):
    @patch("glob.glob", side_effect=lambda p: ["/dev/ttyACM0"] if "ACM" in p else [])
    def test_finds_acm_port(self, _):
        self.assertEqual(ELM327().find_port(), "/dev/ttyACM0")

    @patch("glob.glob", return_value=[])
    def test_returns_none_when_no_port(self, _):
        self.assertIsNone(ELM327().find_port())

    @patch("glob.glob", side_effect=lambda p: ["/dev/ttyACM0", "/dev/ttyACM1"] if "ACM" in p else [])
    def test_picks_latest_acm(self, _):
        self.assertEqual(ELM327().find_port(), "/dev/ttyACM1")


class TestSend(unittest.TestCase):
    def _elm(self, response_bytes):
        elm = ELM327(port="/dev/ttyACM0")
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ser.read.return_value = response_bytes
        elm._ser = mock_ser
        return elm

    def test_returns_cleaned_response(self):
        self.assertEqual(self._elm(b"41 04 3C\r>").send("0104", wait=0), "41 04 3C")

    def test_strips_prompt_and_cr(self):
        self.assertEqual(self._elm(b"OK\r>").send("ATE0", wait=0), "OK")

    def test_raises_when_not_connected(self):
        with self.assertRaises(ELMConnectionError):
            ELM327().send("ATI")


class TestConnect(unittest.TestCase):
    @patch("core.elm327.ELM327.usb_reset", return_value=False)
    @patch("core.elm327.ELM327.find_port", return_value=None)
    def test_raises_when_no_port(self, *_):
        with self.assertRaises(ELMConnectionError):
            ELM327().connect()

    @patch("core.elm327.ELM327.usb_reset", return_value=False)
    @patch("core.elm327.ELM327._init")
    @patch("serial.Serial")
    @patch("core.elm327.ELM327.find_port", return_value="/dev/ttyACM0")
    def test_calls_init_on_elm_response(self, _, mock_serial, mock_init, __):
        mock_ser = MagicMock()
        mock_ser.read.return_value = b"ELM327 v2.2\r>"
        mock_serial.return_value = mock_ser
        elm = ELM327()
        elm.connect()
        mock_init.assert_called_once()

    @patch("core.elm327.ELM327.usb_reset", return_value=False)
    @patch("core.elm327.ELM327.find_port", return_value="/dev/ttyACM0")
    @patch("core.elm327.time.sleep")
    def test_raises_elm_connection_error_on_serial_exception_every_attempt(
        self, _sleep, _find_port, _usb_reset
    ):
        with patch("serial.Serial", side_effect=serial.SerialException("no device")):
            with self.assertRaises(ELMConnectionError):
                ELM327().connect(usb_reset=False)


class TestUsbReset(unittest.TestCase):
    @patch("core.elm327.time.sleep")
    @patch("fcntl.ioctl")
    @patch("os.open", return_value=99)
    @patch("os.close")
    def test_returns_true_when_device_found(
        self, mock_close, mock_open, mock_ioctl, _sleep
    ):
        fake_lsusb = (
            "Bus 001 Device 003: ID 0918:7104 some ELM327 OBD2 adapter\n"
        )
        fake_result = MagicMock()
        fake_result.stdout = fake_lsusb

        with patch("subprocess.run", return_value=fake_result):
            result = ELM327().usb_reset()

        self.assertTrue(result)
        mock_open.assert_called_once_with(
            "/dev/bus/usb/001/003", os.O_WRONLY
        )
        mock_ioctl.assert_called_once()
        mock_close.assert_called_once_with(99)

    @patch("subprocess.run", side_effect=Exception("lsusb not found"))
    def test_returns_false_on_exception(self, _):
        self.assertFalse(ELM327().usb_reset())


if __name__ == "__main__":
    unittest.main()
