"""
Hand-Guided 3x3 Teaching Tab
Provides a direct 3x3 interactive grid layout where each cell has its own
Record button, Color selector, Test Move button, and Coordinate readout.
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from dobot_driver.pnp.grid_model import Grid3x3Model, SlotData, COLOR_PALETTE


class SlotTeachingCell(QtWidgets.QFrame):
    """Visual teaching card for an individual slot inside the 3x3 grid."""

    sig_record_clicked = Signal(int)
    sig_test_clicked = Signal(int)
    sig_color_changed = Signal(int, str)

    def __init__(self, slot: SlotData, is_center: bool = False, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.is_center = is_center
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setMinimumSize(140, 130)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header Title
        title_box = QtWidgets.QHBoxLayout()
        title_box.setSpacing(4)
        if self.is_center:
            self.lbl_title = QtWidgets.QLabel("🏢 CENTER (จุดวาง)")
            self.lbl_title.setStyleSheet("font-weight: 800; font-size: 11px; color: #F59E0B;")
        else:
            self.lbl_title = QtWidgets.QLabel(f"S{self.slot.slot_id}: {self.slot.name.split()[1] if len(self.slot.name.split()) > 1 else self.slot.name}")
            self.lbl_title.setStyleSheet("font-weight: 800; font-size: 11px; color: #94A3B8;")

        title_box.addWidget(self.lbl_title)
        title_box.addStretch()
        layout.addLayout(title_box)

        # Color Selector (for perimeter slots) or Center Badge
        if not self.is_center:
            self.combo_color = QtWidgets.QComboBox()
            self.combo_color.setFixedHeight(22)
            self.combo_color.setStyleSheet("font-size: 10px; padding: 1px 4px;")
            for key, info in COLOR_PALETTE.items():
                self.combo_color.addItem(info["name"], key)
            idx = self.combo_color.findData(self.slot.color)
            if idx >= 0:
                self.combo_color.setCurrentIndex(idx)
            self.combo_color.currentIndexChanged.connect(self._on_color_changed)
            layout.addWidget(self.combo_color)
        else:
            self.lbl_center_desc = QtWidgets.QLabel("ฐานวางซ้อน (Base Stacking)")
            self.lbl_center_desc.setStyleSheet("font-size: 10px; color: #FBBF24;")
            layout.addWidget(self.lbl_center_desc)

        # Coordinates Display Box
        self.coord_box = QtWidgets.QFrame()
        self.coord_box.setStyleSheet("background-color: #0A0B0E; border: 1px solid #232733; border-radius: 4px; padding: 2px;")
        coord_layout = QtWidgets.QVBoxLayout(self.coord_box)
        coord_layout.setContentsMargins(4, 2, 4, 2)
        coord_layout.setSpacing(1)

        self.lbl_xy = QtWidgets.QLabel(f"X:{self.slot.x:.1f}  Y:{self.slot.y:.1f}")
        self.lbl_xy.setStyleSheet("font-size: 10px; font-weight: bold; color: #60A5FA;")
        self.lbl_zr = QtWidgets.QLabel(f"Z:{self.slot.z:.1f}  R:{self.slot.r:.1f}°")
        self.lbl_zr.setStyleSheet("font-size: 10px; font-weight: bold; color: #10B981;")

        coord_layout.addWidget(self.lbl_xy)
        coord_layout.addWidget(self.lbl_zr)
        layout.addWidget(self.coord_box)

        # Action Buttons: Record & Test
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.setSpacing(4)

        self.btn_record = QtWidgets.QPushButton("📍 บันทึก")
        self.btn_record.setObjectName("btn_action_green")
        self.btn_record.setFixedHeight(24)
        self.btn_record.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 6px;")
        self.btn_record.setToolTip(f"บันทึกพิกัดแขนกลขณะนี้ลงใน {self.slot.name}")
        self.btn_record.clicked.connect(lambda: self.sig_record_clicked.emit(self.slot.slot_id))

        self.btn_test = QtWidgets.QPushButton("🎯 ทดสอบ")
        self.btn_test.setFixedHeight(24)
        self.btn_test.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self.btn_test.setToolTip("สั่งแขนกลเลื่อนมาทดสอบความแม่นยำที่ช่องนี้")
        self.btn_test.clicked.connect(lambda: self.sig_test_clicked.emit(self.slot.slot_id))

        btn_box.addWidget(self.btn_record, 1)
        btn_box.addWidget(self.btn_test, 1)
        layout.addLayout(btn_box)

        self.update_style()

    def update_style(self):
        if self.is_center:
            border = "2px dashed #F59E0B"
            bg = "#181A22"
        else:
            border = "1px solid #28303F"
            bg = "#13151D"

        self.setStyleSheet(f"""
            SlotTeachingCell {{
                background-color: {bg};
                border: {border};
                border-radius: 6px;
            }}
            SlotTeachingCell:hover {{
                border: 2px solid #3B82F6;
            }}
        """)

    def _on_color_changed(self):
        color_key = self.combo_color.currentData()
        self.sig_color_changed.emit(self.slot.slot_id, color_key)

    def refresh_pose(self):
        self.lbl_xy.setText(f"X:{self.slot.x:.1f}  Y:{self.slot.y:.1f}")
        self.lbl_zr.setText(f"Z:{self.slot.z:.1f}  R:{self.slot.r:.1f}°")

        # Flash green feedback momentarily
        self.coord_box.setStyleSheet("background-color: #064E3B; border: 1px solid #10B981; border-radius: 4px; padding: 2px;")
        QtCore.QTimer.singleShot(600, lambda: self.coord_box.setStyleSheet(
            "background-color: #0A0B0E; border: 1px solid #232733; border-radius: 4px; padding: 2px;"
        ))


class GridTeachingTab(QtWidgets.QWidget):
    """Interactive 3x3 Teaching Tab where each cell has its own Record button."""

    sig_model_updated = Signal()

    def __init__(self, bridge, grid_model: Grid3x3Model, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.grid_model = grid_model

        self._curr_robot_pose = (220.0, 0.0, 50.0, 0.0)
        self.cells: dict = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(8)

        # Top Bar: Real-time Arm Position & Quick Instructions
        top_bar = QtWidgets.QFrame()
        top_bar.setStyleSheet("background-color: #161822; border: 1px solid #28303F; border-radius: 6px; padding: 4px 8px;")
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 4, 6, 4)
        top_layout.setSpacing(12)

        instr_lbl = QtWidgets.QLabel("✋ <b>วิธี Teach:</b> ช่องหยิบ (S1-S8) แตะ <b>ผิวด้านบนก้อนลูกบาศก์</b> | ช่องวาง (Center) แตะ <b>พื้นผิวโต๊ะ/ฐานรอง</b> แล้วกด <b>'📍 บันทึก'</b>")
        instr_lbl.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        top_layout.addWidget(instr_lbl)

        top_layout.addStretch()

        # Telemetry Badges
        top_layout.addWidget(QtWidgets.QLabel("พิกัดสด:"))
        self.badge_x = self._make_metric_badge("X", "220.0", "#60A5FA")
        self.badge_y = self._make_metric_badge("Y", "0.0", "#60A5FA")
        self.badge_z = self._make_metric_badge("Z", "50.0", "#34D399")
        self.badge_r = self._make_metric_badge("R", "0.0°", "#FBBF24")
        top_layout.addWidget(self.badge_x)
        top_layout.addWidget(self.badge_y)
        top_layout.addWidget(self.badge_z)
        top_layout.addWidget(self.badge_r)

        root_layout.addWidget(top_bar)

        # Center: Direct 3x3 Grid of Teaching Cells
        grid_container = QtWidgets.QFrame()
        grid_container.setStyleSheet("background-color: #0E1015; border: 1px solid #232733; border-radius: 6px;")
        grid_layout = QtWidgets.QGridLayout(grid_container)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        grid_layout.setSpacing(8)

        for slot_id, slot in self.grid_model.slots.items():
            is_center = (slot_id == 9)
            cell = SlotTeachingCell(slot, is_center=is_center)
            cell.sig_record_clicked.connect(self._on_record_cell)
            cell.sig_test_clicked.connect(self._on_test_cell)
            cell.sig_color_changed.connect(self._on_cell_color_changed)
            self.cells[slot_id] = cell
            grid_layout.addWidget(cell, slot.row, slot.col)

        root_layout.addWidget(grid_container, 1)

        # Bottom: Persistence Actions
        bot_bar = QtWidgets.QHBoxLayout()
        bot_bar.setSpacing(8)

        self.btn_save_calib = QtWidgets.QPushButton("💾 บันทึกไฟล์พิกัด (Save JSON)")
        self.btn_save_calib.setFixedHeight(28)
        self.btn_load_calib = QtWidgets.QPushButton("📂 เปิดไฟล์พิกัด (Load JSON)")
        self.btn_load_calib.setFixedHeight(28)
        self.btn_reset_defaults = QtWidgets.QPushButton("🔄 คืนค่าเริ่มต้น")
        self.btn_reset_defaults.setFixedHeight(28)

        bot_bar.addWidget(self.btn_save_calib)
        bot_bar.addWidget(self.btn_load_calib)
        bot_bar.addWidget(self.btn_reset_defaults)
        bot_bar.addStretch()

        self.lbl_feedback = QtWidgets.QLabel("พร้อมบันทึกพิกัด")
        self.lbl_feedback.setStyleSheet("color: #94A3B8; font-size: 10px;")
        bot_bar.addWidget(self.lbl_feedback)

        root_layout.addLayout(bot_bar)

    def _make_metric_badge(self, name: str, val: str, color: str):
        lbl = QtWidgets.QLabel(f"{name}: {val}")
        lbl.setStyleSheet(f"""
            background-color: #0F1015;
            color: {color};
            font-weight: bold;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid #28303F;
        """)
        return lbl

    def _connect_signals(self):
        self.btn_save_calib.clicked.connect(self._on_save_file)
        self.btn_load_calib.clicked.connect(self._on_load_file)
        self.btn_reset_defaults.clicked.connect(self._on_reset_defaults)

        self.bridge.sig_pose_updated.connect(self._on_robot_pose_updated)

    def _on_robot_pose_updated(self, x, y, z, r, j1, j2, j3, j4):
        self._curr_robot_pose = (x, y, z, r)
        self.badge_x.setText(f"X: {x:.1f}")
        self.badge_y.setText(f"Y: {y:.1f}")
        self.badge_z.setText(f"Z: {z:.1f}")
        self.badge_r.setText(f"R: {r:.1f}°")

    def _on_record_cell(self, slot_id: int):
        x, y, z, r = self._curr_robot_pose
        self.grid_model.set_slot_pose(slot_id, x, y, z, r)
        cell = self.cells.get(slot_id)
        if cell:
            cell.refresh_pose()
        self.sig_model_updated.emit()
        slot = self.grid_model.get_slot(slot_id)
        msg = f"บันทึก {slot.name}: X={x:.1f}, Y={y:.1f}, Z={z:.1f}, R={r:.1f}° เรียบร้อย"
        self.lbl_feedback.setText(f"✅ {msg}")
        self.bridge.sig_log.emit("CMD", msg)

    def _on_test_cell(self, slot_id: int):
        slot = self.grid_model.get_slot(slot_id)
        if slot:
            z_safe = self.grid_model.z_safe
            self.lbl_feedback.setText(f"🚀 เคลื่อนที่ไปทดสอบที่ {slot.name}...")
            self.bridge.send_ptp(slot.x, slot.y, z_safe, slot.r, mode=2)
            QtCore.QTimer.singleShot(1100, lambda: self.bridge.send_ptp(slot.x, slot.y, slot.z, slot.r, mode=2))

    def _on_cell_color_changed(self, slot_id: int, color_key: str):
        self.grid_model.set_slot_color(slot_id, color_key)
        self.sig_model_updated.emit()

    def _on_save_file(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "บันทึกการ Calibrate พิกัด 3x3", "grid_calibration.json", "JSON (*.json)")
        if path:
            self.grid_model.save_to_file(path)
            self.lbl_feedback.setText("💾 บันทึกไฟล์พิกัดสำเร็จ")
            self.bridge.sig_log.emit("INFO", f"Saved calibration to {path}")

    def _on_load_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "เปิดไฟล์ Calibrate พิกัด 3x3", "", "JSON (*.json)")
        if path:
            if self.grid_model.load_from_file(path):
                for s_id, cell in self.cells.items():
                    cell.slot = self.grid_model.get_slot(s_id)
                    cell.refresh_pose()
                    if not cell.is_center and hasattr(cell, "combo_color"):
                        idx = cell.combo_color.findData(cell.slot.color)
                        if idx >= 0:
                            cell.combo_color.setCurrentIndex(idx)
                self.sig_model_updated.emit()
                self.lbl_feedback.setText("📂 โหลดไฟล์พิกัดสำเร็จ")
                self.bridge.sig_log.emit("INFO", f"Loaded calibration from {path}")

    def _on_reset_defaults(self):
        self.grid_model._init_default_slots()
        for s_id, cell in self.cells.items():
            cell.slot = self.grid_model.get_slot(s_id)
            cell.refresh_pose()
        self.sig_model_updated.emit()
        self.lbl_feedback.setText("🔄 คืนค่าพิกัดเริ่มต้นสำเร็จ")
        self.bridge.sig_log.emit("INFO", "Reset grid calibration to default.")
