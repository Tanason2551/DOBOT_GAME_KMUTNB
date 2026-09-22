"""
Real-time Monitor and Diagnostics Widget (Compact Dashboard)
Provides live Cartesian pose, joint angles, end-effector status, and event logs.
"""

import time
from ..qt_compat import QtWidgets, QtCore, QtGui, Signal


class MonitorTab(QtWidgets.QWidget):
    """Compact real-time display of Cartesian positions, joint angles, end-effectors, and logs."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Outer GroupBox
        grp_monitor = QtWidgets.QGroupBox("📊 มอนิเตอร์สด (Real-time Telemetry)")
        grp_layout = QtWidgets.QVBoxLayout(grp_monitor)
        grp_layout.setSpacing(6)
        grp_layout.setContentsMargins(6, 8, 6, 6)

        # 1. Cartesian Coordinates (Compact 2x2 Grid)
        cart_box = QtWidgets.QFrame()
        cart_box.setStyleSheet("background-color: #0A0B0E; border: 1px solid #232733; border-radius: 5px;")
        cart_layout = QtWidgets.QGridLayout(cart_box)
        cart_layout.setSpacing(4)
        cart_layout.setContentsMargins(6, 4, 6, 4)

        self.lbl_x = self._create_coord_badge("X", "220.0 mm", "#60A5FA")
        self.lbl_y = self._create_coord_badge("Y", "0.0 mm", "#60A5FA")
        self.lbl_z = self._create_coord_badge("Z", "50.0 mm", "#34D399")
        self.lbl_r = self._create_coord_badge("R", "0.0 °", "#FBBF24")

        cart_layout.addWidget(self.lbl_x, 0, 0)
        cart_layout.addWidget(self.lbl_y, 0, 1)
        cart_layout.addWidget(self.lbl_z, 1, 0)
        cart_layout.addWidget(self.lbl_r, 1, 1)

        grp_layout.addWidget(cart_box)

        # 2. Joint Angles & Compact Visual Meters (2x2 Compact Grid)
        joints_box = QtWidgets.QFrame()
        joints_box.setStyleSheet("background-color: #0A0B0E; border: 1px solid #232733; border-radius: 5px;")
        joints_layout = QtWidgets.QGridLayout(joints_box)
        joints_layout.setSpacing(3)
        joints_layout.setContentsMargins(6, 4, 6, 4)

        self.j1_bar, self.lbl_j1 = self._create_joint_meter(-135, 135)
        self.j2_bar, self.lbl_j2 = self._create_joint_meter(0, 85)
        self.j3_bar, self.lbl_j3 = self._create_joint_meter(-10, 95)
        self.j4_bar, self.lbl_j4 = self._create_joint_meter(-180, 180)

        lbl_j1_name = QtWidgets.QLabel("J1:")
        lbl_j1_name.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 10px;")
        lbl_j2_name = QtWidgets.QLabel("J2:")
        lbl_j2_name.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 10px;")
        lbl_j3_name = QtWidgets.QLabel("J3:")
        lbl_j3_name.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 10px;")
        lbl_j4_name = QtWidgets.QLabel("J4:")
        lbl_j4_name.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 10px;")

        joints_layout.addWidget(lbl_j1_name, 0, 0)
        joints_layout.addWidget(self.j1_bar, 0, 1)
        joints_layout.addWidget(self.lbl_j1, 0, 2)

        joints_layout.addWidget(lbl_j2_name, 0, 3)
        joints_layout.addWidget(self.j2_bar, 0, 4)
        joints_layout.addWidget(self.lbl_j2, 0, 5)

        joints_layout.addWidget(lbl_j3_name, 1, 0)
        joints_layout.addWidget(self.j3_bar, 1, 1)
        joints_layout.addWidget(self.lbl_j3, 1, 2)

        joints_layout.addWidget(lbl_j4_name, 1, 3)
        joints_layout.addWidget(self.j4_bar, 1, 4)
        joints_layout.addWidget(self.lbl_j4, 1, 5)

        grp_layout.addWidget(joints_box)

        # 3. Active End-Effector Status Badges
        eff_box = QtWidgets.QHBoxLayout()
        eff_box.setSpacing(6)

        self.badge_suction = QtWidgets.QLabel("💨 Suction: OFF")
        self.badge_suction.setAlignment(QtCore.Qt.AlignCenter)
        self.badge_suction.setFixedHeight(22)
        self.badge_suction.setStyleSheet("background-color: #1E293B; color: #94A3B8; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;")

        self.badge_gripper = QtWidgets.QLabel("🤏 Gripper: OPEN")
        self.badge_gripper.setAlignment(QtCore.Qt.AlignCenter)
        self.badge_gripper.setFixedHeight(22)
        self.badge_gripper.setStyleSheet("background-color: #1E293B; color: #94A3B8; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;")

        eff_box.addWidget(self.badge_suction)
        eff_box.addWidget(self.badge_gripper)
        grp_layout.addLayout(eff_box)

        # 4. Compact Event Console Log
        log_box = QtWidgets.QVBoxLayout()
        log_box.setSpacing(3)

        log_header = QtWidgets.QHBoxLayout()
        lbl_log_title = QtWidgets.QLabel("📝 บันทึกเหตุการณ์ (Event Log):")
        lbl_log_title.setStyleSheet("font-size: 10px; color: #94A3B8; font-weight: bold;")

        self.btn_clear_log = QtWidgets.QPushButton("ล้าง")
        self.btn_clear_log.setFixedHeight(18)
        self.btn_clear_log.setStyleSheet("font-size: 9px; padding: 1px 6px; background-color: #262B3D;")

        log_header.addWidget(lbl_log_title)
        log_header.addStretch()
        log_header.addWidget(self.btn_clear_log)
        log_box.addLayout(log_header)

        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(75)
        self.txt_log.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0A0B0E;
                color: #CBD5E1;
                font-family: monospace;
                font-size: 10px;
                border: 1px solid #232733;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        log_box.addWidget(self.txt_log)

        grp_layout.addLayout(log_box)
        main_layout.addWidget(grp_monitor)

    def _create_coord_badge(self, prefix: str, default_val: str, color: str):
        lbl = QtWidgets.QLabel(f"{prefix}: {default_val}")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet(f"""
            QLabel {{
                background-color: #12141C;
                color: {color};
                font-size: 11px;
                font-weight: bold;
                padding: 3px 6px;
                border: 1px solid #1E2330;
                border-radius: 4px;
            }}
        """)
        lbl.setProperty("prefix", prefix)
        return lbl

    def _create_joint_meter(self, min_val: int, max_val: int):
        bar = QtWidgets.QProgressBar()
        bar.setRange(min_val, max_val)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet("""
            QProgressBar {
                background-color: #14161F;
                border: 1px solid #28303F;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 3px;
            }
        """)
        lbl = QtWidgets.QLabel("0.0°")
        lbl.setFixedWidth(40)
        lbl.setStyleSheet("font-weight: bold; color: #CBD5E1; font-size: 10px;")
        return bar, lbl

    def _connect_signals(self):
        self.btn_clear_log.clicked.connect(self.txt_log.clear)
        self.bridge.sig_pose_updated.connect(self._on_pose_updated)
        self.bridge.sig_status_updated.connect(self._on_status_updated)
        self.bridge.sig_log.connect(self._append_log)

    def _on_pose_updated(self, x, y, z, r, j1, j2, j3, j4):
        self.lbl_x.setText(f"X: {x:.1f} mm")
        self.lbl_y.setText(f"Y: {y:.1f} mm")
        self.lbl_z.setText(f"Z: {z:.1f} mm")
        self.lbl_r.setText(f"R: {r:.1f} °")

        self.j1_bar.setValue(int(j1))
        self.lbl_j1.setText(f"{j1:.1f}°")

        self.j2_bar.setValue(int(j2))
        self.lbl_j2.setText(f"{j2:.1f}°")

        self.j3_bar.setValue(int(j3))
        self.lbl_j3.setText(f"{j3:.1f}°")

        self.j4_bar.setValue(int(j4))
        self.lbl_j4.setText(f"{j4:.1f}°")

    def _on_status_updated(self, status: dict):
        suction = status.get("suction_state", False)
        gripper = status.get("gripper_state", False)

        if suction:
            self.badge_suction.setText("💨 Suction: ACTIVE")
            self.badge_suction.setStyleSheet("background-color: #059669; color: #FFFFFF; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px;")
        else:
            self.badge_suction.setText("💨 Suction: OFF")
            self.badge_suction.setStyleSheet("background-color: #1E293B; color: #94A3B8; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px;")

        if gripper:
            self.badge_gripper.setText("🤏 Gripper: GRIP")
            self.badge_gripper.setStyleSheet("background-color: #059669; color: #FFFFFF; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px;")
        else:
            self.badge_gripper.setText("🤏 Gripper: OPEN")
            self.badge_gripper.setStyleSheet("background-color: #1E293B; color: #94A3B8; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px;")

    def _append_log(self, level: str, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        color = "#A7F3D0"
        if level == "ERROR":
            color = "#F87171"
        elif level == "WARN":
            color = "#FBBF24"
        elif level == "CMD":
            color = "#60A5FA"

        html = f"<span style='color: #64748B;'>[{timestamp}]</span> <b style='color: {color};'>[{level}]</b> {msg}"
        self.txt_log.appendHtml(html)

