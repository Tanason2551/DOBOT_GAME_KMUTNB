#!/usr/bin/env python3
"""
ROS 2 & Hardware Bridge Worker Thread
Runs ROS 2 spin or direct driver polling in a background QThread,
with Connection Watchdog for heartbeat, latency (Ping ms), and auto-reconnect.
"""

import sys
import json
import time
import math
from typing import Optional, Dict, Any

from .qt_compat import QThread, Signal

# Optional ROS 2 imports
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from geometry_msgs.msg import PoseStamped, Pose, Twist
    from std_msgs.msg import String
    from std_srvs.srv import Trigger, SetBool
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

# Import hardware drivers and watchdog
from dobot_driver.hardware import create_driver, DobotBaseDriver, DobotMagicianDriver
from dobot_driver.hardware.connection_watchdog import ConnectionWatchdog


class RosBridgeWorker(QThread):
    """Worker QThread handling ROS 2 communications, hardware interface, and connection health."""

    # Qt Signals
    sig_pose_updated = Signal(float, float, float, float, float, float, float, float)
    sig_status_updated = Signal(dict)
    sig_log = Signal(str, str)
    sig_connection_changed = Signal(bool, str)
    sig_connection_health = Signal(bool, str, float, float)  # is_connected, model_name, latency_ms, rate_hz

    def __init__(self):
        super().__init__()
        self._running = True
        self._use_ros2 = ROS2_AVAILABLE
        self._node = None
        self._driver: Optional[DobotBaseDriver] = None
        self._watchdog: Optional[ConnectionWatchdog] = None
        self._is_connected = False
        self._active_model_name = "Not Connected"

        # Cached states
        self._current_pose = (220.0, 0.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def run(self):
        """Worker thread main loop."""
        self.sig_log.emit("INFO", f"Worker thread started. ROS2 available: {ROS2_AVAILABLE}")

        if self._use_ros2:
            try:
                if not rclpy.ok():
                    rclpy.init()
                self._node = Node("dobot_gui_node")
                self._setup_ros2_subscribers()
                self.sig_log.emit("INFO", "ROS 2 node 'dobot_gui_node' initialized.")
            except Exception as e:
                self.sig_log.emit("WARN", f"ROS 2 init failed ({e}), falling back to direct mode.")
                self._use_ros2 = False

        # Polling loop
        last_health_emit = 0.0
        while self._running:
            now = time.time()
            if self._use_ros2 and self._node:
                try:
                    rclpy.spin_once(self._node, timeout_sec=0.02)
                except Exception:
                    pass

            if self._driver and self._is_connected:
                # Direct driver polling
                try:
                    pose = self._driver.get_pose()
                    if pose and len(pose) == 8:
                        self._current_pose = pose
                        self.sig_pose_updated.emit(*pose)
                    status = self._driver.get_status()
                    self.sig_status_updated.emit(status)
                except Exception as e:
                    self.sig_log.emit("ERROR", f"Driver polling error: {e}")
                time.sleep(0.04)
            else:
                time.sleep(0.05)

            # Emit health diagnostics periodically (every 0.5s)
            if now - last_health_emit >= 0.5:
                last_health_emit = now
                if self._watchdog:
                    health = self._watchdog.get_health_status()
                    self.sig_connection_health.emit(
                        health["is_connected"],
                        self._active_model_name,
                        health["latency_ms"],
                        health["actual_rate_hz"]
                    )
                else:
                    self.sig_connection_health.emit(
                        self._is_connected,
                        self._active_model_name,
                        5.0 if self._is_connected else 0.0,
                        25.0 if self._is_connected else 0.0
                    )

    def _setup_ros2_subscribers(self):
        """Set up ROS 2 topics and service clients."""
        if not self._node:
            return

        self._node.create_subscription(
            String, "/dobot/status_json", self._on_status_json, 10
        )
        self._node.create_subscription(
            JointState, "/dobot/joint_states", lambda msg: None, 10
        )
        self._node.create_subscription(
            PoseStamped, "/dobot/pose", lambda msg: None, 10
        )

        # Service clients
        self._cli_home = self._node.create_client(Trigger, "/dobot/home")
        self._cli_estop = self._node.create_client(Trigger, "/dobot/emergency_stop")
        self._cli_clear_alarms = self._node.create_client(Trigger, "/dobot/clear_alarms")
        self._cli_suction = self._node.create_client(SetBool, "/dobot/set_suction_cup")
        self._cli_gripper = self._node.create_client(SetBool, "/dobot/set_gripper")
        self._pub_target_pose = self._node.create_publisher(Pose, "/dobot/target_pose", 10)
        self._pub_cmd_jog = self._node.create_publisher(Twist, "/dobot/cmd_jog", 10)

    def _on_status_json(self, msg: String):
        """Handle JSON status update from ROS 2."""
        try:
            data = json.loads(msg.data)
            self._is_connected = data.get("is_connected", False)
            self._active_model_name = data.get("model_name", "Unknown")

            # If receiving updates from external ROS 2 node, release local mock driver
            if self._driver and getattr(self._driver, "model_name", "") == "Dobot Simulation (Mock)":
                self._driver.disconnect()
                self._driver = None

            self.sig_connection_changed.emit(self._is_connected, self._active_model_name)
            self.sig_status_updated.emit(data)

            p = data.get("pose", {})
            j = data.get("joints", {})
            x = p.get("x", 220.0)
            y = p.get("y", 0.0)
            z = p.get("z", 50.0)
            r = p.get("r", 0.0)
            j1 = j.get("j1", 0.0)
            j2 = j.get("j2", 0.0)
            j3 = j.get("j3", 0.0)
            j4 = j.get("j4", 0.0)
            self._current_pose = (x, y, z, r, j1, j2, j3, j4)
            self.sig_pose_updated.emit(x, y, z, r, j1, j2, j3, j4)
        except Exception as e:
            self.sig_log.emit("ERROR", f"Error parsing status JSON: {e}")

    # Connection Control
    def connect_hardware(self, model_type: str, port: str = "", ip: str = "192.168.1.6", baudrate: int = 115200):
        """Connect to hardware either directly or via ROS 2 driver node."""
        self.sig_log.emit("INFO", f"Connecting to model '{model_type}' on port '{port}' / IP '{ip}'...")
        try:
            if self._watchdog:
                self._watchdog.stop()

            self._driver = create_driver(model_type)
            success = self._driver.connect(port=port or None, baudrate=baudrate, ip=ip)
            if success:
                self._is_connected = True
                self._active_model_name = self._driver.model_name
                self.sig_connection_changed.emit(True, self._active_model_name)
                self.sig_log.emit("INFO", f"Successfully connected to {self._active_model_name}")

                # Start Watchdog
                self._watchdog = ConnectionWatchdog(self._driver, timeout_sec=1.2, ping_rate_hz=10.0)
                self._watchdog.add_timeout_callback(self._on_watchdog_timeout)
                self._watchdog.start()
            else:
                self._is_connected = False
                self.sig_connection_changed.emit(False, "Connection Failed")
                self.sig_log.emit("ERROR", f"Connection failed to {model_type}.")
        except Exception as e:
            self._is_connected = False
            self.sig_connection_changed.emit(False, str(e))
            self.sig_log.emit("ERROR", f"Connection exception: {e}")

    def reconnect_hardware(self):
        """Trigger re-connection to active driver."""
        if self._driver:
            self.sig_log.emit("INFO", "Re-connecting to robot...")
            if hasattr(self._driver, "_port") and self._driver._port:
                self.connect_hardware(self._driver.model_name, port=self._driver._port)
            else:
                self.connect_hardware("auto")

    def disconnect_hardware(self):
        """Disconnect active connection."""
        if self._watchdog:
            self._watchdog.stop()
            self._watchdog = None
        if self._driver:
            self._driver.disconnect()
        self._is_connected = False
        self.sig_connection_changed.emit(False, "Disconnected")
        self.sig_log.emit("INFO", "Disconnected from robot.")

    def _on_watchdog_timeout(self):
        """Watchdog detected lost communication."""
        self.sig_log.emit("WARN", "⚠️ WATCHDOG TIMEOUT: Communication with Dobot lost!")
        self.emergency_stop()

    # Arm Actions
    def send_ptp(self, x: float, y: float, z: float, r: float, mode: int = 2):
        """Move arm to Cartesian target."""
        if self._driver and self._is_connected:
            self._driver.move_ptp(x, y, z, r, mode=mode)
        elif self._use_ros2 and self._pub_target_pose:
            p = Pose()
            p.position.x = x / 1000.0
            p.position.y = y / 1000.0
            p.position.z = z / 1000.0
            half_yaw = math.radians(r) * 0.5
            p.orientation.z = math.sin(half_yaw)
            p.orientation.w = math.cos(half_yaw)
            self._pub_target_pose.publish(p)

    def send_jog(self, axis: str, direction: int, step: float = 0.0):
        """Jog arm."""
        if self._driver and self._is_connected:
            self._driver.jog(axis, direction, step)
        elif self._use_ros2 and self._pub_cmd_jog:
            tw = Twist()
            val = float(direction)
            if axis == 'X': tw.linear.x = val
            elif axis == 'Y': tw.linear.y = val
            elif axis == 'Z': tw.linear.z = val
            elif axis == 'R': tw.angular.z = val
            self._pub_cmd_jog.publish(tw)

    def stop_jog(self):
        """Stop jog."""
        if self._driver and self._is_connected:
            self._driver.stop_jog()
        elif self._use_ros2 and self._pub_cmd_jog:
            self._pub_cmd_jog.publish(Twist())

    def set_suction_cup(self, state: bool):
        """Toggle suction cup."""
        if self._driver and self._is_connected:
            self._driver.set_suction_cup(bool(state), bool(state))
            self.sig_log.emit("CMD", f"Suction Cup: {'ON' if state else 'OFF'}")
        elif self._use_ros2 and self._cli_suction and self._cli_suction.service_is_ready():
            req = SetBool.Request()
            req.data = state
            self._cli_suction.call_async(req)

    def set_gripper(self, state: bool):
        """Toggle gripper."""
        if self._driver and self._is_connected:
            self._driver.set_gripper(True, state)
            self.sig_log.emit("CMD", f"Gripper: {'GRIP' if state else 'RELEASE'}")
        elif self._use_ros2 and self._cli_gripper and self._cli_gripper.service_is_ready():
            req = SetBool.Request()
            req.data = state
            self._cli_gripper.call_async(req)

    def set_speed(self, vel_ratio: float, acc_ratio: float):
        """Set speed and acceleration."""
        if self._driver:
            self._driver.set_speed(vel_ratio, acc_ratio)
            self.sig_log.emit("INFO", f"Speed set to {vel_ratio:.0f}%")

    def home(self):
        """Home robot."""
        if self._driver and self._is_connected:
            self._driver.home()
            self.sig_log.emit("CMD", "Home command initiated.")
        elif self._use_ros2 and self._cli_home and self._cli_home.service_is_ready():
            self._cli_home.call_async(Trigger.Request())

    def emergency_stop(self):
        """Emergency stop immediately."""
        if self._driver:
            self._driver.emergency_stop()
        if self._use_ros2 and self._cli_estop and self._cli_estop.service_is_ready():
            self._cli_estop.call_async(Trigger.Request())
        self.sig_log.emit("WARN", "🛑 EMERGENCY STOP TRIGGERED!")

    def clear_alarms(self):
        """Clear error alarms."""
        if self._driver and self._is_connected:
            self._driver.clear_alarms()
        elif self._use_ros2 and self._cli_clear_alarms and self._cli_clear_alarms.service_is_ready():
            self._cli_clear_alarms.call_async(Trigger.Request())
        self.sig_log.emit("INFO", "Clear alarms requested.")

    def stop(self):
        """Stop worker thread."""
        self._running = False
        if self._watchdog:
            self._watchdog.stop()
        if self._driver:
            self._driver.disconnect()
        if self._node:
            try:
                self._node.destroy_node()
            except Exception:
                pass
        self.wait(1000)
