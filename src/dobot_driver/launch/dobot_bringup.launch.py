#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory("dobot_driver")
    default_config = os.path.join(pkg_share, "config", "dobot_params.yaml")

    model_arg = DeclareLaunchArgument(
        "model_type", default_value="auto",
        description="Dobot model ('magician', 'mg400', 'mock', 'auto')"
    )
    port_arg = DeclareLaunchArgument(
        "port", default_value="",
        description="Serial port (e.g. /dev/ttyUSB0)"
    )
    config_arg = DeclareLaunchArgument(
        "config_file", default_value=default_config,
        description="Path to parameter yaml file"
    )

    driver_node = Node(
        package="dobot_driver",
        executable="dobot_node",
        name="dobot_driver_node",
        parameters=[
            LaunchConfiguration("config_file"),
            {
                "model_type": LaunchConfiguration("model_type"),
                "port": LaunchConfiguration("port")
            }
        ],
        output="screen"
    )

    return LaunchDescription([
        model_arg,
        port_arg,
        config_arg,
        driver_node
    ])
