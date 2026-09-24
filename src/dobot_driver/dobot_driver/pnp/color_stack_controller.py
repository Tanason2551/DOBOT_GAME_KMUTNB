#!/usr/bin/env python3
"""
Color Stacking Pick & Place Controller (State Machine)
Coordinates arm trajectory, suction actuation, layer calculation,
and color matching for 3x3 cube stacking.
"""

import time
import threading
from typing import List, Dict, Optional, Callable, Any

from .grid_model import Grid3x3Model, SlotData, COLOR_PALETTE
from .model_profiles import DobotModelProfile, get_profile_for_model


class ColorStackController:
    """State Machine executing the 3x3 Grid Cube Stacking mission."""

    # States
    STATE_IDLE = "IDLE"
    STATE_APPROACH_PICK = "APPROACH_PICK"
    STATE_DESCEND_PICK = "DESCEND_PICK"
    STATE_SUCTION_ON = "SUCTION_ON"
    STATE_LIFT_SAFE = "LIFT_SAFE"
    STATE_APPROACH_CENTER = "APPROACH_CENTER"
    STATE_DESCEND_PLACE = "DESCEND_PLACE"
    STATE_SUCTION_OFF = "SUCTION_OFF"
    STATE_RETRACT_SAFE = "RETRACT_SAFE"
    STATE_PAUSED = "PAUSED"
    STATE_ABORTED = "ABORTED"
    STATE_COMPLETED = "COMPLETED"

    def __init__(self, driver, grid_model: Grid3x3Model):
        self.driver = driver
        self.grid_model = grid_model
        self.profile: DobotModelProfile = get_profile_for_model(getattr(driver, "model_name", "mock"))

        self.current_state = self.STATE_IDLE
        self.is_running = False
        self.is_paused = False

        self._thread: Optional[threading.Thread] = None
        self._pause_cond = threading.Condition()
        self._lock = threading.Lock()

        # Callbacks
        self.callback_state: Optional[Callable[[str, str], None]] = None
        self.callback_layer: Optional[Callable[[int, int, str], None]] = None
        self.callback_finished: Optional[Callable[[bool, str], None]] = None
        self.callback_log: Optional[Callable[[str, str], None]] = None

    def log(self, level: str, msg: str):
        if self.callback_log:
            self.callback_log(level, msg)

    def set_callbacks(self, on_state=None, on_layer=None, on_finished=None, on_log=None):
        self.callback_state = on_state
        self.callback_layer = on_layer
        self.callback_finished = on_finished
        self.callback_log = on_log

    def _set_state(self, state: str, detail: str = ""):
        self.current_state = state
        if self.callback_state:
            self.callback_state(state, detail)

    def start_mission(self, plan_items: List[Any], mode: str = "color") -> bool:
        """
        Start automated stacking mission.
        plan_items: List of colors e.g. ["red", "green", "blue"] or list of slot IDs [1, 2, 3]
        mode: "color" or "slot"
        """
        with self._lock:
            if self.is_running:
                self.log("WARN", "Mission is already running!")
                return False

            if not self.driver or not self.driver.is_connected:
                self.log("ERROR", "Robot is not connected. Cannot start mission.")
                return False

            if not plan_items:
                self.log("WARN", "Mission plan queue is empty.")
                return False

            self.is_running = True
            self.is_paused = False
            self.profile = get_profile_for_model(self.driver.model_name)

            self._thread = threading.Thread(
                target=self._mission_worker,
                args=(list(plan_items), mode),
                daemon=True
            )
            self._thread.start()
            return True

    def pause(self):
        """Pause mission at the current step."""
        with self._pause_cond:
            self.is_paused = True
            self._set_state(self.STATE_PAUSED, "Mission paused by user.")
            self.log("WARN", "Mission PAUSED.")

    def resume(self):
        """Resume paused mission."""
        with self._pause_cond:
            self.is_paused = False
            self._pause_cond.notify_all()
            self.log("INFO", "Mission RESUMED.")

    def stop(self):
        """Stop and cancel mission immediately."""
        with self._pause_cond:
            self.is_running = False
            self.is_paused = False
            self._pause_cond.notify_all()

        if self.driver:
            self.driver.set_suction_cup(False, False)

        self._set_state(self.STATE_ABORTED, "Mission stopped by user.")
        self.log("WARN", "Mission ABORTED.")

    def _check_pause_or_abort(self) -> bool:
        """Check if execution was paused or aborted. Returns False if aborted."""
        with self._pause_cond:
            while self.is_paused and self.is_running:
                self._pause_cond.wait(timeout=0.1)
            return self.is_running

    def _mission_worker(self, plan_items: List[Any], mode: str):
        """Main background execution loop."""
        try:
            total_layers = len(plan_items)
            self.log("INFO", f"Starting Cube Stacking mission for {total_layers} layers (Mode: {mode})...")

            center = self.grid_model.center_slot
            z_safe = max(self.grid_model.z_safe, center.z + (total_layers * self.grid_model.cube_height) + 20.0)

            # 1. Lift arm to safe travel height before doing anything
            pose = self.driver.get_pose() if self.driver else None
            if pose and len(pose) >= 4:
                curr_x, curr_y, curr_z, curr_r = pose[0:4]
            else:
                curr_x, curr_y, curr_z, curr_r = 220.0, 0.0, z_safe, 0.0

            init_r = self.grid_model.locked_r_val if self.grid_model.lock_r else curr_r
            self.driver.move_ptp(curr_x, curr_y, z_safe, init_r, wait=True)

            for layer_idx, item in enumerate(plan_items):
                if not self._check_pause_or_abort():
                    break

                # Identify target pick slot
                slot: Optional[SlotData] = None
                target_color = "red"

                if mode == "color":
                    target_color = str(item).lower()
                    slot = self.grid_model.find_slot_by_color(target_color, available_only=True)
                    if not slot:
                        self.log("ERROR", f"No available cube of color '{target_color}' found on 3x3 grid!")
                        self.stop()
                        if self.callback_finished:
                            self.callback_finished(False, f"Missing cube color: {target_color}")
                        return
                else:
                    slot_id = int(item)
                    slot = self.grid_model.get_slot(slot_id)
                    if not slot or not slot.has_cube:
                        self.log("ERROR", f"Slot #{slot_id} is empty or invalid!")
                        self.stop()
                        if self.callback_finished:
                            self.callback_finished(False, f"Slot #{slot_id} is empty.")
                        return
                    target_color = slot.color

                thai_color = COLOR_PALETTE.get(target_color, {}).get("name", target_color)
                self.log("INFO", f"--- Layer {layer_idx + 1}/{total_layers}: Picking {thai_color} from {slot.name} ---")

                # Determine R orientation (strictly enforce locked_r_val if lock_r is enabled)
                pick_r = self.grid_model.locked_r_val if self.grid_model.lock_r else slot.r
                place_r = self.grid_model.locked_r_val if self.grid_model.lock_r else center.r

                # --- STEP 1: Approach Pick Position at Z_safe ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_APPROACH_PICK, f"กำลังเคลื่อนที่ไปเหนือ {slot.name}")
                self.driver.move_ptp(slot.x, slot.y, z_safe, pick_r, wait=True)

                # --- STEP 2: Descend to Pick Surface ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_DESCEND_PICK, f"กำลังลดระดับลงแตะผิวลูกบาศก์ ({thai_color})")
                self.driver.move_ptp(slot.x, slot.y, slot.z, pick_r, wait=True)
                time.sleep(0.15)

                # --- STEP 3: Actuate Suction Cup ON ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_SUCTION_ON, "เปิดหัวดูดสุญญากาศ (Suction ON)")
                self.driver.set_suction_cup(True, True)
                time.sleep(self.profile.suction_on_delay_sec)

                # --- STEP 4: Lift up to Z_safe with Cube ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_LIFT_SAFE, f"ยกลูกบาศก์ {thai_color} ขึ้นสู่ระดับปลอดภัย")
                self.driver.move_ptp(slot.x, slot.y, z_safe, pick_r, wait=True)

                # Mark slot as picked on model
                self.grid_model.mark_picked(slot.slot_id)

                # --- STEP 5: Travel to Center at Z_safe ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_APPROACH_CENTER, f"นำลูกบาศก์ไปยังจุด Center (ชั้นที่ {layer_idx + 1})")
                self.driver.move_ptp(center.x, center.y, z_safe, place_r, wait=True)

                # Calculate Place Z for this layer
                target_place_z = self.grid_model.calculate_place_z(layer_idx)

                # --- STEP 6: Descend to Stacking Level ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_DESCEND_PLACE, f"วางซ้อนลงบนชั้นที่ {layer_idx + 1} (Z={target_place_z:.1f}mm)")
                self.driver.move_ptp(center.x, center.y, target_place_z, place_r, wait=True)
                time.sleep(0.15)

                # --- STEP 7: Actuate Suction Cup OFF ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_SUCTION_OFF, f"คลายแรงดูด ปล่อยชิ้นงาน {thai_color}")
                self.driver.set_suction_cup(True, False)
                time.sleep(self.profile.suction_off_delay_sec)
                self.driver.set_suction_cup(False, False)

                # --- STEP 8: Retract straight up to Z_safe ---
                if not self._check_pause_or_abort(): break
                self._set_state(self.STATE_RETRACT_SAFE, "ยกแขนกลับสู่ระดับปลอดภัย")
                self.driver.move_ptp(center.x, center.y, z_safe, place_r, wait=True)

                # Record stacked layer
                self.grid_model.add_stacked_layer(target_color)
                if self.callback_layer:
                    self.callback_layer(layer_idx + 1, total_layers, target_color)

                self.log("CMD", f"Layer {layer_idx + 1}/{total_layers} ({thai_color}) placed successfully!")
                time.sleep(0.4)

            if self.current_state != self.STATE_ABORTED:
                self._set_state(self.STATE_COMPLETED, "ภารกิจเสร็จสิ้นสมบูรณ์!")
                self.log("INFO", "🎉 Mission Completed Successfully!")
                if self.callback_finished:
                    self.callback_finished(True, "ภารกิจเสร็จสิ้นสมบูรณ์!")
        except Exception as e:
            self.log("ERROR", f"ข้อผิดพลาดระหว่างปฏิบัติภารกิจ: {e}")
            if self.callback_finished:
                self.callback_finished(False, f"เกิดข้อผิดพลาด: {e}")
        finally:
            with self._lock:
                self.is_running = False
