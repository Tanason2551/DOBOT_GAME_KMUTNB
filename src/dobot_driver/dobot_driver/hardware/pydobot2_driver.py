#!/usr/bin/env python3
"""
Dobot Magician Driver using pydobot2 (v0.1.0 by Zdenek Materna)
Wraps pydobot2 inside the unified DobotBaseDriver interface.
"""

import time
import struct
import threading
from typing import Tuple, List, Optional, Dict, Any

from .base_driver import DobotBaseDriver
from .magician_driver import DobotMagicianDriver

# Try importing vendored pydobot2 first, fallback to system pydobot2
try:
    from .third_party.pydobot2 import Dobot as Pydobot2Device
    from .third_party.pydobot2.dobot import MODE_PTP
    PYDOBOT2_AVAILABLE = True
except ImportError:
    try:
        import pydobot2
        from pydobot2.dobot import MODE_PTP
        Pydobot2Device = pydobot2.Dobot
        PYDOBOT2_AVAILABLE = True
    except ImportError:
        PYDOBOT2_AVAILABLE = False


class DobotPydobot2Driver(DobotBaseDriver):
    """Driver for Dobot Magician using the pydobot2 library."""

    def __init__(self):
        super().__init__()
        self._model_name = "Dobot Magician (pydobot2)"
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
        """Connect to Dobot Magician via pydobot2."""
        if not PYDOBOT2_AVAILABLE:
            raise RuntimeError("pydobot2 library is not available.")

        with self._lock:
            if self._is_connected:
                self.disconnect()

            if not port:
                ports = self.scan_ports()
                if not ports:
                    return False
                port = ports[0]

            try:
                self._device = Pydobot2Device(port=port)
                self._port = port
                self._baudrate = baudrate
                time.sleep(0.3)

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
                p = self._device.get_pose()
                if p and hasattr(p, "position") and hasattr(p, "joints"):
                    self._current_pose = (
                        float(p.position.x),
                        float(p.position.y),
                        float(p.position.z),
                        float(p.position.r),
                        float(p.joints.j1),
                        float(p.joints.j2),
                        float(p.joints.j3),
                        float(p.joints.j4)
                    )
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
                mode_map = {
                    DobotBaseDriver.MODE_JUMP: MODE_PTP.JUMP_XYZ,
                    DobotBaseDriver.MODE_MOVJ: MODE_PTP.MOVJ_XYZ,
                    DobotBaseDriver.MODE_MOVL: MODE_PTP.MOVL_XYZ
                }
                ptp_mode = mode_map.get(mode, MODE_PTP.MOVL_XYZ)
                self._device.move_to(float(x), float(y), float(z), float(r), mode=ptp_mode)
            except Exception:
                return False

        if wait:
            return self.wait_until_reached(float(x), float(y), float(z), float(r), timeout=timeout)
        return True

    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        """Jog robot along an axis using pydobot2 jog commands."""
        if not self._is_connected or not self._device:
            return False

        axis = axis.upper()
        with self._lock:
            try:
                # pydobot2 supports jog_x, jog_y, jog_z, jog_r with direction (1, -1, 0)
                if axis == 'X':
                    self._device.jog_x(direction)
                elif axis == 'Y':
                    self._device.jog_y(direction)
                elif axis == 'Z':
                    self._device.jog_z(direction)
                elif axis == 'R':
                    self._device.jog_r(direction)
                elif direction == 0:
                    self.stop_jog()
                else:
                    return False
                return True
            except Exception:
                return False

    def stop_jog(self) -> bool:
        """Stop all jog motions."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device._set_jog_command(0)
                return True
            except Exception:
                return False

    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        """Control suction cup."""
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
        """Control gripper."""
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
        """Set speed and acceleration ratio (1.0 to 100.0 %)."""
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
        """Trigger homing calibration."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device.home()
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
                self.stop_jog()
                return True
            except Exception:
                return False

    def clear_alarms(self) -> bool:
        """Clear alarms and reset queue."""
        if not self._is_connected or not self._device:
            return False
        with self._lock:
            try:
                self._device.clear_alarms()
                self.emergency_stop()
                return True
            except Exception:
                return False
