import os
from glob import glob
from setuptools import setup, find_packages

package_name = "dobot_gui"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "PySide6", "pyserial"],
    zip_safe=True,
    maintainer="tanason",
    maintainer_email="tanason@todo.todo",
    description="ROS 2 Desktop GUI application for Dobot robotic arm control",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dobot_gui_node = dobot_gui.gui_node:main",
        ],
    },
)
