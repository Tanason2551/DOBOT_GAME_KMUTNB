#!/usr/bin/env python3
"""
Hardware Model Profiles
Stores specifications, workspace safety envelopes, and timing parameters
for different Dobot models (Magician, MG400, CR, Simulation).
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DobotModelProfile:
    model_id: str
    display_name: str
    connection_type: str  # "serial", "tcp", "mock"
    default_port: str     # e.g. "/dev/ttyUSB0" or "192.168.1.6"
    default_baud: int     # 115200
    r_min_mm: float       # Min reach radius
    r_max_mm: float       # Max reach radius
    z_min_mm: float       # Min Z height
    z_max_mm: float       # Max Z height
    suction_on_delay_sec: float   # Wait time for suction seal to form
    suction_off_delay_sec: float  # Wait time for vacuum dissipation
    hand_teach_method: str        # "physical_button", "software_drag", "jog_only"
    supports_3d_urdf: bool        # Future 3D mesh support


PROFILES: Dict[str, DobotModelProfile] = {
    "magician": DobotModelProfile(
        model_id="magician",
        display_name="Dobot Magician / Magician Lite",
        connection_type="serial",
        default_port="/dev/ttyUSB0",
        default_baud=115200,
        r_min_mm=190.0,
        r_max_mm=330.0,
        z_min_mm=-60.0,
        z_max_mm=150.0,
        suction_on_delay_sec=0.80,
        suction_off_delay_sec=0.50,
        hand_teach_method="physical_button",
        supports_3d_urdf=True
    ),
    "mg400": DobotModelProfile(
        model_id="mg400",
        display_name="Dobot MG400 (Desktop SCARA)",
        connection_type="tcp",
        default_port="192.168.1.6",
        default_baud=29999,
        r_min_mm=150.0,
        r_max_mm=440.0,
        z_min_mm=-10.0,
        z_max_mm=210.0,
        suction_on_delay_sec=0.15,
        suction_off_delay_sec=0.10,
        hand_teach_method="software_drag",
        supports_3d_urdf=True
    ),
    "mock": DobotModelProfile(
        model_id="mock",
        display_name="Dobot Simulation (Mock)",
        connection_type="mock",
        default_port="sim",
        default_baud=0,
        r_min_mm=100.0,
        r_max_mm=350.0,
        z_min_mm=-70.0,
        z_max_mm=160.0,
        suction_on_delay_sec=0.20,
        suction_off_delay_sec=0.15,
        hand_teach_method="jog_only",
        supports_3d_urdf=True
    )
}


def get_profile_for_model(model_name: str) -> DobotModelProfile:
    """Retrieve profile by model identifier or return default mock profile."""
    key = model_name.lower().strip()
    if "magician" in key:
        return PROFILES["magician"]
    elif "mg400" in key:
        return PROFILES["mg400"]
    return PROFILES["mock"]
