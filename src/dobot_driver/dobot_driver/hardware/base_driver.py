#!/usr/bin/env python3
"""
Base Driver Interface for Dobot Robotic Arms
Provides an abstract base class that all Dobot model drivers implement.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List


class DobotBaseDriver(ABC):
    """Abstract Base Class defining the unified API for Dobot robotic arms."""

    MODE_JUMP = 0
    MODE_MOVJ = 1
    MODE_MOVL = 2

    def __init__(self):
        self._is_connected = False
        self._model_name = "Unknown"
        self._speed_ratio = 50.0
        self._accel_ratio = 50.0
        self._suction_state = False
        self._gripper_state = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def model_name(self) -> str:
        return self._model_name

    @abstractmethod
    def connect(self, port: Optional[str] = None, baudrate: int = 115200, 
                ip: Optional[str] = None, **kwargs) -> bool:
        """Connect to the Dobot hardware or simulated environment."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the Dobot arm."""
        pass

    @abstractmethod
    def get_pose(self) -> Tuple[float, float, float, float, float, float, float, float]:
        """
        Returns current coordinates and joint angles:
        (x, y, z, r, j1, j2, j3, j4)
        """
        pass

    @abstractmethod
    def move_ptp(self, x: float, y: float, z: float, r: float, 
                 mode: int = MODE_MOVL, wait: bool = False) -> bool:
        """
        Move robot to Cartesian coordinates (x, y, z, r).
        mode: MODE_JUMP, MODE_MOVJ, MODE_MOVL
        """
        pass

    def wait_until_reached(self, target_x: float, target_y: float, target_z: float, 
                           target_r: Optional[float] = None, timeout: float = 8.0, 
                           tol_pos: float = 2.0, tol_r: float = 4.0) -> bool:
        """
        Wait until the arm physically reaches the target Cartesian position.
        Polls get_pose() until Euclidean distance is within tolerance,
        or movement has settled at the target.
        """
        start_time = time.time()
        settled_count = 0
        last_dist = 999999.0

        # Wait at least a tiny bit for the command to register and motion to begin
        time.sleep(0.12)

        while time.time() - start_time < timeout:
            if not self._is_connected:
                return False

            curr = self.get_pose()
            if curr is None or len(curr) < 4:
                time.sleep(0.04)
                continue

            curr_x, curr_y, curr_z, curr_r = curr[0:4]
            dx = curr_x - target_x
            dy = curr_y - target_y
            dz = curr_z - target_z
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5

            dr = abs(curr_r - target_r) if target_r is not None else 0.0
            if dr > 180.0:
                dr = 360.0 - dr

            # Condition 1: Position within tolerance
            if dist <= tol_pos and dr <= tol_r:
                return True

            # Condition 2: Motion has settled (stopped moving) very close to target
            if abs(dist - last_dist) < 0.15:
                settled_count += 1
                if settled_count >= 6 and dist <= (tol_pos * 2.5):
                    return True
            else:
                settled_count = 0

            last_dist = dist
            time.sleep(0.04)

        return False

    @abstractmethod
    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        """
        Jog robot along an axis ('X', 'Y', 'Z', 'R', 'J1', 'J2', 'J3', 'J4').
        direction: 1 (positive), -1 (negative), 0 (stop)
        step: 0.0 for continuous, >0 for incremental distance
        """
        pass

    @abstractmethod
    def stop_jog(self) -> bool:
        """Stop any active jog motion."""
        pass

    @abstractmethod
    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        """Control suction cup end-effector."""
        pass

    @abstractmethod
    def set_gripper(self, enable: bool, grip: bool) -> bool:
        """Control gripper end-effector."""
        pass

    @abstractmethod
    def set_speed(self, velocity_ratio: float, accel_ratio: float) -> bool:
        """Set movement speed and acceleration ratio (1.0 to 100.0 %)."""
        pass

    @abstractmethod
    def home(self) -> bool:
        """Initiate homing calibration sequence."""
        pass

    @abstractmethod
    def emergency_stop(self) -> bool:
        """Immediately halt arm movement."""
        pass

    @abstractmethod
    def clear_alarms(self) -> bool:
        """Clear active alarm / error states."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return a dictionary of the current driver status."""
        try:
            x, y, z, r, j1, j2, j3, j4 = self.get_pose()
        except Exception:
            x = y = z = r = j1 = j2 = j3 = j4 = 0.0

        return {
            "is_connected": self._is_connected,
            "model_name": self._model_name,
            "suction_state": self._suction_state,
            "gripper_state": self._gripper_state,
            "speed_ratio": self._speed_ratio,
            "accel_ratio": self._accel_ratio,
            "pose": {"x": x, "y": y, "z": z, "r": r},
            "joints": {"j1": j1, "j2": j2, "j3": j3, "j4": j4},
            "alarms": []
        }
