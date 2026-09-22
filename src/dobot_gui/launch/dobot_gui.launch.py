#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    launch_driver_arg = DeclareLaunchArgument(
        "launch_driver", default_value="true",
        description="Whether to also launch the ROS 2 dobot_driver_node"
    )

    model_arg = DeclareLaunchArgument(
        "model_type", default_value="auto",
        description="Dobot model ('magician', 'mg400', 'mock', 'auto')"
    )

    port_arg = DeclareLaunchArgument(
        "port", default_value="",
        description="Serial port (e.g. /dev/ttyUSB0)"
    )

    driver_node = Node(
        package="dobot_driver",
        executable="dobot_node",
        name="dobot_driver_node",
        parameters=[{
            "model_type": LaunchConfiguration("model_type"),
            "port": LaunchConfiguration("port")
        }],
        condition=IfCondition(LaunchConfiguration("launch_driver")),
        output="screen"
    )

    gui_node = Node(
        package="dobot_gui",
        executable="dobot_gui_node",
        name="dobot_gui_node",
        output="screen"
    )

    return LaunchDescription([
        launch_driver_arg,
        model_arg,
        port_arg,
        driver_node,
        gui_node
    ])
