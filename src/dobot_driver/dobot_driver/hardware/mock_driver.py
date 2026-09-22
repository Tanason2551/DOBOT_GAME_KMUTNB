#!/usr/bin/env python3
"""
Dobot Mock Simulation Driver
Provides realistic kinematics, state simulation, and smooth interpolation
allowing complete UI and ROS 2 testing without physical hardware.
"""

import math
import time
import threading
from typing import Tuple, List, Optional, Dict, Any

from .base_driver import DobotBaseDriver


class DobotMockDriver(DobotBaseDriver):
    """Simulated Dobot arm for testing, UI validation, and development."""

    def __init__(self):
        super().__init__()
        self._model_name = "Dobot Simulation (Mock)"
        self._lock = threading.RLock()

        # Simulated state: x, y, z, r, j1, j2, j3, j4
        self._x = 220.0
        self._y = 0.0
        self._z = 50.0
        self._r = 0.0

        # Target coordinates for interpolation
        self._target_x = 220.0
        self._target_y = 0.0
        self._target_z = 50.0
        self._target_r = 0.0

        # Active jog motion: (axis, direction)
        self._active_jog = None

        # Background simulation thread
        self._running = False
        self._sim_thread = None

    def connect(self, **kwargs) -> bool:
        """Start simulated connection."""
        with self._lock:
            self._is_connected = True
            self._running = True
            if self._sim_thread is None or not self._sim_thread.is_alive():
                self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
                self._sim_thread.start()
            return True

    def disconnect(self) -> None:
        """Stop simulation."""
        with self._lock:
            self._is_connected = False
            self._running = False
            self._active_jog = None

    def _simulation_loop(self):
        """Continuously smoothly interpolate towards target or handle jog."""
        dt = 0.05
        while self._running:
            with self._lock:
                speed_factor = (self._speed_ratio / 100.0) * 150.0 # mm per second max

                # Handle Jog
                if self._active_jog:
                    axis, direction = self._active_jog
                    delta = direction * speed_factor * dt
                    if axis == 'X':
                        self._target_x = max(100.0, min(330.0, self._target_x + delta))
                    elif axis == 'Y':
                        self._target_y = max(-220.0, min(220.0, self._target_y + delta))
                    elif axis == 'Z':
                        self._target_z = max(-50.0, min(150.0, self._target_z + delta))
                    elif axis == 'R':
                        self._target_r = max(-135.0, min(135.0, self._target_r + delta))

                # Smooth interpolation toward target
                dx = self._target_x - self._x
                dy = self._target_y - self._y
                dz = self._target_z - self._z
                dr = self._target_r - self._r

                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                max_step = speed_factor * dt

                if dist > 0.1:
                    ratio = min(1.0, max_step / dist)
                    self._x += dx * ratio
                    self._y += dy * ratio
                    self._z += dz * ratio
                else:
                    self._x = self._target_x
                    self._y = self._target_y
                    self._z = self._target_z

                if abs(dr) > 0.1:
                    r_step = min(abs(dr), 180.0 * (self._speed_ratio / 100.0) * dt)
                    self._r += math.copysign(r_step, dr)
                else:
                    self._r = self._target_r

            time.sleep(dt)

    def _compute_joints(self) -> Tuple[float, float, float, float]:
        """Simple inverse kinematics approximation for Dobot Magician."""
        x, y, z, r = self._x, self._y, self._z, self._r
        # J1 is base angle in degrees
        j1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0.0

        # Reach distance in XY plane
        reach = math.sqrt(x * x + y * y)
        l1 = 135.0  # upper arm length
        l2 = 147.0  # forearm length

        # Approximate 2-link planar IK for J2 and J3
        d = math.sqrt(reach * reach + z * z)
        d = min(l1 + l2 - 1.0, max(abs(l1 - l2) + 1.0, d))
        alpha = math.atan2(z, reach)
        cos_beta = (l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)

        j2 = math.degrees(alpha + beta)
        cos_gamma = (l1 * l1 + l2 * l2 - d * d) / (2.0 * l1 * l2)
        cos_gamma = max(-1.0, min(1.0, cos_gamma))
        j3 = math.degrees(math.acos(cos_gamma)) - 90.0
        j4 = r - j1

        return (j1, j2, j3, j4)

    def get_pose(self) -> Tuple[float, float, float, float, float, float, float, float]:
        with self._lock:
            j1, j2, j3, j4 = self._compute_joints()
            return (self._x, self._y, self._z, self._r, j1, j2, j3, j4)

    def move_ptp(self, x: float, y: float, z: float, r: float, 
                 mode: int = DobotBaseDriver.MODE_MOVL, wait: bool = False) -> bool:
        with self._lock:
            self._active_jog = None
            # Workspace boundaries check
            self._target_x = max(100.0, min(330.0, float(x)))
            self._target_y = max(-220.0, min(220.0, float(y)))
            self._target_z = max(-50.0, min(150.0, float(z)))
            self._target_r = max(-135.0, min(135.0, float(r)))

        if wait:
            # Wait until close
            for _ in range(50):
                time.sleep(0.1)
                with self._lock:
                    if (abs(self._x - self._target_x) < 1.0 and 
                        abs(self._y - self._target_y) < 1.0 and 
                        abs(self._z - self._target_z) < 1.0):
                        break
        return True

    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        axis = axis.upper()
        with self._lock:
            if direction == 0:
                self._active_jog = None
            elif step > 0.0:
                # Discrete step
                delta = direction * step
                if axis == 'X':
                    self._target_x = max(100.0, min(330.0, self._target_x + delta))
                elif axis == 'Y':
                    self._target_y = max(-220.0, min(220.0, self._target_y + delta))
                elif axis == 'Z':
                    self._target_z = max(-50.0, min(150.0, self._target_z + delta))
                elif axis == 'R':
                    self._target_r = max(-135.0, min(135.0, self._target_r + delta))
            else:
                # Continuous jog
                self._active_jog = (axis, direction)
        return True

    def stop_jog(self) -> bool:
        with self._lock:
            self._active_jog = None
        return True

    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        with self._lock:
            self._suction_state = (enable and suck)
            if self._suction_state:
                self._gripper_state = False
        return True

    def set_gripper(self, enable: bool, grip: bool) -> bool:
        with self._lock:
            self._gripper_state = (enable and grip)
            if self._gripper_state:
                self._suction_state = False
        return True

    def set_speed(self, velocity_ratio: float, accel_ratio: float) -> bool:
        with self._lock:
            self._speed_ratio = max(1.0, min(100.0, float(velocity_ratio)))
            self._accel_ratio = max(1.0, min(100.0, float(accel_ratio)))
        return True

    def home(self) -> bool:
        with self._lock:
            self._target_x = 220.0
            self._target_y = 0.0
            self._target_z = 50.0
            self._target_r = 0.0
        return True

    def emergency_stop(self) -> bool:
        with self._lock:
            self._active_jog = None
            self._target_x = self._x
            self._target_y = self._y
            self._target_z = self._z
            self._target_r = self._r
        return True

    def clear_alarms(self) -> bool:
        return True
