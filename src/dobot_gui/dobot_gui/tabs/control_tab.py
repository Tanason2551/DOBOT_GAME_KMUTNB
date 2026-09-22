"""
Manual Jog and Motion Control Tab
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal


class ControlTab(QtWidgets.QWidget):
    """Tab for manual jogging, Cartesian PTP positioning, and end-effector activation."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        self._curr_x = 0.0
        self._curr_y = 0.0
        self._curr_z = 0.0
        self._curr_r = 0.0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Left Column: Jog Control (Cartesian & Joint)
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(14)

        # Group: Jog Controller
        grp_jog = QtWidgets.QGroupBox("ระบบ Jog Manual Control (ขยับทีละสเต็ป / ขยับต่อเนื่อง)")
        jog_layout = QtWidgets.QVBoxLayout(grp_jog)
        jog_layout.setSpacing(12)
        jog_layout.setContentsMargins(14, 14, 14, 14)

        # Step Size Selector
        step_box = QtWidgets.QHBoxLayout()
        step_box.addWidget(QtWidgets.QLabel("ระยะขยับ (Step Size):"))
        self.btn_grp_step = QtWidgets.QButtonGroup(self)

        steps = [("0.5 mm", 0.5), ("1.0 mm", 1.0), ("5.0 mm", 5.0), ("10 mm", 10.0), ("50 mm", 50.0), ("Continuous", 0.0)]
        self.step_radios = {}
        for name, val in steps:
            rb = QtWidgets.QRadioButton(name)
            if val == 5.0:
                rb.setChecked(True)
            self.btn_grp_step.addButton(rb)
            self.step_radios[rb] = val
            step_box.addWidget(rb)
        step_box.addStretch()
        jog_layout.addLayout(step_box)

        # Jog Grid: Cartesian (X, Y, Z, R)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        self.btn_xp = self._create_jog_btn("X+ (หน้า)", "X", 1)
        self.btn_xn = self._create_jog_btn("X- (หลัง)", "X", -1)
        self.btn_yp = self._create_jog_btn("Y+ (ซ้าย)", "Y", 1)
        self.btn_yn = self._create_jog_btn("Y- (ขวา)", "Y", -1)
        self.btn_zp = self._create_jog_btn("Z+ (ขึ้น)", "Z", 1)
        self.btn_zn = self._create_jog_btn("Z- (ลง)", "Z", -1)
        self.btn_rp = self._create_jog_btn("R+ (หมุนขวา)", "R", 1)
        self.btn_rn = self._create_jog_btn("R- (หมุนซ้าย)", "R", -1)

        # Arrange buttons in an intuitive cross layout
        grid.addWidget(self.btn_xp, 0, 1)
        grid.addWidget(self.btn_yn, 1, 0)
        grid.addWidget(self.btn_yp, 1, 2)
        grid.addWidget(self.btn_xn, 2, 1)

        grid.addWidget(self.btn_zp, 0, 4)
        grid.addWidget(self.btn_zn, 2, 4)
        grid.addWidget(self.btn_rn, 1, 3)
        grid.addWidget(self.btn_rp, 1, 5)

        jog_layout.addLayout(grid)

        # Joint Jog Grid
        lbl_joint = QtWidgets.QLabel("ควบคุมตามข้อต่อ (Joint Jog):")
        lbl_joint.setStyleSheet("font-weight: bold; color: #94A3B8; margin-top: 8px;")
        jog_layout.addWidget(lbl_joint)

        j_grid = QtWidgets.QGridLayout()
        j_grid.setSpacing(6)

        self.btn_j1p = self._create_jog_btn("J1 +", "J1", 1)
        self.btn_j1n = self._create_jog_btn("J1 -", "J1", -1)
        self.btn_j2p = self._create_jog_btn("J2 +", "J2", 1)
        self.btn_j2n = self._create_jog_btn("J2 -", "J2", -1)
        self.btn_j3p = self._create_jog_btn("J3 +", "J3", 1)
        self.btn_j3n = self._create_jog_btn("J3 -", "J3", -1)
        self.btn_j4p = self._create_jog_btn("J4 +", "J4", 1)
        self.btn_j4n = self._create_jog_btn("J4 -", "J4", -1)

        j_grid.addWidget(QtWidgets.QLabel("Joint 1 (Base):"), 0, 0)
        j_grid.addWidget(self.btn_j1n, 0, 1)
        j_grid.addWidget(self.btn_j1p, 0, 2)

        j_grid.addWidget(QtWidgets.QLabel("Joint 2 (Rear):"), 0, 3)
        j_grid.addWidget(self.btn_j2n, 0, 4)
        j_grid.addWidget(self.btn_j2p, 0, 5)

        j_grid.addWidget(QtWidgets.QLabel("Joint 3 (Fore):"), 1, 0)
        j_grid.addWidget(self.btn_j3n, 1, 1)
        j_grid.addWidget(self.btn_j3p, 1, 2)

        j_grid.addWidget(QtWidgets.QLabel("Joint 4 (Wrist):"), 1, 3)
        j_grid.addWidget(self.btn_j4n, 1, 4)
        j_grid.addWidget(self.btn_j4p, 1, 5)

        jog_layout.addLayout(j_grid)
        left_panel.addWidget(grp_jog)
        left_panel.addStretch()
        main_layout.addLayout(left_panel, 1)

        # Right Column: Target Coordinates & End-Effector Control
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(14)

        # Group: Target Coordinate Move
        grp_target = QtWidgets.QGroupBox("สั่งเคลื่อนที่ตามพิกัด (Target Cartesian Move)")
        target_layout = QtWidgets.QFormLayout(grp_target)
        target_layout.setSpacing(10)
        target_layout.setContentsMargins(14, 14, 14, 14)

        self.spin_target_x = QtWidgets.QDoubleSpinBox()
        self.spin_target_x.setRange(-500.0, 500.0)
        self.spin_target_x.setValue(220.0)
        self.spin_target_x.setSuffix(" mm")

        self.spin_target_y = QtWidgets.QDoubleSpinBox()
        self.spin_target_y.setRange(-500.0, 500.0)
        self.spin_target_y.setValue(0.0)
        self.spin_target_y.setSuffix(" mm")

        self.spin_target_z = QtWidgets.QDoubleSpinBox()
        self.spin_target_z.setRange(-200.0, 400.0)
        self.spin_target_z.setValue(50.0)
        self.spin_target_z.setSuffix(" mm")

        self.spin_target_r = QtWidgets.QDoubleSpinBox()
        self.spin_target_r.setRange(-180.0, 180.0)
        self.spin_target_r.setValue(0.0)
        self.spin_target_r.setSuffix(" °")

        target_layout.addRow("พิกัด X:", self.spin_target_x)
        target_layout.addRow("พิกัด Y:", self.spin_target_y)
        target_layout.addRow("พิกัด Z:", self.spin_target_z)
        target_layout.addRow("มุมหมุน R:", self.spin_target_r)

        self.combo_mode = QtWidgets.QComboBox()
        self.combo_mode.addItems(["MOVL (เคลื่อนที่เส้นตรง - Linear)", "MOVJ (เคลื่อนที่เร็วตามข้อต่อ - Joint)", "JUMP (ยกขึ้นแล้ววางลง)"])
        target_layout.addRow("โหมดการเคลื่อนที่:", self.combo_mode)

        btn_target_box = QtWidgets.QHBoxLayout()
        self.btn_copy_curr = QtWidgets.QPushButton("📋 ดึงพิกัดปัจจุบัน")
        self.btn_send_target = QtWidgets.QPushButton("🚀 Move to Target")
        self.btn_send_target.setObjectName("btn_action_green")
        btn_target_box.addWidget(self.btn_copy_curr)
        btn_target_box.addWidget(self.btn_send_target)
        target_layout.addRow("", btn_target_box)

        right_panel.addWidget(grp_target)

        # Group: End-Effector Control
        grp_effector = QtWidgets.QGroupBox("ควบคุมอุปกรณ์ปลายแขน (End-Effector Control)")
        eff_layout = QtWidgets.QGridLayout(grp_effector)
        eff_layout.setSpacing(12)
        eff_layout.setContentsMargins(14, 14, 14, 14)

        # Suction Cup
        self.btn_suction = QtWidgets.QPushButton("💨 หัวดูดสุญญากาศ (Suction Cup): OFF")
        self.btn_suction.setCheckable(True)
        self.btn_suction.setMinimumHeight(38)

        # Gripper
        self.btn_gripper = QtWidgets.QPushButton("🤏 คีมหนีบ (Gripper): OPEN")
        self.btn_gripper.setCheckable(True)
        self.btn_gripper.setMinimumHeight(38)

        eff_layout.addWidget(self.btn_suction, 0, 0)
        eff_layout.addWidget(self.btn_gripper, 0, 1)
        right_panel.addWidget(grp_effector)

        # Emergency Stop Button
        self.btn_estop = QtWidgets.QPushButton("🛑 EMERGENCY STOP (หยุดฉุกเฉิน)")
        self.btn_estop.setObjectName("btn_estop")
        self.btn_estop.setMinimumHeight(50)
        right_panel.addWidget(self.btn_estop)

        right_panel.addStretch()
        main_layout.addLayout(right_panel, 1)

    def _create_jog_btn(self, text: str, axis: str, direction: int) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(text)
        btn.setMinimumHeight(36)
        # Store metadata
        btn.setProperty("axis", axis)
        btn.setProperty("direction", direction)

        # Connect both pressed & released for continuous or step
        btn.pressed.connect(lambda: self._on_jog_pressed(btn))
        btn.released.connect(lambda: self._on_jog_released(btn))
        return btn

    def _get_current_step(self) -> float:
        checked_btn = self.btn_grp_step.checkedButton()
        return self.step_radios.get(checked_btn, 5.0)

    def _on_jog_pressed(self, btn):
        axis = btn.property("axis")
        direction = btn.property("direction")
        step = self._get_current_step()
        self.bridge.send_jog(axis, direction, step=step)

    def _on_jog_released(self, btn):
        step = self._get_current_step()
        if step == 0.0:  # Continuous jog stops on release
            self.bridge.stop_jog()

    def _connect_signals(self):
        self.btn_copy_curr.clicked.connect(self._copy_current_pose)
        self.btn_send_target.clicked.connect(self._send_target_move)
        self.btn_suction.clicked.connect(self._toggle_suction)
        self.btn_gripper.clicked.connect(self._toggle_gripper)
        self.btn_estop.clicked.connect(self.bridge.emergency_stop)

        self.bridge.sig_pose_updated.connect(self._on_pose_update)
        self.bridge.sig_status_updated.connect(self._on_status_update)

    def _copy_current_pose(self):
        self.spin_target_x.setValue(self._curr_x)
        self.spin_target_y.setValue(self._curr_y)
        self.spin_target_z.setValue(self._curr_z)
        self.spin_target_r.setValue(self._curr_r)

    def _send_target_move(self):
        x = self.spin_target_x.value()
        y = self.spin_target_y.value()
        z = self.spin_target_z.value()
        r = self.spin_target_r.value()
        mode_idx = self.combo_mode.currentIndex()
        # Mode: 0 -> MOVL(2), 1 -> MOVJ(1), 2 -> JUMP(0)
        mode_map = {0: 2, 1: 1, 2: 0}
        self.bridge.send_ptp(x, y, z, r, mode=mode_map.get(mode_idx, 2))

    def _toggle_suction(self, checked: bool):
        if checked:
            self.btn_suction.setText("💨 หัวดูดสุญญากาศ: ON (กำลังดูด)")
            self.btn_suction.setObjectName("btn_action_green")
            self.btn_suction.setStyle(self.btn_suction.style())
        else:
            self.btn_suction.setText("💨 หัวดูดสุญญากาศ: OFF")
            self.btn_suction.setObjectName("")
            self.btn_suction.setStyle(self.btn_suction.style())
        self.bridge.set_suction_cup(checked)

    def _toggle_gripper(self, checked: bool):
        if checked:
            self.btn_gripper.setText("🤏 คีมหนีบ: CLOSED (หนีบ)")
            self.btn_gripper.setObjectName("btn_action_green")
            self.btn_gripper.setStyle(self.btn_gripper.style())
        else:
            self.btn_gripper.setText("🤏 คีมหนีบ: OPEN (ปล่อย)")
            self.btn_gripper.setObjectName("")
            self.btn_gripper.setStyle(self.btn_gripper.style())
        self.bridge.set_gripper(checked)

    def _on_pose_update(self, x, y, z, r, j1, j2, j3, j4):
        self._curr_x, self._curr_y, self._curr_z, self._curr_r = x, y, z, r

    def _on_status_update(self, status: dict):
        suction = status.get("suction_state", False)
        gripper = status.get("gripper_state", False)
        if self.btn_suction.isChecked() != suction:
            self.btn_suction.setChecked(suction)
            self.btn_suction.setText(f"💨 หัวดูดสุญญากาศ: {'ON' if suction else 'OFF'}")
        if self.btn_gripper.isChecked() != gripper:
            self.btn_gripper.setChecked(gripper)
            self.btn_gripper.setText(f"🤏 คีมหนีบ: {'CLOSED' if gripper else 'OPEN'}")
