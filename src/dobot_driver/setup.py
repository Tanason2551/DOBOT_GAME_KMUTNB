import os
from glob import glob
from setuptools import setup, find_packages

package_name = "dobot_driver"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools", "pyserial"],
    zip_safe=True,
    maintainer="tanason",
    maintainer_email="tanason@todo.todo",
    description="ROS 2 Driver package for Dobot robotic arms",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dobot_node = dobot_driver.dobot_node:main",
        ],
    },
)
