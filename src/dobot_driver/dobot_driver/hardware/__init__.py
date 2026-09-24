"""
Dobot Hardware Drivers Package
Factory and exports for different Dobot model drivers.
"""

from .base_driver import DobotBaseDriver
from .magician_driver import DobotMagicianDriver
from .pydobot_driver import DobotPydobotDriver
from .pydobot2_driver import DobotPydobot2Driver
from .mg400_driver import DobotMG400Driver
from .mock_driver import DobotMockDriver

def create_driver(model_type: str = "auto") -> DobotBaseDriver:
    """
    Factory to instantiate the appropriate Dobot driver.
    model_type: 'magician', 'pydobot', 'pydobot2', 'mg400', 'mock', or 'auto'
    """
    model_type = model_type.lower()
    if model_type in ["magician", "magician_lite", "serial", "custom"]:
        return DobotMagicianDriver()
    elif model_type in ["pydobot", "pydobot_driver", "dobot1"]:
        return DobotPydobotDriver()
    elif model_type in ["pydobot2", "pydobot2_driver", "dobot2"]:
        return DobotPydobot2Driver()
    elif model_type in ["mg400", "cr", "tcp"]:
        return DobotMG400Driver()
    elif model_type in ["mock", "sim", "simulation"]:
        return DobotMockDriver()
    elif model_type == "auto":
        # Check if serial ports exist
        ports = DobotMagicianDriver.scan_ports()
        if ports:
            return DobotMagicianDriver()
        return DobotMockDriver()
    else:
        raise ValueError(f"Unknown Dobot model type: {model_type}")

__all__ = [
    "DobotBaseDriver",
    "DobotMagicianDriver",
    "DobotPydobotDriver",
    "DobotPydobot2Driver",
    "DobotMG400Driver",
    "DobotMockDriver",
    "create_driver"
]
