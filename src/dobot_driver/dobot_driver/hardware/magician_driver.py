#!/usr/bin/env python3
"""
Dobot Magician / Magician Lite Driver
Implements serial communication protocol v1.1.x for Dobot Magician.
"""

import struct
import time
import threading
from typing import Tuple, List, Optional, Dict, Any
import glob

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from .base_driver import DobotBaseDriver


class DobotMagicianDriver(DobotBaseDriver):
    """Driver for Dobot Magician and Magician Lite arms over USB Serial."""

    # Protocol Commands
    ID_DEVICE_SN = 0
    ID_DEVICE_NAME = 1
    ID_POSE = 10
    ID_ALARMS = 20
    ID_CLEAR_ALARMS = 21
    ID_HOME_CMD = 31
    ID_END_EFFECTOR_SUCTION = 62
    ID_END_EFFECTOR_GRIPPER = 63
    ID_JOG_COMMON_PARAMS = 72
    ID_JOG_CMD = 73
    ID_PTP_COMMON_PARAMS = 83
    ID_PTP_CMD = 84
    ID_CP_CMD = 91
    ID_QUEUED_CMD_START = 240
    ID_QUEUED_CMD_STOP = 242
    ID_QUEUED_CMD_FORCE_STOP = 243
    ID_QUEUED_CMD_CLEAR = 245

    # Jog Command Mapping
    JOG_IDLE = 0
    JOG_XP = 1
    JOG_XN = 2
    JOG_YP = 3
    JOG_YN = 4
    JOG_ZP = 5
    JOG_ZN = 6
    JOG_RP = 7
    JOG_RN = 8

    def __init__(self):
        super().__init__()
        self._model_name = "Dobot Magician"
        self._ser = None
        self._lock = threading.RLock()
        self._current_pose = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._port = None
        self._baudrate = 115200

    @staticmethod
    def scan_ports() -> List[str]:
        """Scan available USB serial ports for Dobot."""
        ports = []
        if SERIAL_AVAILABLE:
            for p in serial.tools.list_ports.comports():
                dev = p.device
                desc = p.description or ""
                # Only keep real USB-to-UART converters, ignore motherboard dummy ttyS* ports
                if "ttyUSB" in dev or "ttyACM" in dev or "USB" in desc or "CP210" in desc or "CH340" in desc or "FTDI" in desc:
                    ports.append(dev)
        if not ports:
            ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        return sorted(list(set(ports)))

    def connect(self, port: Optional[str] = None, baudrate: int = 115200, **kwargs) -> bool:
        """Connect to Dobot Magician via serial."""
        if not SERIAL_AVAILABLE:
            raise RuntimeError("pyserial is not installed. Please run: pip install pyserial")

        with self._lock:
            if self._is_connected:
                self.disconnect()

            if not port:
                available = self.scan_ports()
                if not available:
                    return False
                port = available[0]

            try:
                self._ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                    write_timeout=0.5
                )
                self._port = port
                self._baudrate = baudrate
                time.sleep(0.5)

                # Clear queued commands and start execution queue
                self._send_cmd(self.ID_QUEUED_CMD_CLEAR, 0x01, b"")
                self._send_cmd(self.ID_QUEUED_CMD_START, 0x01, b"")

                # Test reading pose to verify communication
                self._is_connected = True
                pose = self._read_pose_raw()
                if pose is not None:
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
        """Disconnect and close serial port."""
        with self._lock:
            self._is_connected = False
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self._ser = None

    def _calc_checksum(self, payload: bytes) -> int:
        """Calculate Dobot protocol checksum."""
        total = sum(payload) & 0xFF
        return (256 - total) & 0xFF

    def _send_cmd(self, msg_id: int, ctrl: int, params: bytes = b"") -> Optional[bytes]:
        """Package and send protocol message, wait for response."""
        if not self._ser or not self._ser.is_open:
            return None

        length = len(params) + 2
        payload = bytes([msg_id, ctrl]) + params
        checksum = self._calc_checksum(payload)
        packet = bytes([0xAA, 0xAA, length]) + payload + bytes([checksum])

        try:
            self._ser.reset_input_buffer()
            self._ser.write(packet)
            self._ser.flush()

            # Read response header
            header = self._ser.read(2)
            if header != b"\xAA\xAA":
                return None

            resp_len_b = self._ser.read(1)
            if not resp_len_b:
                return None
            resp_len = resp_len_b[0]

            resp_payload = self._ser.read(resp_len)
            resp_checksum_b = self._ser.read(1)
            if not resp_checksum_b:
                return None

            expected_checksum = self._calc_checksum(resp_payload)
            if resp_checksum_b[0] != expected_checksum:
                return None

            return resp_payload
        except Exception:
            return None

    def _read_pose_raw(self) -> Optional[Tuple[float, float, float, float, float, float, float, float]]:
        """Query raw pose from Dobot (returns 8 floats: x, y, z, r, j1..j4)."""
        resp = self._send_cmd(self.ID_POSE, 0x00, b"")
        if resp and len(resp) >= 34:
            # resp[0]=id(10), resp[1]=ctrl, resp[2:34]=8 floats (little endian)
            values = struct.unpack("<8f", resp[2:34])
            return values
        return None

    def get_pose(self) -> Tuple[float, float, float, float, float, float, float, float]:
        """Get latest coordinates and joint angles."""
        if not self._is_connected:
            return self._current_pose

        with self._lock:
            pose = self._read_pose_raw()
            if pose is not None:
                self._current_pose = pose
            return self._current_pose

    def move_ptp(self, x: float, y: float, z: float, r: float, 
                 mode: int = DobotBaseDriver.MODE_MOVL, wait: bool = False,
                 timeout: float = 10.0) -> bool:
        """Send PTP motion command and optionally wait until target coordinates are reached."""
        if not self._is_connected:
            return False

        # Mode: 0=Jump, 1=MovJ, 2=MovL
        # Dobot protocol: 0=JUMP_XYZ, 1=MOVJ_XYZ, 2=MOVL_XYZ
        ptp_mode = mode
        params = struct.pack("<B4f", ptp_mode, float(x), float(y), float(z), float(r))

        with self._lock:
            resp = self._send_cmd(self.ID_PTP_CMD, 0x03, params) # isQueued=1, rw=1 -> 0x03
            if resp is None:
                return False

        if wait:
            return self.wait_until_reached(float(x), float(y), float(z), float(r), timeout=timeout)
        return True

    def jog(self, axis: str, direction: int, step: float = 0.0) -> bool:
        """Jog arm movement."""
        if not self._is_connected:
            return False

        axis = axis.upper()
        jog_cmd = self.JOG_IDLE

        if direction == 0:
            jog_cmd = self.JOG_IDLE
        elif axis == 'X':
            jog_cmd = self.JOG_XP if direction > 0 else self.JOG_XN
        elif axis == 'Y':
            jog_cmd = self.JOG_YP if direction > 0 else self.JOG_YN
        elif axis == 'Z':
            jog_cmd = self.JOG_ZP if direction > 0 else self.JOG_ZN
        elif axis == 'R':
            jog_cmd = self.JOG_RP if direction > 0 else self.JOG_RN

        is_joint = 1 if axis.startswith('J') else 0
        if is_joint:
            # Joint jog
            j_map = {'J1': (1, 2), 'J2': (3, 4), 'J3': (5, 6), 'J4': (7, 8)}
            if axis in j_map:
                jog_cmd = j_map[axis][0] if direction > 0 else j_map[axis][1]

        params = struct.pack("<2B", is_joint, jog_cmd)
        with self._lock:
            resp = self._send_cmd(self.ID_JOG_CMD, 0x01, params)
            return resp is not None

    def stop_jog(self) -> bool:
        """Stop any jog movement."""
        params = struct.pack("<2B", 0, self.JOG_IDLE)
        with self._lock:
            resp = self._send_cmd(self.ID_JOG_CMD, 0x01, params)
            return resp is not None

    def set_suction_cup(self, enable: bool, suck: bool) -> bool:
        """Set suction cup on or off."""
        if not self._is_connected:
            return False
        params = struct.pack("<2B", 1 if enable else 0, 1 if suck else 0)
        with self._lock:
            # Send immediate command (0x01) for instant actuation
            resp = self._send_cmd(self.ID_END_EFFECTOR_SUCTION, 0x01, params)
            # Also queue (0x03) for trajectory execution consistency
            self._send_cmd(self.ID_END_EFFECTOR_SUCTION, 0x03, params)
            if resp is not None:
                self._suction_state = (enable and suck)
                return True
        return False

    def set_gripper(self, enable: bool, grip: bool) -> bool:
        """Set gripper open or closed."""
        if not self._is_connected:
            return False
        params = struct.pack("<2B", 1 if enable else 0, 1 if grip else 0)
        with self._lock:
            resp = self._send_cmd(self.ID_END_EFFECTOR_GRIPPER, 0x01, params)
            self._send_cmd(self.ID_END_EFFECTOR_GRIPPER, 0x03, params)
            if resp is not None:
                self._gripper_state = (enable and grip)
                return True
        return False

    def set_speed(self, velocity_ratio: float, accel_ratio: float) -> bool:
        """Set velocity and acceleration ratio (1.0 to 100.0)."""
        velocity_ratio = max(1.0, min(100.0, float(velocity_ratio)))
        accel_ratio = max(1.0, min(100.0, float(accel_ratio)))
        self._speed_ratio = velocity_ratio
        self._accel_ratio = accel_ratio

        if not self._is_connected:
            return True

        params = struct.pack("<2f", velocity_ratio, accel_ratio)
        with self._lock:
            self._send_cmd(self.ID_PTP_COMMON_PARAMS, 0x01, params)
            self._send_cmd(self.ID_JOG_COMMON_PARAMS, 0x01, params)
            return True

    def home(self) -> bool:
        """Trigger homing calibration."""
        if not self._is_connected:
            return False
        params = struct.pack("<I", 0)
        with self._lock:
            resp = self._send_cmd(self.ID_HOME_CMD, 0x03, params)
            return resp is not None

    def emergency_stop(self) -> bool:
        """Emergency stop: force stop queue and jog."""
        if not self._is_connected:
            return False
        with self._lock:
            self._send_cmd(self.ID_QUEUED_CMD_FORCE_STOP, 0x01, b"")
            self._send_cmd(self.ID_QUEUED_CMD_CLEAR, 0x01, b"")
            self._send_cmd(self.ID_QUEUED_CMD_START, 0x01, b"")
            self.stop_jog()
            return True

    def clear_alarms(self) -> bool:
        """Clear active alarms and reset queued commands."""
        if not self._is_connected:
            return False
        with self._lock:
            self._send_cmd(self.ID_CLEAR_ALARMS, 0x01, b"")
            self._send_cmd(self.ID_QUEUED_CMD_FORCE_STOP, 0x01, b"")
            self._send_cmd(self.ID_QUEUED_CMD_CLEAR, 0x01, b"")
            self._send_cmd(self.ID_QUEUED_CMD_START, 0x01, b"")
            self.stop_jog()
            return True

    def get_alarms(self) -> List[int]:
        """Query active alarms bitmask from Dobot."""
        if not self._is_connected:
            return []
        with self._lock:
            resp = self._send_cmd(self.ID_ALARMS, 0x00, b"")
            if resp and len(resp) >= 2:
                alarm_bytes = resp[2:]
                active = []
                for byte_idx, b in enumerate(alarm_bytes):
                    for bit_idx in range(8):
                        if (b >> bit_idx) & 1:
                            active.append(byte_idx * 8 + bit_idx)
                return active
        return []
