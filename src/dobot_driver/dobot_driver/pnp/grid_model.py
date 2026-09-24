#!/usr/bin/env python3
"""
3x3 Arena Grid Model and Color Stacking Math
Manages coordinates, cube colors for each slot, layer calculations,
and calibration persistence.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

# Supported Color Palette
COLOR_PALETTE = {
    "red": {"name": "🔴 แดง", "hex": "#EF4444"},
    "green": {"name": "🟢 เขียว", "hex": "#10B981"},
    "blue": {"name": "🔵 น้ำเงิน", "hex": "#3B82F6"},
    "yellow": {"name": "🟡 เหลือง", "hex": "#FBBF24"},
    "orange": {"name": "🟠 ส้ม", "hex": "#F97316"},
    "purple": {"name": "🟣 ม่วง", "hex": "#A855F7"},
    "cyan": {"name": "🔷 ฟ้า", "hex": "#06B6D4"},
    "white": {"name": "⚪ ขาว", "hex": "#F1F5F9"}
}


@dataclass
class SlotData:
    slot_id: int          # 1..8 (perimeter), 9 (center)
    name: str             # Display name
    row: int              # 0..2
    col: int              # 0..2
    x: float = 200.0      # mm
    y: float = 0.0        # mm
    z: float = 10.0       # mm
    r: float = 0.0        # deg
    color: str = "red"    # color key from COLOR_PALETTE
    has_cube: bool = True # True if cube is currently available in this slot


class Grid3x3Model:
    """Manages the 3x3 Arena grid, slot positions, cube colors, and stacking logic."""

    def __init__(self, cube_height: float = 25.0, z_safe: float = 80.0, center_z_ref: str = "base", place_z_offset: float = 0.0, lock_r: bool = True, locked_r_val: float = 0.0):
        self.cube_height = float(cube_height)
        self.z_safe = float(z_safe)
        self.approach_offset = 15.0  # mm above target for smooth descent
        self.center_z_ref = str(center_z_ref)  # 'base' (table ground) or 'top_of_cube'
        self.place_z_offset = float(place_z_offset)  # fine-tuning placement offset in mm
        self.lock_r = bool(lock_r)
        self.locked_r_val = float(locked_r_val)

        # 9 slots: 8 perimeter slots + 1 center slot
        # Grid layout:
        # (0,0)=Slot 1, (0,1)=Slot 2, (0,2)=Slot 3
        # (1,0)=Slot 4, (1,1)=Slot 9(Center), (1,2)=Slot 5
        # (2,0)=Slot 6, (2,1)=Slot 7, (2,2)=Slot 8
        self.slots: Dict[int, SlotData] = {}
        self._init_default_slots()

        # Stacked layers in the center: list of colors placed from bottom to top
        self.stacked_layers: List[str] = []

    def _init_default_slots(self):
        """Initialize realistic default positions around Dobot workspace."""
        # Default Center at (X=220, Y=0, Z=10)
        # Pitch dx=45mm, dy=45mm
        center_x, center_y = 220.0, 0.0
        pitch = 45.0
        base_z = 10.0

        slot_defs = [
            (1, "Slot 1 (บนซ้าย)", 0, 0, center_x - pitch, center_y + pitch, "red"),
            (2, "Slot 2 (บน)",     0, 1, center_x,         center_y + pitch, "green"),
            (3, "Slot 3 (บนขวา)",  0, 2, center_x + pitch, center_y + pitch, "blue"),
            (4, "Slot 4 (ซ้าย)",   1, 0, center_x - pitch, center_y,         "yellow"),
            (9, "Center (จุดวาง)", 1, 1, center_x,         center_y,         "white"),  # Center Stacking
            (5, "Slot 5 (ขวา)",    1, 2, center_x + pitch, center_y,         "orange"),
            (6, "Slot 6 (ล่างซ้าย)", 2, 0, center_x - pitch, center_y - pitch, "purple"),
            (7, "Slot 7 (ล่าง)",   2, 1, center_x,         center_y - pitch, "cyan"),
            (8, "Slot 8 (ล่างขวา)", 2, 2, center_x + pitch, center_y - pitch, "red"),
        ]

        for s_id, name, row, col, x, y, colr in slot_defs:
            is_center = (s_id == 9)
            self.slots[s_id] = SlotData(
                slot_id=s_id,
                name=name,
                row=row,
                col=col,
                x=x,
                y=y,
                z=base_z,
                r=0.0,
                color=colr,
                has_cube=not is_center
            )

    @property
    def center_slot(self) -> SlotData:
        return self.slots[9]

    @property
    def perimeter_slots(self) -> List[SlotData]:
        return [self.slots[i] for i in [1, 2, 3, 4, 5, 6, 7, 8]]

    def get_slot(self, slot_id: int) -> Optional[SlotData]:
        return self.slots.get(slot_id)

    def set_slot_pose(self, slot_id: int, x: float, y: float, z: float, r: float):
        """Update calibrated pose for a slot."""
        if slot_id in self.slots:
            self.slots[slot_id].x = round(float(x), 2)
            self.slots[slot_id].y = round(float(y), 2)
            self.slots[slot_id].z = round(float(z), 2)
            final_r = self.locked_r_val if self.lock_r else float(r)
            self.slots[slot_id].r = round(final_r, 2)

    def apply_locked_r_to_all(self, r_val: Optional[float] = None):
        """Apply locked R angle to all slots (S1-S8 and Center)."""
        if r_val is not None:
            self.locked_r_val = round(float(r_val), 2)
        for slot in self.slots.values():
            slot.r = self.locked_r_val

    def set_slot_color(self, slot_id: int, color_key: str):
        """Assign cube color to slot."""
        if slot_id in self.slots and color_key in COLOR_PALETTE:
            self.slots[slot_id].color = color_key

    def calculate_place_z(self, layer_index: int) -> float:
        """
        Calculate placement Z height for a given layer index:
        layer_index: 0 for 1st layer, 1 for 2nd layer, etc.

        - If center_z_ref == 'base' (default & recommended):
            Center slot was taught at table/arena ground level.
            The 1st layer sits on top of the base: Z_base + 1*cube_height + offset
            Formula: Z_place(L) = Z_base + ((L + 1) * cube_height) + place_z_offset

        - If center_z_ref == 'top_of_cube':
            Center slot was taught on the top surface of the 1st cube.
            The 1st layer sits at Z_base + 0*cube_height + offset
            Formula: Z_place(L) = Z_base + (L * cube_height) + place_z_offset
        """
        base_z = self.center_slot.z
        if self.center_z_ref == "top_of_cube":
            return round(base_z + (float(layer_index) * self.cube_height) + self.place_z_offset, 2)
        else:
            return round(base_z + (float(layer_index + 1) * self.cube_height) + self.place_z_offset, 2)

    def find_slot_by_color(self, color_key: str, available_only: bool = True) -> Optional[SlotData]:
        """Find perimeter slot holding the specified cube color."""
        for slot in self.perimeter_slots:
            if slot.color == color_key:
                if not available_only or slot.has_cube:
                    return slot
        return None

    def reset_arena(self):
        """Reset all perimeter cubes to present and clear the center stack."""
        for slot in self.perimeter_slots:
            slot.has_cube = True
        self.stacked_layers.clear()

    def mark_picked(self, slot_id: int):
        """Mark a perimeter slot as picked/empty."""
        if slot_id in self.slots and slot_id != 9:
            self.slots[slot_id].has_cube = False

    def add_stacked_layer(self, color_key: str):
        """Register a new cube stacked on the center tower."""
        self.stacked_layers.append(color_key)

    def save_to_file(self, filepath: str):
        """Save grid calibration and color configuration to JSON."""
        data = {
            "cube_height": self.cube_height,
            "z_safe": self.z_safe,
            "approach_offset": self.approach_offset,
            "center_z_ref": self.center_z_ref,
            "place_z_offset": self.place_z_offset,
            "lock_r": self.lock_r,
            "locked_r_val": self.locked_r_val,
            "slots": [asdict(s) for s in self.slots.values()]
        }
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_from_file(self, filepath: str) -> bool:
        """Load grid calibration from JSON file."""
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cube_height = float(data.get("cube_height", self.cube_height))
            self.z_safe = float(data.get("z_safe", self.z_safe))
            self.approach_offset = float(data.get("approach_offset", self.approach_offset))
            self.center_z_ref = str(data.get("center_z_ref", self.center_z_ref))
            self.place_z_offset = float(data.get("place_z_offset", self.place_z_offset))
            self.lock_r = bool(data.get("lock_r", self.lock_r))
            self.locked_r_val = float(data.get("locked_r_val", self.locked_r_val))

            for s_dict in data.get("slots", []):
                s_id = s_dict.get("slot_id")
                if s_id in self.slots:
                    self.slots[s_id].x = s_dict.get("x", self.slots[s_id].x)
                    self.slots[s_id].y = s_dict.get("y", self.slots[s_id].y)
                    self.slots[s_id].z = s_dict.get("z", self.slots[s_id].z)
                    self.slots[s_id].r = s_dict.get("r", self.slots[s_id].r)
                    self.slots[s_id].color = s_dict.get("color", self.slots[s_id].color)
                    self.slots[s_id].has_cube = s_dict.get("has_cube", self.slots[s_id].has_cube)
            return True
        except Exception:
            return False
