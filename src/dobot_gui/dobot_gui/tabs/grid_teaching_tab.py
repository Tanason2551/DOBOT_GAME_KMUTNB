"""
Hand-Guided 3x3 Teaching Tab with Coordinate Editing & R Axis Locking
Provides:
- 3x3 interactive grid layout where each cell has its own Record, Edit, and Test Move buttons
- Individual coordinate editing modal with Z fine-tuning (nudge), live pose grab, and test move
- Batch coordinate table editor for managing all 9 slots simultaneously
- R axis lock system enforcing a fixed rotation angle at all times
"""

from typing import Dict, Tuple, Optional
from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from dobot_driver.pnp.grid_model import Grid3x3Model, SlotData, COLOR_PALETTE


class EditSlotPoseDialog(QtWidgets.QDialog):
    """Dialog for editing coordinates (X, Y, Z, R) of an individual pick/place slot."""

    def __init__(self, slot: SlotData, curr_pose: tuple, bridge, z_safe: float,
                 lock_r: bool = False, locked_r_val: float = 0.0, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.curr_pose = curr_pose
        self.bridge = bridge
        self.z_safe = z_safe
        self.lock_r = lock_r
        self.locked_r_val = locked_r_val

        self.setWindowTitle(f"✏️ แก้ไขพิกัด {slot.name}")
        self.setMinimumWidth(380)
        self.setStyleSheet("""
            QDialog {
                background-color: #12141C;
                color: #E2E8F0;
            }
            QLabel {
                font-size: 11px;
                color: #CBD5E1;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info Banner
        header = QtWidgets.QFrame()
        header.setStyleSheet("background-color: #1A1D27; border: 1px solid #28303F; border-radius: 6px; padding: 6px;")
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(8, 6, 8, 6)

        is_center = (self.slot.slot_id == 9)
        title_text = f"🏢 {self.slot.name} (จุดวางฐานกลาง)" if is_center else f"📦 {self.slot.name} (จุดหยิบ)"
        title_color = "#F59E0B" if is_center else "#60A5FA"
        lbl_head = QtWidgets.QLabel(f"<b>{title_text}</b>")
        lbl_head.setStyleSheet(f"font-size: 13px; color: {title_color};")
        h_layout.addWidget(lbl_head)
        h_layout.addStretch()
        layout.addWidget(header)

        # Form Inputs: X, Y, Z, R
        form_group = QtWidgets.QGroupBox("พิกัดตำแหน่งเป้าหมาย (Target Coordinates)")
        form_layout = QtWidgets.QGridLayout(form_group)
        form_layout.setContentsMargins(12, 14, 12, 12)
        form_layout.setSpacing(8)

        # X
        form_layout.addWidget(QtWidgets.QLabel("X (mm):"), 0, 0)
        self.spin_x = QtWidgets.QDoubleSpinBox()
        self.spin_x.setRange(-500.0, 500.0)
        self.spin_x.setDecimals(2)
        self.spin_x.setSingleStep(0.5)
        self.spin_x.setValue(self.slot.x)
        self.spin_x.setSuffix(" mm")
        form_layout.addWidget(self.spin_x, 0, 1)

        # Y
        form_layout.addWidget(QtWidgets.QLabel("Y (mm):"), 1, 0)
        self.spin_y = QtWidgets.QDoubleSpinBox()
        self.spin_y.setRange(-500.0, 500.0)
        self.spin_y.setDecimals(2)
        self.spin_y.setSingleStep(0.5)
        self.spin_y.setValue(self.slot.y)
        self.spin_y.setSuffix(" mm")
        form_layout.addWidget(self.spin_y, 1, 1)

        # Z
        form_layout.addWidget(QtWidgets.QLabel("Z (mm):"), 2, 0)
        self.spin_z = QtWidgets.QDoubleSpinBox()
        self.spin_z.setRange(-200.0, 300.0)
        self.spin_z.setDecimals(2)
        self.spin_z.setSingleStep(0.5)
        self.spin_z.setValue(self.slot.z)
        self.spin_z.setSuffix(" mm")
        form_layout.addWidget(self.spin_z, 2, 1)

        # R
        form_layout.addWidget(QtWidgets.QLabel("R (องศา):"), 3, 0)
        self.spin_r = QtWidgets.QDoubleSpinBox()
        self.spin_r.setRange(-180.0, 180.0)
        self.spin_r.setDecimals(2)
        self.spin_r.setSingleStep(1.0)
        initial_r = self.locked_r_val if self.lock_r else self.slot.r
        self.spin_r.setValue(initial_r)
        self.spin_r.setSuffix("°")
        form_layout.addWidget(self.spin_r, 3, 1)

        if self.lock_r:
            lbl_r_lock = QtWidgets.QLabel(f"🔒 ล็อกแกน R ที่ {self.locked_r_val:.1f}°")
            lbl_r_lock.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 600;")
            form_layout.addWidget(lbl_r_lock, 3, 2)
            self.spin_r.setEnabled(False)

        layout.addWidget(form_group)

        # Quick Z Nudge Buttons (Fine-tuning height for suction cup contact)
        nudge_box = QtWidgets.QGroupBox("ปรับระดับความสูง Z แบบละเอียด (Z Nudge)")
        nudge_layout = QtWidgets.QHBoxLayout(nudge_box)
        nudge_layout.setContentsMargins(8, 10, 8, 8)
        nudge_layout.setSpacing(4)

        nudge_values = [-5.0, -1.0, -0.5, 0.5, 1.0, 5.0]
        for val in nudge_values:
            sign_str = f"+{val:.1f}" if val > 0 else f"{val:.1f}"
            btn = QtWidgets.QPushButton(f"{sign_str} mm")
            btn.setFixedHeight(24)
            btn.setStyleSheet("font-size: 10px; padding: 2px 4px; background-color: #1F2430; border: 1px solid #333C4E;")
            btn.clicked.connect(lambda _, delta=val: self._nudge_z(delta))
            nudge_layout.addWidget(btn)

        layout.addWidget(nudge_box)

        # Action Buttons: Use Current Pose & Test Move
        tools_box = QtWidgets.QHBoxLayout()
        tools_box.setSpacing(6)

        self.btn_use_current = QtWidgets.QPushButton("📍 ดึงพิกัดแขนกลขณะนี้")
        self.btn_use_current.setFixedHeight(28)
        self.btn_use_current.setToolTip("นำพิกัดปัจจุบันของแขนกลมากรอกในช่อง")
        self.btn_use_current.clicked.connect(self._on_use_current_pose)
        tools_box.addWidget(self.btn_use_current)

        self.btn_test_move = QtWidgets.QPushButton("🎯 ทดสอบเลื่อนไปยังพิกัดนี้")
        self.btn_test_move.setFixedHeight(28)
        self.btn_test_move.setStyleSheet("background-color: #2563EB;")
        self.btn_test_move.setToolTip("สั่งให้แขนกลเลื่อนมาทดสอบความแม่นยำตามตัวเลขด้านบน")
        self.btn_test_move.clicked.connect(self._on_test_move)
        tools_box.addWidget(self.btn_test_move)

        layout.addLayout(tools_box)

        # Dialog Standard Confirm / Cancel Buttons
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_save = QtWidgets.QPushButton("💾 บันทึก (Save)")
        self.btn_save.setObjectName("btn_action_green")
        self.btn_save.setFixedHeight(32)
        self.btn_save.clicked.connect(self.accept)

        self.btn_cancel = QtWidgets.QPushButton("❌ ยกเลิก")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setStyleSheet("background-color: #374151;")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _nudge_z(self, delta: float):
        new_z = round(self.spin_z.value() + delta, 2)
        self.spin_z.setValue(new_z)

    def _on_use_current_pose(self):
        cx, cy, cz, cr = self.curr_pose
        self.spin_x.setValue(round(cx, 2))
        self.spin_y.setValue(round(cy, 2))
        self.spin_z.setValue(round(cz, 2))
        if not self.lock_r:
            self.spin_r.setValue(round(cr, 2))

    def _on_test_move(self):
        x = self.spin_x.value()
        y = self.spin_y.value()
        z = self.spin_z.value()
        r = self.locked_r_val if self.lock_r else self.spin_r.value()

        # Safely approach above target then descend
        self.bridge.send_ptp(x, y, self.z_safe, r, mode=2)
        QtCore.QTimer.singleShot(1100, lambda: self.bridge.send_ptp(x, y, z, r, mode=2))

    def get_pose(self) -> Tuple[float, float, float, float]:
        x = round(self.spin_x.value(), 2)
        y = round(self.spin_y.value(), 2)
        z = round(self.spin_z.value(), 2)
        r = round(self.locked_r_val if self.lock_r else self.spin_r.value(), 2)
        return x, y, z, r


class EditAllSlotsDialog(QtWidgets.QDialog):
    """Dialog displaying all 9 slots in an editable table for batch coordinate updates."""

    def __init__(self, grid_model: Grid3x3Model, bridge, parent=None):
        super().__init__(parent)
        self.grid_model = grid_model
        self.bridge = bridge

        self.setWindowTitle("📋 ตารางแก้ไขพิกัดทุกช่อง (Pick & Place Batch Editor)")
        self.resize(750, 420)
        self.setMinimumSize(680, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #12141C;
                color: #E2E8F0;
            }
            QTableWidget {
                background-color: #0E1017;
                gridline-color: #232733;
                border: 1px solid #28303F;
                color: #F1F5F9;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #1B1E28;
                color: #94A3B8;
                font-weight: bold;
                border: 1px solid #232733;
                padding: 4px;
            }
        """)

        self.rows_spinners = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Top Bar with Quick Actions
        top_bar = QtWidgets.QHBoxLayout()
        lbl_info = QtWidgets.QLabel("สามารถพิมพ์แก้ไขพิกัด X, Y, Z, R ของแต่ละช่องได้โดยตรง แล้วกด <b>'บันทึกทั้งหมด'</b>")
        lbl_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
        top_bar.addWidget(lbl_info)
        top_bar.addStretch()

        self.btn_apply_locked_r = QtWidgets.QPushButton(f"🔒 ตั้ง R ทุกช่องเป็น {self.grid_model.locked_r_val:.1f}°")
        self.btn_apply_locked_r.setFixedHeight(26)
        self.btn_apply_locked_r.setStyleSheet("font-size: 10px; background-color: #1E293B; color: #CBD5E1; border: 1px solid #334155; padding: 2px 8px;")
        self.btn_apply_locked_r.clicked.connect(self._on_apply_locked_r_to_table)
        top_bar.addWidget(self.btn_apply_locked_r)

        layout.addLayout(top_bar)

        # 9-row Table
        self.table = QtWidgets.QTableWidget(9, 7)
        self.table.setHorizontalHeaderLabels([
            "ช่อง (Slot)", "บทบาท", "X (mm)", "Y (mm)", "Z (mm)", "R (°)", "ทดสอบ"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)

        ordered_slots = [
            self.grid_model.slots[1], self.grid_model.slots[2], self.grid_model.slots[3],
            self.grid_model.slots[4], self.grid_model.slots[9], self.grid_model.slots[5],
            self.grid_model.slots[6], self.grid_model.slots[7], self.grid_model.slots[8]
        ]

        for row_idx, slot in enumerate(ordered_slots):
            is_center = (slot.slot_id == 9)

            # Slot Name Item
            item_name = QtWidgets.QTableWidgetItem(f"{slot.name}")
            item_name.setFlags(QtCore.Qt.ItemIsEnabled)
            if is_center:
                item_name.setForeground(QtGui.QBrush(QtGui.QColor("#F59E0B")))
                item_name.setFont(QtGui.QFont("", -1, QtGui.QFont.Bold))
            self.table.setItem(row_idx, 0, item_name)

            # Role Item
            role_text = "🏢 จุดวางซ้อน" if is_center else "📦 จุดหยิบ"
            item_role = QtWidgets.QTableWidgetItem(role_text)
            item_role.setFlags(QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 1, item_role)

            # Spinners for X, Y, Z, R
            spin_x = QtWidgets.QDoubleSpinBox()
            spin_x.setRange(-500.0, 500.0)
            spin_x.setDecimals(2)
            spin_x.setValue(slot.x)

            spin_y = QtWidgets.QDoubleSpinBox()
            spin_y.setRange(-500.0, 500.0)
            spin_y.setDecimals(2)
            spin_y.setValue(slot.y)

            spin_z = QtWidgets.QDoubleSpinBox()
            spin_z.setRange(-200.0, 300.0)
            spin_z.setDecimals(2)
            spin_z.setValue(slot.z)

            spin_r = QtWidgets.QDoubleSpinBox()
            spin_r.setRange(-180.0, 180.0)
            spin_r.setDecimals(2)
            r_val = self.grid_model.locked_r_val if self.grid_model.lock_r else slot.r
            spin_r.setValue(r_val)

            self.table.setCellWidget(row_idx, 2, spin_x)
            self.table.setCellWidget(row_idx, 3, spin_y)
            self.table.setCellWidget(row_idx, 4, spin_z)
            self.table.setCellWidget(row_idx, 5, spin_r)

            # Test Button
            btn_test = QtWidgets.QPushButton("🎯")
            btn_test.setFixedSize(30, 24)
            btn_test.setToolTip(f"ทดสอบเลื่อนแขนกลไปยัง {slot.name}")
            btn_test.clicked.connect(lambda _, s_id=slot.slot_id, sx=spin_x, sy=spin_y, sz=spin_z, sr=spin_r:
                                     self._test_row(s_id, sx.value(), sy.value(), sz.value(), sr.value()))
            self.table.setCellWidget(row_idx, 6, btn_test)

            self.rows_spinners[slot.slot_id] = (spin_x, spin_y, spin_z, spin_r)

        layout.addWidget(self.table)

        # Bottom Confirmation Buttons
        bot_box = QtWidgets.QHBoxLayout()
        bot_box.setSpacing(8)

        self.btn_save = QtWidgets.QPushButton("💾 บันทึกทั้งหมด (Save All)")
        self.btn_save.setObjectName("btn_action_green")
        self.btn_save.setFixedHeight(32)
        self.btn_save.clicked.connect(self.accept)

        self.btn_cancel = QtWidgets.QPushButton("❌ ยกเลิก")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setStyleSheet("background-color: #374151;")
        self.btn_cancel.clicked.connect(self.reject)

        bot_box.addStretch()
        bot_box.addWidget(self.btn_cancel)
        bot_box.addWidget(self.btn_save)
        layout.addLayout(bot_box)

    def _on_apply_locked_r_to_table(self):
        locked_r = self.grid_model.locked_r_val
        for spin_x, spin_y, spin_z, spin_r in self.rows_spinners.values():
            spin_r.setValue(locked_r)

    def _test_row(self, slot_id: int, x: float, y: float, z: float, r: float):
        z_safe = self.grid_model.z_safe
        self.bridge.send_ptp(x, y, z_safe, r, mode=2)
        QtCore.QTimer.singleShot(1100, lambda: self.bridge.send_ptp(x, y, z, r, mode=2))

    def get_all_poses(self) -> Dict[int, Tuple[float, float, float, float]]:
        result = {}
        for s_id, (sx, sy, sz, sr) in self.rows_spinners.items():
            result[s_id] = (round(sx.value(), 2), round(sy.value(), 2), round(sz.value(), 2), round(sr.value(), 2))
        return result


class SlotTeachingCell(QtWidgets.QFrame):
    """Visual teaching card for an individual slot inside the 3x3 grid."""

    sig_record_clicked = Signal(int)
    sig_edit_clicked = Signal(int)
    sig_test_clicked = Signal(int)
    sig_color_changed = Signal(int, str)
    sig_scan_color_clicked = Signal(int)

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
            color_row = QtWidgets.QHBoxLayout()
            color_row.setSpacing(3)
            self.combo_color = QtWidgets.QComboBox()
            self.combo_color.setFixedHeight(22)
            self.combo_color.setStyleSheet("font-size: 10px; padding: 1px 4px;")
            for key, info in COLOR_PALETTE.items():
                self.combo_color.addItem(info["name"], key)
            idx = self.combo_color.findData(self.slot.color)
            if idx >= 0:
                self.combo_color.setCurrentIndex(idx)
            self.combo_color.currentIndexChanged.connect(self._on_color_changed)

            self.btn_scan_color = QtWidgets.QPushButton("📷")
            self.btn_scan_color.setFixedSize(24, 22)
            self.btn_scan_color.setToolTip(f"📸 ถ่ายภาพสแกนสีเฉพาะ {self.slot.name}")
            self.btn_scan_color.setStyleSheet("font-size: 10px; padding: 0; background-color: #1E293B; border: 1px solid #334155;")
            self.btn_scan_color.clicked.connect(lambda: self.sig_scan_color_clicked.emit(self.slot.slot_id))

            color_row.addWidget(self.combo_color, 1)
            color_row.addWidget(self.btn_scan_color)
            layout.addLayout(color_row)
        else:
            self.lbl_center_desc = QtWidgets.QLabel("ฐานวางซ้อน (Base Stacking)")
            self.lbl_center_desc.setStyleSheet("font-size: 10px; color: #FBBF24;")
            layout.addWidget(self.lbl_center_desc)

        # Coordinates Display Box (Clickable to edit)
        self.coord_box = QtWidgets.QFrame()
        self.coord_box.setStyleSheet("background-color: #0A0B0E; border: 1px solid #232733; border-radius: 4px; padding: 2px;")
        self.coord_box.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.coord_box.setToolTip("คลิกเพื่อแก้ไขพิกัด X, Y, Z, R")
        self.coord_box.mousePressEvent = lambda event: self.sig_edit_clicked.emit(self.slot.slot_id)

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

        # Action Buttons: Record & Edit & Test
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.setSpacing(3)

        self.btn_record = QtWidgets.QPushButton("📍 บันทึก")
        self.btn_record.setObjectName("btn_action_green")
        self.btn_record.setFixedHeight(24)
        self.btn_record.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 4px;")
        self.btn_record.setToolTip(f"บันทึกพิกัดแขนกลขณะนี้ลงใน {self.slot.name}")
        self.btn_record.clicked.connect(lambda: self.sig_record_clicked.emit(self.slot.slot_id))

        self.btn_edit = QtWidgets.QPushButton("✏️ แก้ไข")
        self.btn_edit.setFixedHeight(24)
        self.btn_edit.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 4px; background-color: #1E293B; color: #93C5FD; border: 1px solid #3B82F6;")
        self.btn_edit.setToolTip("แก้ไขตัวเลขพิกัด X, Y, Z, R ด้วยตนเอง")
        self.btn_edit.clicked.connect(lambda: self.sig_edit_clicked.emit(self.slot.slot_id))

        self.btn_test = QtWidgets.QPushButton("🎯 ทดสอบ")
        self.btn_test.setFixedHeight(24)
        self.btn_test.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        self.btn_test.setToolTip("สั่งแขนกลเลื่อนมาทดสอบความแม่นยำที่ช่องนี้")
        self.btn_test.clicked.connect(lambda: self.sig_test_clicked.emit(self.slot.slot_id))

        btn_box.addWidget(self.btn_record, 1)
        btn_box.addWidget(self.btn_edit, 1)
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

    def refresh_pose(self, lock_r: bool = False):
        self.lbl_xy.setText(f"X:{self.slot.x:.1f}  Y:{self.slot.y:.1f}")
        r_str = f"R:{self.slot.r:.1f}°"
        if lock_r:
            r_str = f"🔒 {r_str}"
        self.lbl_zr.setText(f"Z:{self.slot.z:.1f}  {r_str}")

        # Flash green feedback momentarily
        self.coord_box.setStyleSheet("background-color: #064E3B; border: 1px solid #10B981; border-radius: 4px; padding: 2px;")
        QtCore.QTimer.singleShot(600, lambda: self.coord_box.setStyleSheet(
            "background-color: #0A0B0E; border: 1px solid #232733; border-radius: 4px; padding: 2px;"
        ))

    def refresh_color(self):
        """Update combobox to match current slot.color in model."""
        if not self.is_center and hasattr(self, "combo_color"):
            self.combo_color.blockSignals(True)
            idx = self.combo_color.findData(self.slot.color)
            if idx >= 0:
                self.combo_color.setCurrentIndex(idx)
            self.combo_color.blockSignals(False)


class GridTeachingTab(QtWidgets.QWidget):
    """Interactive 3x3 Teaching Tab where each cell has Record, Edit, and Test buttons."""

    sig_model_updated = Signal()

    def __init__(self, bridge, grid_model: Grid3x3Model, camera_widget=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.grid_model = grid_model
        self.camera_widget = camera_widget

        self._curr_robot_pose = (220.0, 0.0, 50.0, 0.0)
        self.cells: dict = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(8)

        # Top Bar: Arm Telemetry, Instructions, and R Lock Controls
        top_bar = QtWidgets.QFrame()
        top_bar.setStyleSheet("background-color: #161822; border: 1px solid #28303F; border-radius: 6px; padding: 4px 8px;")
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 4, 6, 4)
        top_layout.setSpacing(10)

        instr_lbl = QtWidgets.QLabel("✋ <b>วิธี Teach:</b> ช่องหยิบ (S1-S8) แตะ <b>ผิวก้อน</b> | ช่องวาง (Center) แตะ <b>ฐานโต๊ะ</b> แล้วกด <b>'📍 บันทึก'</b> หรือกด <b>'✏️ แก้ไข'</b>")
        instr_lbl.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        top_layout.addWidget(instr_lbl)

        top_layout.addStretch()

        # Lock R Axis Controls (Normal theme styling)
        r_lock_frame = QtWidgets.QFrame()
        r_lock_frame.setStyleSheet("background-color: #0F121A; border: 1px solid #28303F; border-radius: 4px; padding: 2px 6px;")
        r_lock_layout = QtWidgets.QHBoxLayout(r_lock_frame)
        r_lock_layout.setContentsMargins(4, 1, 4, 1)
        r_lock_layout.setSpacing(6)

        self.chk_lock_r = QtWidgets.QCheckBox("🔒 ล็อกแกน R:")
        self.chk_lock_r.setChecked(self.grid_model.lock_r)
        self.chk_lock_r.setStyleSheet("font-weight: 600; color: #CBD5E1; font-size: 11px;")
        self.chk_lock_r.setToolTip("เมื่อเปิดใช้งาน พิกัด R จะถูกล็อกไว้ตามค่าที่ระบุตลอดเวลา ทั้งตอนบันทึกและรันภารกิจ")
        r_lock_layout.addWidget(self.chk_lock_r)

        self.spin_lock_r = QtWidgets.QDoubleSpinBox()
        self.spin_lock_r.setRange(-180.0, 180.0)
        self.spin_lock_r.setDecimals(1)
        self.spin_lock_r.setSingleStep(1.0)
        self.spin_lock_r.setValue(self.grid_model.locked_r_val)
        self.spin_lock_r.setSuffix("°")
        self.spin_lock_r.setFixedWidth(68)
        self.spin_lock_r.setFixedHeight(24)
        self.spin_lock_r.setToolTip("มุมองศา R ที่ต้องการล็อกให้เท่ากันทุกจุด (ปกติ 0.0°)")
        r_lock_layout.addWidget(self.spin_lock_r)

        self.btn_apply_r = QtWidgets.QPushButton("⚡ ปรับทุกช่อง")
        self.btn_apply_r.setFixedHeight(24)
        self.btn_apply_r.setStyleSheet("font-size: 10px; font-weight: 600; background-color: #1E293B; color: #CBD5E1; border: 1px solid #334155; padding: 1px 6px;")
        self.btn_apply_r.setToolTip("นำค่าองศา R นี้ไปปรับใช้กับทุกช่อง (S1-S8 และ Center)")
        r_lock_layout.addWidget(self.btn_apply_r)

        top_layout.addWidget(r_lock_frame)

        # Camera Scan Button
        self.btn_camera_scan_all = QtWidgets.QPushButton("📸 สแกนสีจากกล้อง")
        self.btn_camera_scan_all.setFixedHeight(26)
        self.btn_camera_scan_all.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: #6EE7B7;
                border: 1px solid #10B981;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #047857; color: #FFFFFF; }
        """)
        self.btn_camera_scan_all.setToolTip("เปิดหน้าต่างกล้องเพื่อตรวจจับและบันทึกสีก้อนลูกบาศก์บนสนาม 3x3 ทั้งหมดแบบอัตโนมัติ")
        self.btn_camera_scan_all.clicked.connect(self._on_scan_all_colors)
        top_layout.addWidget(self.btn_camera_scan_all)

        # Real-time Telemetry Badges
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
            cell.sig_edit_clicked.connect(self._on_edit_cell)
            cell.sig_test_clicked.connect(self._on_test_cell)
            cell.sig_color_changed.connect(self._on_cell_color_changed)
            cell.sig_scan_color_clicked.connect(self._on_scan_slot_color)
            self.cells[slot_id] = cell
            grid_layout.addWidget(cell, slot.row, slot.col)

        root_layout.addWidget(grid_container, 1)

        # Bottom: Persistence & Batch Edit Actions
        bot_bar = QtWidgets.QHBoxLayout()
        bot_bar.setSpacing(8)

        self.btn_edit_all = QtWidgets.QPushButton("📋 ตารางแก้ไขพิกัดทุกช่อง (Batch Edit)")
        self.btn_edit_all.setFixedHeight(28)
        self.btn_edit_all.setStyleSheet("background-color: #1E293B; color: #93C5FD; border: 1px solid #3B82F6; font-weight: bold;")
        self.btn_edit_all.setToolTip("เปิดตารางรวมแก้ไขพิกัด X, Y, Z, R ของทั้ง 9 ช่องพร้อมกัน")
        bot_bar.addWidget(self.btn_edit_all)

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

        self.lbl_feedback = QtWidgets.QLabel("พร้อมบันทึกหรือแก้ไขพิกัด")
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
        self.chk_lock_r.toggled.connect(self._on_lock_r_toggled)
        self.spin_lock_r.valueChanged.connect(self._on_lock_r_value_changed)
        self.btn_apply_r.clicked.connect(self._on_apply_r_all)

        self.btn_edit_all.clicked.connect(self._on_edit_all_dialog)
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

    def _on_lock_r_toggled(self, checked: bool):
        self.grid_model.lock_r = checked
        for cell in self.cells.values():
            cell.refresh_pose(lock_r=checked)
        status_str = f"เปิดการล็อกแกน R ที่ {self.grid_model.locked_r_val:.1f}°" if checked else "ปลดการล็อกแกน R"
        self.lbl_feedback.setText(f"🔒 {status_str}")

    def _on_lock_r_value_changed(self, val: float):
        self.grid_model.locked_r_val = round(float(val), 2)
        if self.grid_model.lock_r:
            self.lbl_feedback.setText(f"🔒 ค่าล็อกแกน R อัปเดตเป็น {val:.1f}° (กด '⚡ ปรับทุกช่อง' เพื่อใช้งานกับพิกัดเดิม)")

    def _on_apply_r_all(self):
        val = round(self.spin_lock_r.value(), 2)
        self.grid_model.apply_locked_r_to_all(val)
        for cell in self.cells.values():
            cell.refresh_pose(lock_r=self.grid_model.lock_r)
        self.sig_model_updated.emit()
        msg = f"ปรับมุม R ทุกช่อง (S1-S8 และ Center) เป็น {val:.1f}° เรียบร้อย"
        self.lbl_feedback.setText(f"⚡ {msg}")
        self.bridge.sig_log.emit("CMD", msg)

    def _on_record_cell(self, slot_id: int):
        x, y, z, curr_r = self._curr_robot_pose
        r = self.grid_model.locked_r_val if self.grid_model.lock_r else curr_r
        self.grid_model.set_slot_pose(slot_id, x, y, z, r)
        cell = self.cells.get(slot_id)
        if cell:
            cell.refresh_pose(lock_r=self.grid_model.lock_r)
        self.sig_model_updated.emit()
        slot = self.grid_model.get_slot(slot_id)
        lock_note = " (🔒 R ล็อก)" if self.grid_model.lock_r else ""
        msg = f"บันทึก {slot.name}: X={slot.x:.1f}, Y={slot.y:.1f}, Z={slot.z:.1f}, R={slot.r:.1f}°{lock_note} เรียบร้อย"
        self.lbl_feedback.setText(f"✅ {msg}")
        self.bridge.sig_log.emit("CMD", msg)

    def _on_edit_cell(self, slot_id: int):
        slot = self.grid_model.get_slot(slot_id)
        if not slot:
            return

        dlg = EditSlotPoseDialog(
            slot=slot,
            curr_pose=self._curr_robot_pose,
            bridge=self.bridge,
            z_safe=self.grid_model.z_safe,
            lock_r=self.grid_model.lock_r,
            locked_r_val=self.grid_model.locked_r_val,
            parent=self
        )

        if dlg.exec() == QtWidgets.QDialog.Accepted:
            new_x, new_y, new_z, new_r = dlg.get_pose()
            self.grid_model.set_slot_pose(slot_id, new_x, new_y, new_z, new_r)
            cell = self.cells.get(slot_id)
            if cell:
                cell.refresh_pose(lock_r=self.grid_model.lock_r)
            self.sig_model_updated.emit()
            msg = f"แก้ไขพิกัด {slot.name}: X={new_x:.1f}, Y={new_y:.1f}, Z={new_z:.1f}, R={new_r:.1f}° สำเร็จ"
            self.lbl_feedback.setText(f"✏️ {msg}")
            self.bridge.sig_log.emit("CMD", msg)

    def _on_edit_all_dialog(self):
        dlg = EditAllSlotsDialog(self.grid_model, self.bridge, parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            updated_poses = dlg.get_all_poses()
            for s_id, (x, y, z, r) in updated_poses.items():
                self.grid_model.set_slot_pose(s_id, x, y, z, r)
                cell = self.cells.get(s_id)
                if cell:
                    cell.refresh_pose(lock_r=self.grid_model.lock_r)
            self.sig_model_updated.emit()
            msg = "แก้ไขพิกัดทุกช่องสำเร็จเรียบร้อย"
            self.lbl_feedback.setText(f"💾 {msg}")
            self.bridge.sig_log.emit("CMD", msg)

    def _on_test_cell(self, slot_id: int):
        slot = self.grid_model.get_slot(slot_id)
        if slot:
            z_safe = self.grid_model.z_safe
            r_val = self.grid_model.locked_r_val if self.grid_model.lock_r else slot.r
            self.lbl_feedback.setText(f"🚀 เคลื่อนที่ไปทดสอบที่ {slot.name}...")
            self.bridge.send_ptp(slot.x, slot.y, z_safe, r_val, mode=2)
            QtCore.QTimer.singleShot(1100, lambda: self.bridge.send_ptp(slot.x, slot.y, slot.z, r_val, mode=2))

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
                self.chk_lock_r.blockSignals(True)
                self.chk_lock_r.setChecked(self.grid_model.lock_r)
                self.chk_lock_r.blockSignals(False)

                self.spin_lock_r.blockSignals(True)
                self.spin_lock_r.setValue(self.grid_model.locked_r_val)
                self.spin_lock_r.blockSignals(False)

                for s_id, cell in self.cells.items():
                    cell.slot = self.grid_model.get_slot(s_id)
                    cell.refresh_pose(lock_r=self.grid_model.lock_r)
                    if not cell.is_center and hasattr(cell, "combo_color"):
                        idx = cell.combo_color.findData(cell.slot.color)
                        if idx >= 0:
                            cell.combo_color.setCurrentIndex(idx)
                self.sig_model_updated.emit()
                self.lbl_feedback.setText("📂 โหลดไฟล์พิกัดสำเร็จ")
                self.bridge.sig_log.emit("INFO", f"Loaded calibration from {path}")

    def _on_reset_defaults(self):
        self.grid_model._init_default_slots()
        self.chk_lock_r.blockSignals(True)
        self.chk_lock_r.setChecked(self.grid_model.lock_r)
        self.chk_lock_r.blockSignals(False)

        self.spin_lock_r.blockSignals(True)
        self.spin_lock_r.setValue(self.grid_model.locked_r_val)
        self.spin_lock_r.blockSignals(False)

        for s_id, cell in self.cells.items():
            cell.slot = self.grid_model.get_slot(s_id)
            cell.refresh_pose(lock_r=self.grid_model.lock_r)
        self.sig_model_updated.emit()
        self.lbl_feedback.setText("🔄 คืนค่าพิกัดเริ่มต้นสำเร็จ")
        self.bridge.sig_log.emit("INFO", "Reset grid calibration to default.")

    def _on_scan_all_colors(self):
        from ..widgets.color_capture_dialog import ColorCaptureDialog
        dialog = ColorCaptureDialog(self.grid_model, camera_widget=self.camera_widget, parent=self)
        if dialog.exec() if hasattr(dialog, "exec") else dialog.exec_():
            for s_id, cell in self.cells.items():
                cell.slot = self.grid_model.get_slot(s_id)
                cell.refresh_color()
            self.sig_model_updated.emit()
            msg = "สแกนและบันทึกสีของลูกบาศก์บนสนาม 3x3 จากกล้องเรียบร้อย (พิกัดแขนกลคงเดิม 100%)"
            self.lbl_feedback.setText(f"📸 {msg}")
            self.bridge.sig_log.emit("INFO", msg)

    def _on_scan_slot_color(self, slot_id: int):
        from ..widgets.color_capture_dialog import ColorCaptureDialog
        dialog = ColorCaptureDialog(self.grid_model, camera_widget=self.camera_widget, target_slot_id=slot_id, parent=self)
        if dialog.exec() if hasattr(dialog, "exec") else dialog.exec_():
            for s_id, cell in self.cells.items():
                cell.slot = self.grid_model.get_slot(s_id)
                cell.refresh_color()
            self.sig_model_updated.emit()
            msg = f"สแกนและบันทึกสีของช่อง {slot_id} เรียบร้อย (พิกัดแขนกลคงเดิม 100%)"
            self.lbl_feedback.setText(f"📸 {msg}")
            self.bridge.sig_log.emit("INFO", msg)
