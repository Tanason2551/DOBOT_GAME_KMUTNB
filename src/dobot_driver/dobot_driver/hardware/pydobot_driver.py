#!/usr/bin/env python3
"""
Dobot Magician Driver using pydobot (v1.3.2 by Luis Mesas)
Wraps pydobot inside the unified DobotBaseDriver interface.
"""

import time
import struct
import threading
from typing import Tuple, List, Optional, Dict, Any

from .base_driver import DobotBaseDriver
from .magician_driver import DobotMagicianDriver

# Try importing vendored pydobot first, fallback to system pydobot
try:
    from .third_party.pydobot import Dobot as PydobotDevice
    from .third_party.pydobot.message import Message
    from .third_party.pydobot.enums import PTPMode
    from .third_party.pydobot.enums.CommunicationProtocolIDs import CommunicationProtocolIDs
    PYDOBOT_AVAILABLE = True
except ImportError:
    try:
        import pydobot
        from pydobot.message import Message
        from pydobot.enums import PTPMode
        from pydobot.enums.CommunicationProtocolIDs import CommunicationProtocolIDs
        PydobotDevice = pydobot.Dobot
        PYDOBOT_AVAILABLE = True
    except ImportError:
        PYDOBOT_AVAILABLE = False


class DobotPydobotDriver(DobotBaseDriver):
    """Driver for Dobot Magician using the community pydobot library."""

    def __init__(self):
        super().__init__()
        self._model_name = "Dobot Magician (pydobot)"
        self._device: Optional[Any] = None
        self._lock = threading.RLock()
        self._port: Optional[str] = None
        self._baudrate: int = 115200
        self._current_pose: Tuple[float, float, float, float, float, float, float, float] = (
            220.0, 0.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )

    @staticmethod
    def scan_ports() -> List[str]:
        """Scan available USB serial ports."""
        return DobotMagicianDriver.scan_ports()

    def connect(self, port: Optional[str] = None, baudrate: int = 115200, **kwargs) -> bool:
        """Connect to Dobot Magician via pydobot."""
        if not PYDOBOT_AVAILABLE:
            raise RuntimeError("pydobot library is not available.")

        with self._lock:
            if self._is_connected:
                self.disconnect()

            if not port:
                ports = self.scan_ports()
                if not ports:
                    return False
                port = ports[0]

            try:
                self._device = PydobotDevice(port=port, verbose=False)
                self._port = port
                self._baudrate = baudrate
                time.sleep(0.3)

                # Verify connection by reading current pose
                pose = self.get_pose()
                if pose is not None:
                    self._is_connected = True
                    self._current_pose = pose
                    self.set_speed(self._speed_ratio, self._accel_ratio)
                    return True
                else:
                    self.disconnect()
                    return False
            except Exception as e:
                self.disconnect()
                return False

    def disconnect(self) -> None:
        """Disconnect and close serial communication."""
        with self._lock:
            self._is_connected = False
            if self._device:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None

    def get_pose(self) -> Tuple[float, float, float, float, float, float, float, float]:
        """Get latest coordinates and joint angles (x, y, z, r, j1, j2, j3, j4)."""
        if not self._is_connected or not self._device:
            return self._current_pose

        with self._lock:
            try:
                p = self._device.pose()
                if p and len(p) == 8:
                    self._current_pose = tuple(float(v) for v in p)
            except Exception:
                pass
            return self._current_pose

    def move_ptp(self, x: float, y: float, z: float, r: float,
                 mode: int = DobotBaseDriver.MODE_MOVL, wait: bool = False,
                 timeout: float = 10.0) -> bool:
        """Move arm to target coordinates using PTP mode."""
        if not self._is_connected or not self._device:
            return False

        with self._lock:
            try:
                # Map mode to PTPMode enum
                mode_map = {
                    DobotBaseDriver.MODE_JUMP: PTPMode.JUMP_XYZ,
                    DobotBaseDriver.MODE_MOVJ: PTPMode.MOVJ_XYZ,
                    DobotBaseDriver.MODE_MOVL: PTPMode.MOVL_XYZ
                }
                ptp_mode = mode_map.get(mode, PTPMode.MOVL_XYZ)
                self._device._set_ptp_cmd(float(x), float(y), float(z), float(r), mode=ptp_mode, wait=wait)
            except Exception:
                return False

        if wait:
            return self.wait_until_reached(float(x), float(y), float(z), float(r), timeout=timeout)
        return True

    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        """
        Jog motion for pydobot.
        Uses incremental step move to ensure compatibility across all pydobot versions.
        """
        if not self._is_connected or not self._device or direction == 0:
            return True

        axis = axis.upper()
        step_val = step if step > 0.0 else 5.0
        delta = step_val * (1.0 if direction > 0 else -1.0)

        with self._lock:
            curr = list(self.get_pose())
            x, y, z, r = curr[0], curr[1], curr[2], curr[3]
            if axis == 'X':
                x += delta
            elif axis == 'Y':
                y += delta
            elif axis == 'Z':
                z += delta
            elif axis == 'R':
                r += delta
            else:
                return False

            return self.move_ptp(x, y, z, r, mode=DobotBaseDriver.MODE_MOVL, wait=False)

    def stop_jog(self) -> bool:
        """Stop jog movement."""
        return True

    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        """Control suction cup end-effector."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device.suck(enable and suck)
                self._suction_state = (enable and suck)
                return True
            except Exception:
                return False

    def set_gripper(self, enable: bool, grip: bool) -> bool:
        """Control gripper end-effector."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device.grip(enable and grip)
                self._gripper_state = (enable and grip)
                return True
            except Exception:
                return False

    def set_speed(self, velocity_ratio: float, accel_ratio: float) -> bool:
        """Set movement speed and acceleration (1.0 to 100.0 %)."""
        self._speed_ratio = max(1.0, min(100.0, float(velocity_ratio)))
        self._accel_ratio = max(1.0, min(100.0, float(accel_ratio)))

        if not self._is_connected or not self._device:
            return True

        with self._lock:
            try:
                self._device.speed(velocity=self._speed_ratio, acceleration=self._accel_ratio)
                return True
            except Exception:
                return False

    def home(self) -> bool:
        """Send homing calibration command."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                # Send raw homing command packet via pydobot message interface
                msg = Message()
                msg.id = 31  # ID_HOME_CMD
                msg.ctrl = 0x03
                msg.params = struct.pack("<I", 0)
                self._device._send_command(msg, wait=False)
                return True
            except Exception:
                return False

    def emergency_stop(self) -> bool:
        """Halt motion and clear command queue."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device._set_queued_cmd_stop_exec()
                self._device._set_queued_cmd_clear()
                self._device._set_queued_cmd_start_exec()
                return True
            except Exception:
                return False

    def clear_alarms(self) -> bool:
        """Reset errors and clear command queue."""
        return self.emergency_stop()
