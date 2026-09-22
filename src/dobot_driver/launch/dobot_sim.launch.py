#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    driver_node = Node(
        package="dobot_driver",
        executable="dobot_node",
        name="dobot_driver_node",
        parameters=[{
            "model_type": "mock",
            "publish_rate": 20.0
        }],
        output="screen"
    )

    return LaunchDescription([
        driver_node
    ])
