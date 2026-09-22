#!/usr/bin/env python3
"""
Dobot ROS 2 Driver Node
Publishes joint states, pose, and status.
Exposes services for PTP motion, Jogging, End-effectors, Speed, and Homing.
"""

import sys
import json
import math
import time

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from geometry_msgs.msg import PoseStamped, Pose, Twist
    from std_msgs.msg import String, Header
    from std_srvs.srv import Trigger, SetBool
    RCLPY_AVAILABLE = True
except ImportError:
    RCLPY_AVAILABLE = False

# Try importing custom dobot_msgs
try:
    from dobot_msgs.msg import DobotPose, DobotStatus
    from dobot_msgs.srv import SetPTP, SetEndEffector, SetSpeed, SetJog
    DOBOT_MSGS_AVAILABLE = True
except ImportError:
    DOBOT_MSGS_AVAILABLE = False

from .hardware import create_driver, DobotBaseDriver, DobotMagicianDriver


class DobotDriverNode(Node if RCLPY_AVAILABLE else object):
    """ROS 2 Node interfacing Dobot robotic arms."""

    def __init__(self):
        if not RCLPY_AVAILABLE:
            raise RuntimeError("rclpy is not available. Please source your ROS 2 environment.")

        super().__init__("dobot_driver_node")

        # Declare parameters
        self.declare_parameter("model_type", "auto")
        self.declare_parameter("port", "")
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("ip", "192.168.1.6")
        self.declare_parameter("publish_rate", 20.0)

        model_type = self.get_parameter("model_type").value
        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        ip = self.get_parameter("ip").value
        publish_rate = float(self.get_parameter("publish_rate").value)

        self.get_logger().info(f"Initializing Dobot driver (Model: {model_type}, Port: '{port}', IP: '{ip}')")

        # Initialize hardware driver
        self.driver = create_driver(model_type)
        connected = self.driver.connect(port=port or None, baudrate=baudrate, ip=ip)
        if connected:
            self.get_logger().info(f"Connected successfully to {self.driver.model_name}")
        else:
            self.get_logger().warn(f"Could not connect to physical hardware. Falling back to simulation mode.")
            from .hardware.mock_driver import DobotMockDriver
            self.driver = DobotMockDriver()
            self.driver.connect()

        # Publishers
        self.joint_pub = self.create_publisher(JointState, "/dobot/joint_states", 10)
        self.pose_pub = self.create_publisher(PoseStamped, "/dobot/pose", 10)
        self.status_json_pub = self.create_publisher(String, "/dobot/status_json", 10)

        if DOBOT_MSGS_AVAILABLE:
            self.dobot_pose_pub = self.create_publisher(DobotPose, "/dobot/dobot_pose", 10)
            self.dobot_status_pub = self.create_publisher(DobotStatus, "/dobot/dobot_status", 10)

        # Standard Services
        self.srv_home = self.create_service(Trigger, "/dobot/home", self.handle_home)
        self.srv_estop = self.create_service(Trigger, "/dobot/emergency_stop", self.handle_emergency_stop)
        self.srv_clear_alarms = self.create_service(Trigger, "/dobot/clear_alarms", self.handle_clear_alarms)
        self.srv_suction = self.create_service(SetBool, "/dobot/set_suction_cup", self.handle_suction_cup)
        self.srv_gripper = self.create_service(SetBool, "/dobot/set_gripper", self.handle_gripper)

        # Custom Services (if compiled)
        if DOBOT_MSGS_AVAILABLE:
            self.srv_ptp = self.create_service(SetPTP, "/dobot/set_ptp", self.handle_set_ptp)
            self.srv_end_effector = self.create_service(SetEndEffector, "/dobot/set_end_effector", self.handle_set_end_effector)
            self.srv_speed = self.create_service(SetSpeed, "/dobot/set_speed", self.handle_set_speed)
            self.srv_jog = self.create_service(SetJog, "/dobot/set_jog", self.handle_set_jog)

        # Subscribers
        self.sub_target_pose = self.create_subscription(
            Pose, "/dobot/target_pose", self.handle_target_pose, 10
        )
        self.sub_cmd_jog = self.create_subscription(
            Twist, "/dobot/cmd_jog", self.handle_cmd_jog, 10
        )

        # Timer for state feedback
        timer_period = 1.0 / max(1.0, publish_rate)
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.get_logger().info("Dobot Driver Node ready and publishing state.")

    def timer_callback(self):
        """Periodic state publishing loop."""
        try:
            x, y, z, r, j1, j2, j3, j4 = self.driver.get_pose()
        except Exception as e:
            self.get_logger().error(f"Error querying pose: {e}")
            return

        now = self.get_clock().now().to_msg()

        # 1. Publish JointState (angles in radians)
        js = JointState()
        js.header.stamp = now
        js.header.frame_id = "dobot_base_link"
        js.name = ["dobot_joint1", "dobot_joint2", "dobot_joint3", "dobot_joint4"]
        js.position = [
            math.radians(j1),
            math.radians(j2),
            math.radians(j3),
            math.radians(j4)
        ]
        self.joint_pub.publish(js)

        # 2. Publish PoseStamped (meters & orientation quaternion)
        ps = PoseStamped()
        ps.header.stamp = now
        ps.header.frame_id = "dobot_base_link"
        # Convert mm to meters
        ps.pose.position.x = x / 1000.0
        ps.pose.position.y = y / 1000.0
        ps.pose.position.z = z / 1000.0
        
        # Yaw rotation (r in degrees to quaternion)
        half_yaw = math.radians(r) * 0.5
        ps.pose.orientation.z = math.sin(half_yaw)
        ps.pose.orientation.w = math.cos(half_yaw)
        self.pose_pub.publish(ps)

        # 3. Publish JSON Status
        status_data = self.driver.get_status()
        status_str = json.dumps(status_data)
        str_msg = String()
        str_msg.data = status_str
        self.status_json_pub.publish(str_msg)

        # 4. Publish DobotPose & DobotStatus if custom msgs are active
        if DOBOT_MSGS_AVAILABLE:
            dp = DobotPose()
            dp.x, dp.y, dp.z, dp.r = float(x), float(y), float(z), float(r)
            dp.j1, dp.j2, dp.j3, dp.j4 = float(j1), float(j2), float(j3), float(j4)
            self.dobot_pose_pub.publish(dp)

            ds = DobotStatus()
            ds.is_connected = self.driver.is_connected
            ds.model_name = self.driver.model_name
            ds.suction_cup_state = status_data.get("suction_state", False)
            ds.gripper_state = status_data.get("gripper_state", False)
            ds.speed_ratio = float(status_data.get("speed_ratio", 50.0))
            self.dobot_status_pub.publish(ds)

    # Service Handlers
    def handle_home(self, request, response):
        success = self.driver.home()
        response.success = success
        response.message = "Homing sequence initiated." if success else "Failed to start homing."
        return response

    def handle_emergency_stop(self, request, response):
        success = self.driver.emergency_stop()
        response.success = success
        response.message = "Emergency Stop triggered." if success else "Failed to trigger E-Stop."
        return response

    def handle_clear_alarms(self, request, response):
        success = self.driver.clear_alarms()
        response.success = success
        response.message = "Alarms cleared." if success else "Failed to clear alarms."
        return response

    def handle_suction_cup(self, request, response):
        success = self.driver.set_suction_cup(True, request.data)
        response.success = success
        response.message = f"Suction cup set to {request.data}"
        return response

    def handle_gripper(self, request, response):
        success = self.driver.set_gripper(True, request.data)
        response.success = success
        response.message = f"Gripper set to {request.data}"
        return response

    def handle_set_ptp(self, request, response):
        success = self.driver.move_ptp(request.x, request.y, request.z, request.r, mode=request.mode)
        response.success = success
        response.message = "Move command sent." if success else "Move command rejected."
        return response

    def handle_set_end_effector(self, request, response):
        if request.effector_type == 0:  # Suction
            success = self.driver.set_suction_cup(request.enable, request.state)
        else:  # Gripper
            success = self.driver.set_gripper(request.enable, request.state)
        response.success = success
        response.message = "End-effector updated."
        return response

    def handle_set_speed(self, request, response):
        success = self.driver.set_speed(request.velocity_ratio, request.acceleration_ratio)
        response.success = success
        response.message = f"Speed set: Vel={request.velocity_ratio}%, Acc={request.acceleration_ratio}%"
        return response

    def handle_set_jog(self, request, response):
        success = self.driver.jog(request.axis, request.direction, request.step)
        response.success = success
        response.message = f"Jog {request.axis} dir={request.direction}"
        return response

    def handle_target_pose(self, msg: Pose):
        # Convert meters to mm
        x = msg.position.x * 1000.0
        y = msg.position.y * 1000.0
        z = msg.position.z * 1000.0
        # Approximate yaw
        r = 2.0 * math.degrees(math.atan2(msg.orientation.z, msg.orientation.w))
        self.driver.move_ptp(x, y, z, r, mode=DobotBaseDriver.MODE_MOVL)

    def handle_cmd_jog(self, msg: Twist):
        # Twist.linear.x, y, z -> Jog X, Y, Z
        if abs(msg.linear.x) > 0.1:
            self.driver.jog("X", 1 if msg.linear.x > 0 else -1)
        elif abs(msg.linear.y) > 0.1:
            self.driver.jog("Y", 1 if msg.linear.y > 0 else -1)
        elif abs(msg.linear.z) > 0.1:
            self.driver.jog("Z", 1 if msg.linear.z > 0 else -1)
        elif abs(msg.angular.z) > 0.1:
            self.driver.jog("R", 1 if msg.angular.z > 0 else -1)
        else:
            self.driver.stop_jog()


def main(args=None):
    if not RCLPY_AVAILABLE:
        print("Error: ROS 2 rclpy is required to run dobot_driver_node.", file=sys.stderr)
        sys.exit(1)

    rclpy.init(args=args)
    node = DobotDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.driver.disconnect()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
