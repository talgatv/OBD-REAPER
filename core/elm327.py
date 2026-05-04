#!/usr/bin/env python3
import serial
import time
import glob
import os
import fcntl
import subprocess

USBDEVFS_RESET = 21780
BAUD = 38400
TIMEOUT = 5


class ELMConnectionError(Exception):
    pass


class ELM327:
    def __init__(self, port=None):
        self._port = port
        self._ser = None

    def find_port(self):
        for pattern in ["/dev/ttyACM*", "/dev/ttyUSB*"]:
            ports = sorted(glob.glob(pattern))
            if ports:
                return ports[-1]
        return None

    def usb_reset(self):
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if "0918:7104" in line:  # ELM327 OBD2 USB adapter VID:PID
                    parts = line.split()
                    bus, dev = parts[1], parts[3].rstrip(":")
                    path = "/dev/bus/usb/{}/{}".format(bus, dev)
                    fd = os.open(path, os.O_WRONLY)
                    try:
                        fcntl.ioctl(fd, USBDEVFS_RESET, 0)
                    finally:
                        os.close(fd)
                    time.sleep(2)
                    return True
        except Exception:
            pass
        return False

    def connect(self, usb_reset=True):
        if usb_reset:
            self.usb_reset()

        port = self._port or self.find_port()
        if not port:
            raise ELMConnectionError(
                "No OBD adapter found on /dev/ttyACM* or /dev/ttyUSB*"
            )

        last_err = None
        last_resp = None
        for _ in range(5):
            try:
                if self._ser:
                    self._ser.close()
                    time.sleep(0.5)
                self._ser = serial.Serial(
                    port, baudrate=BAUD, timeout=TIMEOUT,
                    bytesize=8, parity="N", stopbits=1,
                    xonxoff=False, rtscts=False, dsrdtr=False,
                )
                self._ser.setDTR(True)
                self._ser.setRTS(True)
                time.sleep(0.3)
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
                self._ser.write(b"\r\r\r")
                time.sleep(0.3)
                self._ser.reset_input_buffer()
                self._ser.write(b"ATZ\r")
                time.sleep(3)
                resp = self._ser.read(2048).decode(errors="replace").strip()
                last_resp = resp
                if "ELM" in resp or ">" in resp:
                    self._init()
                    return
            except (serial.SerialException, OSError) as e:
                last_err = e
                new_port = self._port or self.find_port()
                if new_port:
                    port = new_port
            time.sleep(2)

        raise ELMConnectionError(
            "ELM327 did not respond after 5 attempts. Last error: {}. Last response: {!r}".format(
                last_err, last_resp
            )
        )

    def _init(self):
        for cmd in ["ATE0", "ATL0", "ATH1", "ATSP0"]:
            self.send(cmd, wait=1.0)

    def send(self, cmd, wait=2.0):
        if not self._ser or not self._ser.is_open:
            raise ELMConnectionError("Not connected")
        self._ser.reset_input_buffer()
        self._ser.write((cmd + "\r").encode())
        time.sleep(wait)
        raw = self._ser.read(4096).decode(errors="replace").strip()
        return raw.replace("\r", " ").replace(">", "").strip()

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
            self._ser = None
