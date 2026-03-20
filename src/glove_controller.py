"""
glove_controller.py
Author: S. Sasmitha

Python serial interface to the Arduino Uno glove controller.
Sends commands that exactly match glove_controller.ino's protocol.

Paper (Section III-D):
  - 5 × MG996R servos actuated via tendon-driven mechanism
  - OPEN  → all servos 0°  (extended fingers)
  - CLOSE → all servos 90° (flexed, peak grip force ~12.4 N)
  - Watchdog resets to OPEN after 2 s of no communication
  - Emergency stop via 'E' command
"""

import threading
import time
from typing import Optional, Tuple

try:
    import serial
    import serial.tools.list_ports
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False

from src.config import GLOVE


class GloveController:
    """
    Sends servo commands over USB serial to the Arduino Uno.

    Usage
    -----
        glove = GloveController()
        glove.set_state("OPEN")    # extends all fingers
        glove.set_state("CLOSED")  # flexes all fingers
        glove.emergency_stop()     # instant open + disables motion
        glove.close()
    """

    def __init__(self, port: Optional[str] = None):
        self._port    = port or self._detect_port()
        self._serial: Optional[serial.Serial] = None
        self._lock    = threading.Lock()
        self._running = False
        self._state   = "OPEN"

        # Cached hand position (set externally when in GLOVE mode)
        self._x = 640
        self._y = 360

        self._connect()
        if self._serial:
            self._start_watchdog()

    # ── Connection ─────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_port() -> Optional[str]:
        if not _SERIAL_OK:
            return None
        for p in serial.tools.list_ports.comports():
            if any(k in p.description.lower()
                   for k in ("arduino", "ch340", "usb serial", "ftdi")):
                return p.device
        return None

    def _connect(self):
        if not _SERIAL_OK or not self._port:
            print("[GloveController] No serial port — glove disabled.")
            return
        try:
            self._serial  = serial.Serial(
                self._port, GLOVE.BAUD, timeout=1
            )
            self._running = True
            time.sleep(GLOVE.INIT_DELAY)   # wait for Arduino reset
            resp = self._serial.readline().decode("utf-8", errors="ignore").strip()
            print(f"[GloveController] Connected {self._port} → {resp}")
        except Exception as e:
            print(f"[GloveController] {e}")
            self._serial = None

    # ── Watchdog ───────────────────────────────────────────────────────────────

    def _start_watchdog(self):
        t = threading.Thread(target=self._watchdog_loop, daemon=True)
        t.start()

    def _watchdog_loop(self):
        """Send a heartbeat every second to keep the Arduino watchdog happy."""
        while self._running:
            time.sleep(1.0)
            self._send("H")

    # ── Serial I/O ─────────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> Optional[str]:
        """Send a command string and return the reply line (thread-safe)."""
        if not self._serial or not self._serial.is_open:
            return None
        try:
            with self._lock:
                self._serial.write(f"{cmd}\n".encode())
                return self._serial.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()
        except Exception as e:
            print(f"[GloveController] send error: {e}")
            return None

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        """
        Map game hand state to servo command.
        OPEN   → 'O'  (0°  — extended)
        CLOSED → 'C'  (90° — flexed, ~12.4 N grip force per paper)
        """
        if state == self._state:
            return
        self._state = state
        self._send("O" if state == "OPEN" else "C")

    def set_angle(self, angle: int):
        """Set all fingers to a specific angle (0–90°)."""
        angle = max(GLOVE.OPEN_DEG, min(GLOVE.CLOSE_DEG, angle))
        self._send(f"S{angle}")

    def set_finger(self, finger: int, angle: int):
        """Set a single finger (0=thumb … 4=pinky) to an angle."""
        angle = max(GLOVE.OPEN_DEG, min(GLOVE.CLOSE_DEG, angle))
        self._send(f"F{finger},{angle}")

    def get_angles(self) -> Optional[list]:
        """Read current servo angles from Arduino."""
        resp = self._send("R")
        if resp and resp.startswith("ANGLES:"):
            try:
                return [int(v) for v in resp[7:].split(",")]
            except ValueError:
                pass
        return None

    def get_hand_state(self) -> Tuple[int, int, str]:
        """Return cached (x, y, state) for use by the game engine."""
        return self._x, self._y, self._state

    def update_position(self, x: int, y: int):
        """Called by game engine to update glove screen position."""
        self._x, self._y = x, y

    def emergency_stop(self):
        """Immediately open all fingers — mirrors Arduino 'E' command."""
        self._running = False
        self._send("E")
        print("[GloveController] EMERGENCY STOP")

    def close(self):
        self._running = False
        self.set_state("OPEN")
        time.sleep(0.1)
        if self._serial and self._serial.is_open:
            self._serial.close()
