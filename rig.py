import queue
import threading
import time

import serial
from serial.tools import list_ports


def enumerate_ports() -> list:
    ports = [p.device for p in list_ports.comports() if p.device.startswith("/dev/cu.")]
    if not ports:
        raise RuntimeError("No /dev/cu.* serial ports found")
    return ports


class RigController:
    def __init__(self, port: str, freq_queue: queue.Queue, baud: int = 4800):
        self._port = port
        self._queue = freq_queue
        self._baud = baud
        self._stop_event = threading.Event()
        self._thread = None
        self._last_freq = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _poll_loop(self):
        ser = None
        try:
            ser = serial.Serial(self._port, self._baud, timeout=1.0)
            while not self._stop_event.is_set():
                try:
                    freq = self._parse_fa(self._send_cat(ser, "FA;"))
                    if freq is not None:
                        self._last_freq = freq
                except (serial.SerialTimeoutException, serial.SerialException):
                    pass
                except ValueError:
                    pass

                if self._last_freq is not None:
                    try:
                        self._queue.put_nowait(self._last_freq)
                    except queue.Full:
                        pass

                self._stop_event.wait(0.2)
        finally:
            if ser and ser.is_open:
                ser.close()

    def _send_cat(self, ser, cmd: str) -> str:
        ser.write(cmd.encode())
        response = ser.read_until(b";")
        return response.decode(errors="replace")

    def _parse_fa(self, response) -> int:
        if response is None:
            return None
        if not isinstance(response, str) or not response.startswith("FA") or not response.endswith(";"):
            raise ValueError(f"Invalid FA response: {response!r}")
        digits = response[2:-1]
        if not digits.isdigit():
            raise ValueError(f"Non-numeric FA payload: {digits!r}")
        return int(digits)
