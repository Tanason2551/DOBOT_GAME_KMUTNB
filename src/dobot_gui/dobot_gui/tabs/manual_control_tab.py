"""
Full Manual Jog and System Diagnostics Tab
Provides Cartesian/Joint jog control, step sizes, direct coordinate inputs,
manual suction cup testing, and emergency stop.
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal


class ManualControlTab(QtWidgets.QWidget):
    """Dedicated tab for manual positioning, motor jogging, and end-effector testing."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        self._curr_x = 220.0
        self._curr_y = 0.0
        self._curr_z = 50.0
        self._curr_r = 0.0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left Column: Jog Pad (Cartesian & Joint)
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(12)

        # Group: Jog Controller
        grp_jog = QtWidgets.QGroupBox("ควบคุมการเคลื่อนที่ด้วยตนเอง (Manual Jog Control)")
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

        # Cartesian Jog Grid
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
        lbl_joint.setStyleSheet("font-weight: bold; color: #94A3B8; margin-top: 6px;")
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

        j_grid.addWidget(QtWidgets.QLabel("J1 (Base):"), 0, 0)
        j_grid.addWidget(self.btn_j1n, 0, 1)
        j_grid.addWidget(self.btn_j1p, 0, 2)

        j_grid.addWidget(QtWidgets.QLabel("J2 (Rear):"), 0, 3)
        j_grid.addWidget(self.btn_j2n, 0, 4)
        j_grid.addWidget(self.btn_j2p, 0, 5)

        j_grid.addWidget(QtWidgets.QLabel("J3 (Fore):"), 1, 0)
        j_grid.addWidget(self.btn_j3n, 1, 1)
        j_grid.addWidget(self.btn_j3p, 1, 2)

        j_grid.addWidget(QtWidgets.QLabel("J4 (Wrist):"), 1, 3)
        j_grid.addWidget(self.btn_j4n, 1, 4)
        j_grid.addWidget(self.btn_j4p, 1, 5)

        jog_layout.addLayout(j_grid)
        left_panel.addWidget(grp_jog)
        left_panel.addStretch()
        main_layout.addLayout(left_panel, 1)

        # Right Column: Target Move, Suction Test, Actions
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(12)

        # Group: Target Coordinate Move
        grp_target = QtWidgets.QGroupBox("สั่งเคลื่อนที่ไปยังพิกัดเป้าหมาย (Direct Move to Target)")
        target_layout = QtWidgets.QFormLayout(grp_target)
        target_layout.setSpacing(8)
        target_layout.setContentsMargins(14, 14, 14, 14)

        self.spin_x = QtWidgets.QDoubleSpinBox()
        self.spin_x.setRange(-500.0, 500.0)
        self.spin_x.setValue(220.0)
        self.spin_x.setSuffix(" mm")

        self.spin_y = QtWidgets.QDoubleSpinBox()
        self.spin_y.setRange(-500.0, 500.0)
        self.spin_y.setValue(0.0)
        self.spin_y.setSuffix(" mm")

        self.spin_z = QtWidgets.QDoubleSpinBox()
        self.spin_z.setRange(-200.0, 400.0)
        self.spin_z.setValue(50.0)
        self.spin_z.setSuffix(" mm")

        self.spin_r = QtWidgets.QDoubleSpinBox()
        self.spin_r.setRange(-180.0, 180.0)
        self.spin_r.setValue(0.0)
        self.spin_r.setSuffix(" °")

        target_layout.addRow("พิกัด X:", self.spin_x)
        target_layout.addRow("พิกัด Y:", self.spin_y)
        target_layout.addRow("พิกัด Z:", self.spin_z)
        target_layout.addRow("มุมหมุน R:", self.spin_r)

        btn_target_box = QtWidgets.QHBoxLayout()
        self.btn_copy_pose = QtWidgets.QPushButton("📋 ดึงพิกัดปัจจุบัน")
        self.btn_send_pose = QtWidgets.QPushButton("🚀 Move to Target")
        self.btn_send_pose.setObjectName("btn_action_green")
        btn_target_box.addWidget(self.btn_copy_pose)
        btn_target_box.addWidget(self.btn_send_pose)
        target_layout.addRow("", btn_target_box)
        right_panel.addWidget(grp_target)

        # Group: Suction Cup Manual Test
        grp_suction = QtWidgets.QGroupBox("ทดสอบหัวดูดสุญญากาศ (Manual Suction Cup Test)")
        suction_layout = QtWidgets.QVBoxLayout(grp_suction)
        suction_layout.setContentsMargins(14, 14, 14, 14)

        self.btn_suction = QtWidgets.QPushButton("💨 หัวดูดสุญญากาศ (Suction Cup): OFF")
        self.btn_suction.setCheckable(True)
        self.btn_suction.setMinimumHeight(30)
        suction_layout.addWidget(self.btn_suction)
        right_panel.addWidget(grp_suction)

        # System Actions (Home & E-Stop)
        action_box = QtWidgets.QHBoxLayout()
        self.btn_home = QtWidgets.QPushButton("🏠 Home Calibration")
        self.btn_home.setObjectName("btn_action_amber")
        self.btn_home.setMinimumHeight(28)

        self.btn_clear_alarms = QtWidgets.QPushButton("🛡️ Clear Alarms")
        self.btn_clear_alarms.setMinimumHeight(28)

        action_box.addWidget(self.btn_home)
        action_box.addWidget(self.btn_clear_alarms)
        right_panel.addLayout(action_box)

        # Emergency Stop
        self.btn_estop = QtWidgets.QPushButton("🛑 EMERGENCY STOP (หยุดฉุกเฉิน)")
        self.btn_estop.setObjectName("btn_estop")
        self.btn_estop.setMinimumHeight(34)
        right_panel.addWidget(self.btn_estop)

        right_panel.addStretch()
        main_layout.addLayout(right_panel, 1)

    def _create_jog_btn(self, text: str, axis: str, direction: int) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(text)
        btn.setMinimumHeight(28)
        btn.setProperty("axis", axis)
        btn.setProperty("direction", direction)
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
        if step > 0.0 and not axis.startswith('J'):
            # Step Cartesian Mode: move precisely by step (mm) using PTP linear motion
            x, y, z, r = self._curr_x, self._curr_y, self._curr_z, self._curr_r
            if axis == 'X': x += direction * step
            elif axis == 'Y': y += direction * step
            elif axis == 'Z': z += direction * step
            elif axis == 'R': r += direction * step
            self.bridge.send_ptp(x, y, z, r, mode=2)
        else:
            # Continuous mode or Joint jog: send real-time jog command
            self.bridge.send_jog(axis, direction, step=step)

    def _on_jog_released(self, btn):
        step = self._get_current_step()
        axis = btn.property("axis")
        if step == 0.0 or axis.startswith('J'):
            self.bridge.stop_jog()

    def _connect_signals(self):
        self.btn_copy_pose.clicked.connect(self._copy_current_pose)
        self.btn_send_pose.clicked.connect(self._send_target_pose)
        self.btn_suction.clicked.connect(self._toggle_suction)
        self.btn_home.clicked.connect(self.bridge.home)
        self.btn_clear_alarms.clicked.connect(self.bridge.clear_alarms)
        self.btn_estop.clicked.connect(self.bridge.emergency_stop)

        self.bridge.sig_pose_updated.connect(self._on_pose_updated)

    def _copy_current_pose(self):
        self.spin_x.setValue(self._curr_x)
        self.spin_y.setValue(self._curr_y)
        self.spin_z.setValue(self._curr_z)
        self.spin_r.setValue(self._curr_r)

    def _send_target_pose(self):
        x = self.spin_x.value()
        y = self.spin_y.value()
        z = self.spin_z.value()
        r = self.spin_r.value()
        self.bridge.send_ptp(x, y, z, r, mode=2)

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

    def _on_pose_updated(self, x, y, z, r, j1, j2, j3, j4):
        self._curr_x, self._curr_y, self._curr_z, self._curr_r = x, y, z, r
