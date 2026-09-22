"""
Dobot Hardware Drivers Package
Factory and exports for different Dobot model drivers.
"""

from .base_driver import DobotBaseDriver
from .magician_driver import DobotMagicianDriver
from .mg400_driver import DobotMG400Driver
from .mock_driver import DobotMockDriver

def create_driver(model_type: str = "auto") -> DobotBaseDriver:
    """
    Factory to instantiate the appropriate Dobot driver.
    model_type: 'magician', 'mg400', 'mock', or 'auto'
    """
    model_type = model_type.lower()
    if model_type in ["magician", "magician_lite", "serial"]:
        return DobotMagicianDriver()
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
    "DobotMG400Driver",
    "DobotMockDriver",
    "create_driver"
]
