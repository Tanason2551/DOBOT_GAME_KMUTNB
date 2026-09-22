#!/usr/bin/env python3
"""
Dobot MG400 / CR Series Driver
Implements TCP/IP Dashboard and Feedback communication for industrial Dobot arms.
"""

import socket
import time
import threading
import re
from typing import Tuple, List, Optional, Dict, Any

from .base_driver import DobotBaseDriver


class DobotMG400Driver(DobotBaseDriver):
    """Driver for Dobot MG400, M1 Pro, and CR series cobots over TCP/IP."""

    def __init__(self):
        super().__init__()
        self._model_name = "Dobot MG400"
        self._ip = "192.168.1.6"
        self._dashboard_port = 29999
        self._feedback_port = 30003
        self._dash_sock = None
        self._lock = threading.RLock()
        self._current_pose = (250.0, 0.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def connect(self, ip: Optional[str] = None, port: int = 29999, **kwargs) -> bool:
        """Connect to Dobot MG400 via TCP socket."""
        if ip:
            self._ip = ip
        self._dashboard_port = port

        with self._lock:
            if self._is_connected:
                self.disconnect()

            try:
                self._dash_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._dash_sock.settimeout(2.0)
                self._dash_sock.connect((self._ip, self._dashboard_port))

                # Enable robot
                self._send_dashboard_cmd("ClearError()")
                self._send_dashboard_cmd("ResetRobot()")
                self._send_dashboard_cmd("EnableRobot()")
                self._send_dashboard_cmd(f"SpeedFactor({int(self._speed_ratio)})")

                self._is_connected = True
                self.get_pose()
                return True
            except Exception:
                self.disconnect()
                return False

    def disconnect(self) -> None:
        """Close TCP sockets."""
        with self._lock:
            self._is_connected = False
            if self._dash_sock:
                try:
                    self._dash_sock.close()
                except Exception:
                    pass
            self._dash_sock = None

    def _send_dashboard_cmd(self, cmd: str) -> str:
        """Send ASCII command to Dashboard port and return response."""
        if not self._dash_sock:
            return ""
        try:
            full_cmd = cmd.strip() + "\r\n"
            self._dash_sock.sendall(full_cmd.encode("utf-8"))
            resp = self._dash_sock.recv(1024).decode("utf-8")
            return resp.strip()
        except Exception:
            return ""

    def get_pose(self) -> Tuple[float, float, float, float, float, float, float, float]:
        """Query GetPose() from Dashboard."""
        if not self._is_connected:
            return self._current_pose

        with self._lock:
            try:
                resp = self._send_dashboard_cmd("GetPose()")
                # Response format typically: 0,{},GetPose();{x,y,z,r} or similar
                match = re.search(r"\{([\d\.\-\s,]+)\}", resp)
                if match:
                    parts = [float(v.strip()) for v in match.group(1).split(",")]
                    if len(parts) >= 4:
                        x, y, z, r = parts[0], parts[1], parts[2], parts[3]
                        # Joint angles query
                        j_resp = self._send_dashboard_cmd("GetAngle()")
                        j_match = re.search(r"\{([\d\.\-\s,]+)\}", j_resp)
                        if j_match:
                            j_parts = [float(v.strip()) for v in j_match.group(1).split(",")]
                            j1 = j_parts[0] if len(j_parts) > 0 else 0.0
                            j2 = j_parts[1] if len(j_parts) > 1 else 0.0
                            j3 = j_parts[2] if len(j_parts) > 2 else 0.0
                            j4 = j_parts[3] if len(j_parts) > 3 else 0.0
                        else:
                            j1 = j2 = j3 = j4 = 0.0
                        self._current_pose = (x, y, z, r, j1, j2, j3, j4)
            except Exception:
                pass
            return self._current_pose

    def move_ptp(self, x: float, y: float, z: float, r: float, 
                 mode: int = DobotBaseDriver.MODE_MOVL, wait: bool = False) -> bool:
        """Send MovL or MovJ command."""
        if not self._is_connected:
            return False

        with self._lock:
            cmd = f"MovL({x:.2f},{y:.2f},{z:.2f},{r:.2f})" if mode == self.MODE_MOVL else f"MovJ({x:.2f},{y:.2f},{z:.2f},{r:.2f})"
            resp = self._send_dashboard_cmd(cmd)
            return "0" in resp

    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        """Jog robot along axis."""
        if not self._is_connected:
            return False

        axis = axis.upper()
        with self._lock:
            if direction == 0:
                return "0" in self._send_dashboard_cmd("StopJog()")
            
            coord_type = "coord" if axis in ["X", "Y", "Z", "R"] else "joint"
            cmd_axis = axis
            sign = "+" if direction > 0 else "-"
            # Command format: MoveJog(axis)
            resp = self._send_dashboard_cmd(f"MoveJog({sign}{cmd_axis})")
            return "0" in resp

    def stop_jog(self) -> bool:
        """Stop jog motion."""
        if not self._is_connected:
            return False
        with self._lock:
            resp = self._send_cmd_direct("StopJog()")
            return True

    def _send_cmd_direct(self, cmd: str) -> str:
        return self._send_dashboard_cmd(cmd)

    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        """Control digital output for suction cup."""
        if not self._is_connected:
            return False
        with self._lock:
            status = 1 if (enable and suck) else 0
            resp = self._send_dashboard_cmd(f"DO(1,{status})")
            self._suction_state = (enable and suck)
            return "0" in resp

    def set_gripper(self, enable: bool, grip: bool) -> bool:
        """Control digital output for gripper."""
        if not self._is_connected:
            return False
        with self._lock:
            status = 1 if (enable and grip) else 0
            resp = self._send_dashboard_cmd(f"DO(2,{status})")
            self._gripper_state = (enable and grip)
            return "0" in resp

    def set_speed(self, velocity_ratio: float, accel_ratio: float) -> bool:
        """Set speed factor."""
        self._speed_ratio = max(1.0, min(100.0, float(velocity_ratio)))
        self._accel_ratio = max(1.0, min(100.0, float(accel_ratio)))
        if not self._is_connected:
            return True
        with self._lock:
            resp = self._send_dashboard_cmd(f"SpeedFactor({int(self._speed_ratio)})")
            return "0" in resp

    def home(self) -> bool:
        """Home robot."""
        if not self._is_connected:
            return False
        with self._lock:
            resp = self._send_dashboard_cmd("MovJ(250, 0, 50, 0)")
            return "0" in resp

    def emergency_stop(self) -> bool:
        """Emergency Stop."""
        if not self._is_connected:
            return False
        with self._lock:
            self._send_dashboard_cmd("EmergencyStop()")
            self._send_dashboard_cmd("DisableRobot()")
            return True

    def clear_alarms(self) -> bool:
        """Clear error."""
        if not self._is_connected:
            return False
        with self._lock:
            self._send_dashboard_cmd("ClearError()")
            self._send_dashboard_cmd("EnableRobot()")
            return True
