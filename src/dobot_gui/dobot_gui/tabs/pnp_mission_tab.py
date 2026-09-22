"""
Main Pick & Place and Color Stacking Mission Tab
Hosts the 3x3 interactive arena grid, color sequence builder,
real-time progress, and mission execution controls.
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from dobot_driver.pnp import Grid3x3Model, ColorStackController, COLOR_PALETTE
from ..widgets.grid_3x3_widget import Grid3x3Widget


class PnpMissionTab(QtWidgets.QWidget):
    """Primary tab for configuring and running 3x3 Cube Stacking Pick & Place missions."""

    def __init__(self, bridge, grid_model: Grid3x3Model, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.grid_model = grid_model

        # Core controller
        self.controller = ColorStackController(self.bridge._driver, self.grid_model)
        self.controller.set_callbacks(
            on_state=self._on_controller_state,
            on_layer=self._on_controller_layer,
            on_finished=self._on_controller_finished,
            on_log=self._on_controller_log
        )

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left Column: Interactive 3x3 Grid Widget & Arena Control
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(10)

        grp_arena = QtWidgets.QGroupBox("สนามตาราง 3x3 และเสาซ้อนลูกบาศก์ (3x3 Arena & Center Stack)")
        arena_layout = QtWidgets.QVBoxLayout(grp_arena)
        arena_layout.setContentsMargins(12, 12, 12, 12)

        # 3x3 Grid Widget
        self.grid_widget = Grid3x3Widget(self.grid_model)
        arena_layout.addWidget(self.grid_widget, 1)

        # Quick Arena Actions
        arena_btn_box = QtWidgets.QHBoxLayout()
        self.btn_reset_arena = QtWidgets.QPushButton("🔄 รีเซ็ตสนาม (เติมลูกบาศก์)")
        self.btn_reset_arena.setToolTip("ตั้งค่าให้ทุกลูกบาศก์กลับมาวางพร้อมหยิบบนสนาม และเคลียร์เสากลาง")
        arena_btn_box.addWidget(self.btn_reset_arena)
        arena_layout.addLayout(arena_btn_box)

        left_panel.addWidget(grp_arena, 1)
        main_layout.addLayout(left_panel, 1)

        # Right Column: Mission Configuration & Controls
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(12)

        # Group: Stacking Plan by Color
        grp_plan = QtWidgets.QGroupBox("ลำดับการวางซ้อนเป็นชั้นๆ (Layer Stacking Plan)")
        plan_layout = QtWidgets.QVBoxLayout(grp_plan)
        plan_layout.setSpacing(6)
        plan_layout.setContentsMargins(10, 10, 10, 10)

        # Mode Selection
        mode_box = QtWidgets.QHBoxLayout()
        self.rb_mode_color = QtWidgets.QRadioButton("ซ้อนตามลำดับสี (Color Sequence)")
        self.rb_mode_slot = QtWidgets.QRadioButton("ซ้อนตามลำดับช่อง (Slot Sequence)")
        self.rb_mode_color.setChecked(True)
        mode_box.addWidget(self.rb_mode_color)
        mode_box.addWidget(self.rb_mode_slot)
        plan_layout.addLayout(mode_box)

        # Layer List Container
        self.layer_scroll = QtWidgets.QScrollArea()
        self.layer_scroll.setWidgetResizable(True)
        self.layer_scroll.setFixedHeight(105)
        self.layer_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #10121A;
                border: 1px solid #28303F;
                border-radius: 5px;
            }
        """)
        self.layer_container = QtWidgets.QWidget()
        self.layer_layout = QtWidgets.QVBoxLayout(self.layer_container)
        self.layer_layout.setSpacing(3)
        self.layer_layout.setContentsMargins(3, 3, 3, 3)
        self.layer_layout.setAlignment(QtCore.Qt.AlignTop)
        self.layer_scroll.setWidget(self.layer_container)
        plan_layout.addWidget(self.layer_scroll)

        # Buttons to Add / Remove Layers
        layer_btn_box = QtWidgets.QHBoxLayout()
        layer_btn_box.setSpacing(6)
        self.btn_add_layer = QtWidgets.QPushButton("➕ เพิ่มชั้น (Add Layer)")
        self.btn_remove_layer = QtWidgets.QPushButton("➖ ลบชั้น (Remove Layer)")
        layer_btn_box.addWidget(self.btn_add_layer)
        layer_btn_box.addWidget(self.btn_remove_layer)
        plan_layout.addLayout(layer_btn_box)

        # Height Settings & Center Z Reference (Compact 2x2 Grid)
        param_grid = QtWidgets.QGridLayout()
        param_grid.setContentsMargins(0, 0, 0, 0)
        param_grid.setSpacing(6)

        self.spin_cube_h = QtWidgets.QDoubleSpinBox()
        self.spin_cube_h.setRange(5.0, 100.0)
        self.spin_cube_h.setValue(self.grid_model.cube_height)
        self.spin_cube_h.setSuffix(" mm")

        self.spin_z_safe = QtWidgets.QDoubleSpinBox()
        self.spin_z_safe.setRange(10.0, 200.0)
        self.spin_z_safe.setValue(self.grid_model.z_safe)
        self.spin_z_safe.setSuffix(" mm")

        self.combo_center_ref = QtWidgets.QComboBox()
        self.combo_center_ref.addItem("📍 ฐานโต๊ะ (Base Ground)", "base")
        self.combo_center_ref.addItem("📦 ผิวก้อนแรก (Top of 1st)", "top_of_cube")
        idx_ref = self.combo_center_ref.findData(self.grid_model.center_z_ref)
        if idx_ref >= 0:
            self.combo_center_ref.setCurrentIndex(idx_ref)

        self.spin_place_offset = QtWidgets.QDoubleSpinBox()
        self.spin_place_offset.setRange(-20.0, 20.0)
        self.spin_place_offset.setSingleStep(0.5)
        self.spin_place_offset.setValue(self.grid_model.place_z_offset)
        self.spin_place_offset.setSuffix(" mm")
        self.spin_place_offset.setToolTip("ปรับชดเชยความสูงการวางให้พอดีกับหัวดูด (Fine-tuning Z Offset)")

        lbl_cube_h = QtWidgets.QLabel("สูงลูกบาศก์ (h):")
        lbl_cube_h.setStyleSheet("font-size: 10px;")
        lbl_z_safe = QtWidgets.QLabel("ยกปลอดภัย (Z):")
        lbl_z_safe.setStyleSheet("font-size: 10px;")
        lbl_center_ref = QtWidgets.QLabel("อ้างอิง Center:")
        lbl_center_ref.setStyleSheet("font-size: 10px;")
        lbl_offset = QtWidgets.QLabel("ชดเชย Z (Offset):")
        lbl_offset.setStyleSheet("font-size: 10px;")

        param_grid.addWidget(lbl_cube_h, 0, 0)
        param_grid.addWidget(self.spin_cube_h, 0, 1)
        param_grid.addWidget(lbl_z_safe, 0, 2)
        param_grid.addWidget(self.spin_z_safe, 0, 3)

        param_grid.addWidget(lbl_center_ref, 1, 0)
        param_grid.addWidget(self.combo_center_ref, 1, 1)
        param_grid.addWidget(lbl_offset, 1, 2)
        param_grid.addWidget(self.spin_place_offset, 1, 3)

        plan_layout.addLayout(param_grid)

        right_panel.addWidget(grp_plan)

        # Group: Mission Execution & Progress
        grp_exec = QtWidgets.QGroupBox("ควบคุมภารกิจและความคืบหน้า (Execution Controls)")
        exec_layout = QtWidgets.QVBoxLayout(grp_exec)
        exec_layout.setSpacing(6)
        exec_layout.setContentsMargins(10, 10, 10, 10)

        # Buttons: Start / Pause / Stop
        btn_ctrl_box = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("▶️ START MISSION")
        self.btn_start.setObjectName("btn_action_green")
        self.btn_start.setMinimumHeight(30)

        self.btn_pause = QtWidgets.QPushButton("⏸️ PAUSE")
        self.btn_pause.setObjectName("btn_action_amber")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setMinimumHeight(30)

        self.btn_stop = QtWidgets.QPushButton("⏹️ STOP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(30)

        btn_ctrl_box.addWidget(self.btn_start)
        btn_ctrl_box.addWidget(self.btn_pause)
        btn_ctrl_box.addWidget(self.btn_stop)
        exec_layout.addLayout(btn_ctrl_box)

        # Progress Bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #121318;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 3px;
            }
        """)
        exec_layout.addWidget(self.progress_bar)

        # Status Label
        self.lbl_mission_status = QtWidgets.QLabel("สถานะ: พร้อมเริ่มภารกิจ (Ready)")
        self.lbl_mission_status.setStyleSheet("font-weight: bold; color: #60A5FA; font-size: 11px;")
        exec_layout.addWidget(self.lbl_mission_status)

        right_panel.addWidget(grp_exec)
        right_panel.addStretch()
        main_layout.addLayout(right_panel, 1)

        # Initialize default 3 layers
        self.layer_combos = []
        self._add_layer_row("red")
        self._add_layer_row("blue")
        self._add_layer_row("green")

    def _populate_combo(self, combo: QtWidgets.QComboBox, default_val=None):
        """Populate layer combo with colors or slot IDs depending on active mode."""
        combo.blockSignals(True)
        combo.clear()
        if self.rb_mode_color.isChecked():
            for key, info in COLOR_PALETTE.items():
                combo.addItem(info["name"], key)
            target = str(default_val) if default_val is not None else "red"
            idx = combo.findData(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        else:
            for s in self.grid_model.perimeter_slots:
                colr_name = COLOR_PALETTE.get(s.color, {}).get("name", s.color)
                combo.addItem(f"ช่อง {s.slot_id} ({colr_name})", s.slot_id)
            target = int(default_val) if (default_val is not None and isinstance(default_val, int)) else 1
            idx = combo.findData(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _add_layer_row(self, default_val=None):
        layer_num = len(self.layer_combos) + 1
        if layer_num > 8:
            return  # Max 8 layers (8 perimeter slots)

        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        lbl = QtWidgets.QLabel(f"ชั้นที่ {layer_num}:")
        lbl.setFixedWidth(50)
        lbl.setStyleSheet("font-weight: bold; font-size: 11px;")

        combo = QtWidgets.QComboBox()
        if default_val is not None:
            def_val = default_val
        elif self.rb_mode_slot.isChecked():
            def_val = layer_num
        else:
            used_colors = {c.currentData() for _, c, *_ in self.layer_combos}
            def_val = next((k for k in COLOR_PALETTE if k not in used_colors), "red")
        self._populate_combo(combo, def_val)
        combo.currentIndexChanged.connect(self._on_layer_combo_changed)

        lbl_z = QtWidgets.QLabel()
        lbl_z.setStyleSheet("""
            background-color: #0F172A;
            color: #38BDF8;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border: 1px solid #1E293B;
            border-radius: 4px;
        """)
        lbl_z.setAlignment(QtCore.Qt.AlignCenter)

        # Up and Down Reorder Buttons
        btn_up = QtWidgets.QPushButton("▲")
        btn_up.setFixedSize(20, 20)
        btn_up.setToolTip("เลื่อนขึ้น (หยิบก่อน)")
        btn_up.setStyleSheet("font-size: 8px; padding: 0; background-color: #1E293B;")
        btn_up.clicked.connect(lambda: self._move_layer(row_widget, -1))

        btn_down = QtWidgets.QPushButton("▼")
        btn_down.setFixedSize(20, 20)
        btn_down.setToolTip("เลื่อนลง (หยิบทีกรอบ)")
        btn_down.setStyleSheet("font-size: 8px; padding: 0; background-color: #1E293B;")
        btn_down.clicked.connect(lambda: self._move_layer(row_widget, 1))

        btn_del = QtWidgets.QPushButton("✕")
        btn_del.setFixedSize(20, 20)
        btn_del.setToolTip("ลบชั้นนี้")
        btn_del.setStyleSheet("font-size: 9px; padding: 0; background-color: #371B1B; color: #F87171;")
        btn_del.clicked.connect(lambda: self._remove_specific_layer(row_widget))

        row_layout.addWidget(lbl)
        row_layout.addWidget(combo, 1)
        row_layout.addWidget(lbl_z)
        row_layout.addWidget(btn_up)
        row_layout.addWidget(btn_down)
        row_layout.addWidget(btn_del)

        self.layer_layout.addWidget(row_widget)
        self.layer_combos.append((row_widget, combo, lbl_z, lbl))
        self._update_layer_z_previews()

    def _remove_layer_row(self):
        if len(self.layer_combos) > 1:
            row_widget, combo, lbl_z, lbl = self.layer_combos.pop()
            row_widget.deleteLater()
            self._update_layer_z_previews()

    def _remove_specific_layer(self, row_widget):
        """Remove a specific layer row."""
        if len(self.layer_combos) <= 1:
            return
        idx = -1
        for i, (w, *_) in enumerate(self.layer_combos):
            if w == row_widget:
                idx = i
                break
        if idx != -1:
            w, combo, lbl_z, lbl = self.layer_combos.pop(idx)
            w.deleteLater()
            for i, (_, _, _, l) in enumerate(self.layer_combos):
                l.setText(f"ชั้นที่ {i + 1}:")
            self._update_layer_z_previews()

    def _move_layer(self, row_widget, direction: int):
        """Move a layer row up (-1) or down (+1)."""
        idx = -1
        for i, (w, *_) in enumerate(self.layer_combos):
            if w == row_widget:
                idx = i
                break
        if idx == -1:
            return

        new_idx = idx + direction
        if 0 <= new_idx < len(self.layer_combos):
            item = self.layer_combos.pop(idx)
            self.layer_combos.insert(new_idx, item)

            for i, (w, _, _, l) in enumerate(self.layer_combos):
                self.layer_layout.removeWidget(w)
                self.layer_layout.addWidget(w)
                l.setText(f"ชั้นที่ {i + 1}:")

            self._update_layer_z_previews()

    def _on_layer_combo_changed(self):
        pass

    def _on_grid_slot_clicked(self, slot_id: int):
        """Handle user clicking a slot tile on the interactive 3x3 arena."""
        if slot_id == 9:
            return  # Center slot
        if len(self.layer_combos) >= 8:
            return  # Max 8 layers
        if self.rb_mode_slot.isChecked():
            self._add_layer_row(default_val=slot_id)
            self.lbl_mission_status.setText(f"สถานะ: ➕ เพิ่มช่อง {slot_id} เป็นชั้นที่ {len(self.layer_combos)}")
        elif self.rb_mode_color.isChecked():
            slot = self.grid_model.get_slot(slot_id)
            if slot:
                c_name = COLOR_PALETTE.get(slot.color, {}).get("name", slot.color)
                self._add_layer_row(default_val=slot.color)
                self.lbl_mission_status.setText(f"สถานะ: ➕ เพิ่มสี {c_name} เป็นชั้นที่ {len(self.layer_combos)}")

    def _update_layer_z_previews(self):
        """Update live target Z badges for all configured layers."""
        for idx, (_, _, lbl_z, *_) in enumerate(self.layer_combos):
            target_z = self.grid_model.calculate_place_z(idx)
            lbl_z.setText(f"🎯 Z วาง: {target_z:.1f} mm")

    def sync_from_model(self):
        """Sync UI controls and layer previews from current grid model."""
        self.spin_cube_h.blockSignals(True)
        self.spin_cube_h.setValue(self.grid_model.cube_height)
        self.spin_cube_h.blockSignals(False)

        self.spin_z_safe.blockSignals(True)
        self.spin_z_safe.setValue(self.grid_model.z_safe)
        self.spin_z_safe.blockSignals(False)

        self.combo_center_ref.blockSignals(True)
        idx_ref = self.combo_center_ref.findData(self.grid_model.center_z_ref)
        if idx_ref >= 0:
            self.combo_center_ref.setCurrentIndex(idx_ref)
        self.combo_center_ref.blockSignals(False)

        self.spin_place_offset.blockSignals(True)
        self.spin_place_offset.setValue(self.grid_model.place_z_offset)
        self.spin_place_offset.blockSignals(False)

        self.grid_widget.refresh()
        self._update_layer_z_previews()

    def _connect_signals(self):
        self.btn_reset_arena.clicked.connect(self._on_reset_arena)
        self.btn_add_layer.clicked.connect(lambda: self._add_layer_row())
        self.btn_remove_layer.clicked.connect(self._remove_layer_row)
        self.rb_mode_color.toggled.connect(self._on_mode_toggled)
        self.grid_widget.sig_slot_selected.connect(self._on_grid_slot_clicked)

        self.spin_cube_h.valueChanged.connect(self._on_cube_h_changed)
        self.spin_z_safe.valueChanged.connect(self._on_z_safe_changed)
        self.combo_center_ref.currentIndexChanged.connect(self._on_center_ref_changed)
        self.spin_place_offset.valueChanged.connect(self._on_place_offset_changed)

        self.btn_start.clicked.connect(self._on_start_mission)
        self.btn_pause.clicked.connect(self._on_pause_mission)
        self.btn_stop.clicked.connect(self._on_stop_mission)

    def _on_mode_toggled(self):
        """Update items in all layer combos when user switches between Color and Slot mode."""
        is_slot = self.rb_mode_slot.isChecked()
        for idx, (_, combo, *_) in enumerate(self.layer_combos):
            if is_slot:
                self._populate_combo(combo, default_val=(idx + 1))
            else:
                default_colors = ["red", "blue", "green", "yellow", "orange", "purple", "cyan", "white"]
                c_val = default_colors[idx % len(default_colors)]
                self._populate_combo(combo, default_val=c_val)

    def _on_cube_h_changed(self, val: float):
        self.grid_model.cube_height = val
        self._update_layer_z_previews()

    def _on_z_safe_changed(self, val: float):
        self.grid_model.z_safe = val

    def _on_center_ref_changed(self, idx: int):
        self.grid_model.center_z_ref = self.combo_center_ref.currentData()
        self._update_layer_z_previews()

    def _on_place_offset_changed(self, val: float):
        self.grid_model.place_z_offset = val
        self._update_layer_z_previews()

    def _on_reset_arena(self):
        self.grid_model.reset_arena()
        self.grid_widget.refresh()
        self.progress_bar.setValue(0)
        self.lbl_mission_status.setText("สถานะ: รีเซ็ตสนามเรียบร้อย พร้อมเริ่มงาน")
        self._update_layer_z_previews()

    def _on_start_mission(self):
        # Update driver reference
        self.controller.driver = self.bridge._driver

        self.grid_model.cube_height = self.spin_cube_h.value()
        self.grid_model.z_safe = self.spin_z_safe.value()
        self.grid_model.center_z_ref = self.combo_center_ref.currentData()
        self.grid_model.place_z_offset = self.spin_place_offset.value()

        mode = "slot" if self.rb_mode_slot.isChecked() else "color"
        plan_items = [combo.currentData() for _, combo, *_ in self.layer_combos]
        self.grid_model.reset_arena()
        self.grid_widget.refresh()
        self._update_layer_z_previews()

        success = self.controller.start_mission(plan_items, mode=mode)
        if success:
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.progress_bar.setValue(0)

    def _on_pause_mission(self):
        if self.controller.is_paused:
            self.controller.resume()
            self.btn_pause.setText("⏸️ PAUSE")
        else:
            self.controller.pause()
            self.btn_pause.setText("▶️ RESUME")

    def _on_stop_mission(self):
        self.controller.stop()
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ PAUSE")

    def _on_controller_state(self, state: str, detail: str):
        self.lbl_mission_status.setText(f"สถานะ: {detail}")
        self.grid_widget.refresh()

    def _on_controller_layer(self, current_layer: int, total_layers: int, color_key: str):
        pct = int((current_layer / total_layers) * 100)
        self.progress_bar.setValue(pct)
        self.grid_widget.refresh()

    def _on_controller_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ PAUSE")
        self.grid_widget.refresh()
        if success:
            self.progress_bar.setValue(100)
            self.lbl_mission_status.setText("สถานะ: 🎉 ภารกิจสำเร็จ วางซ้อนลูกบาศก์ครบทุกชั้นสมบูรณ์!")
            self.lbl_mission_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11px;")
        else:
            self.lbl_mission_status.setText(f"สถานะ: ⚠️ ภารกิจหยุดทำงาน: {message}")
            self.lbl_mission_status.setStyleSheet("font-weight: bold; color: #EF4444; font-size: 11px;")

    def _on_controller_log(self, level: str, msg: str):
        self.bridge.sig_log.emit(level, msg)
