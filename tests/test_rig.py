import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from rig import RigController, enumerate_ports


class TestParseFaResponse(unittest.TestCase):
    def setUp(self):
        self.controller = RigController.__new__(RigController)

    def test_valid_response(self):
        self.assertEqual(self.controller._parse_fa("FA00014225000;"), 14225000)

    def test_malformed_response(self):
        with self.assertRaises(ValueError):
            self.controller._parse_fa("GARBAGE;")

    def test_empty_string(self):
        with self.assertRaises(ValueError):
            self.controller._parse_fa("")

    def test_partial_response(self):
        self.assertIsNone(self.controller._parse_fa(None))


class TestEnumeratePorts(unittest.TestCase):
    @patch("rig.list_ports")
    def test_returns_cu_ports(self, mock_list_ports):
        mock_port = MagicMock()
        mock_port.device = "/dev/cu.usbserial-1234"
        mock_list_ports.comports.return_value = [mock_port]
        ports = enumerate_ports()
        self.assertEqual(ports, ["/dev/cu.usbserial-1234"])

    @patch("rig.list_ports")
    def test_raises_if_none_found(self, mock_list_ports):
        mock_list_ports.comports.return_value = []
        with self.assertRaises(RuntimeError):
            enumerate_ports()

    @patch("rig.list_ports")
    def test_filters_tty_ports(self, mock_list_ports):
        mock_tty = MagicMock()
        mock_tty.device = "/dev/tty.usbserial-1234"
        mock_cu = MagicMock()
        mock_cu.device = "/dev/cu.usbserial-1234"
        mock_list_ports.comports.return_value = [mock_tty, mock_cu]
        ports = enumerate_ports()
        self.assertEqual(ports, ["/dev/cu.usbserial-1234"])


class TestPollPopulatesQueue(unittest.TestCase):
    @patch("rig.serial.Serial")
    def test_queue_receives_frequency(self, mock_serial_cls):
        mock_serial = MagicMock()
        mock_serial.read_until.return_value = b"FA00014225000;"
        mock_serial_cls.return_value = mock_serial

        q = queue.Queue(maxsize=1)
        controller = RigController("/dev/cu.usbserial-test", q)
        controller.start()
        try:
            freq = q.get(timeout=0.5)
            self.assertEqual(freq, 14225000)
        finally:
            controller.stop()


class TestSerialTimeoutHoldsLastValue(unittest.TestCase):
    @patch("rig.serial.Serial")
    def test_holds_last_known_frequency(self, mock_serial_cls):
        import serial as pyserial

        mock_serial = MagicMock()
        mock_serial.read_until.side_effect = [
            b"FA00014225000;",
            pyserial.SerialTimeoutException(),
            pyserial.SerialTimeoutException(),
        ]
        mock_serial_cls.return_value = mock_serial

        q = queue.Queue(maxsize=1)
        controller = RigController("/dev/cu.usbserial-test", q)
        controller.start()
        try:
            freq = q.get(timeout=0.5)
            self.assertEqual(freq, 14225000)
        finally:
            controller.stop()


class TestThreadStopsCleanly(unittest.TestCase):
    @patch("rig.serial.Serial")
    def test_stop_joins_within_one_second(self, mock_serial_cls):
        mock_serial = MagicMock()
        mock_serial.read_until.return_value = b"FA00014225000;"
        mock_serial_cls.return_value = mock_serial

        q = queue.Queue(maxsize=1)
        controller = RigController("/dev/cu.usbserial-test", q)
        controller.start()
        controller.stop()
        self.assertFalse(controller._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
