"""
Main Application Window for Dobot 3x3 Pick & Place Stacking Studio
Integrates Mission Tab, Hand-Guided Teaching, Manual Jog, Camera Feed, and Health Badge.
"""

import sys
from .qt_compat import QtWidgets, QtCore, QtGui
from .styles import DARK_THEME_QSS
from .ros_worker import RosBridgeWorker
from .widgets import ConnectionStatusBadge, CameraWidget
from dobot_driver.pnp.grid_model import Grid3x3Model
from .tabs import (
    PnpMissionTab,
    GridTeachingTab,
    ManualControlTab,
    ConnectionTab,
    MonitorTab
)


class DobotMainWindow(QtWidgets.QMainWindow):
    """Primary GUI Application Window hosting all tabs, live camera, and connection health."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dobot 3x3 Pick & Place & Color Stacking Studio (ROS 2)")
        self.resize(1280, 800)
        self.setMinimumSize(1050, 650)

        # Apply dark industrial styling
        self.setStyleSheet(DARK_THEME_QSS)

        # Shared 3x3 Grid Model
        self.grid_model = Grid3x3Model(cube_height=25.0, z_safe=80.0)

        # Start ROS & Hardware Bridge Worker Thread
        self.bridge = RosBridgeWorker()
        self.bridge.start()

        # Start in simulation mode by default for instant, zero-delay UI startup
        self.bridge.connect_hardware("mock")

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        root_vbox = QtWidgets.QVBoxLayout(central_widget)
        root_vbox.setContentsMargins(10, 6, 10, 6)
        root_vbox.setSpacing(8)

        # --- Top Header Bar ---
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)

        # Title
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(1)
        title_lbl = QtWidgets.QLabel("🤖 DOBOT 4-DOF PICK & PLACE & COLOR STACKING STUDIO")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #60A5FA; letter-spacing: 0.5px;")
        sub_lbl = QtWidgets.QLabel("ระบบควบคุมแขนกล Dobot 4-DOF ผ่าน ROS 2 สำหรับภารกิจซ้อนลูกบาศก์บนตาราง 3x3 ตามสี")
        sub_lbl.setStyleSheet("font-size: 10px; color: #94A3B8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()

        # Connection Health Badge
        self.badge_health = ConnectionStatusBadge()
        header.addWidget(self.badge_health)

        # Global Emergency Stop
        self.btn_header_estop = QtWidgets.QPushButton("🛑 E-STOP")
        self.btn_header_estop.setObjectName("btn_estop")
        self.btn_header_estop.setToolTip("กดเพื่อหยุดการเคลื่อนที่ทุกอย่างทันที")
        header.addWidget(self.btn_header_estop)

        root_vbox.addLayout(header)

        # --- Main Body: Split into Tabs and Side Camera Panel ---
        body_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left Container: Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tab_pnp = PnpMissionTab(self.bridge, self.grid_model)
        self.tab_teach = GridTeachingTab(self.bridge, self.grid_model)
        self.tab_manual = ManualControlTab(self.bridge)
        self.tab_conn = ConnectionTab(self.bridge)

        self.tabs.addTab(self.tab_pnp, "🎯 ภารกิจหลัก (Pick & Place)")
        self.tabs.addTab(self.tab_teach, "📝 บันทึกสี & Teach พิกัด")
        self.tabs.addTab(self.tab_manual, "🎮 ควบคุมแมนนวล (Manual Jog)")
        self.tabs.addTab(self.tab_conn, "⚙️ การเชื่อมต่อ (Connection)")

        body_splitter.addWidget(self.tabs)

        # Right Container: Camera on Top, Real-time Monitor on Bottom (Always Visible)
        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Top Right: Live Camera View
        cam_panel = QtWidgets.QGroupBox("📹 กล้องมอนิเตอร์สด (Live Camera Monitor)")
        cam_layout = QtWidgets.QVBoxLayout(cam_panel)
        cam_layout.setContentsMargins(6, 10, 6, 6)
        self.cam_widget = CameraWidget()
        cam_layout.addWidget(self.cam_widget)
        right_splitter.addWidget(cam_panel)

        # Bottom Right: Real-time Telemetry Monitor (Always Visible & Shrunk/Compact)
        self.tab_monitor = MonitorTab(self.bridge)
        right_splitter.addWidget(self.tab_monitor)

        right_splitter.setSizes([330, 370])
        body_splitter.addWidget(right_splitter)
        body_splitter.setSizes([820, 460])

        root_vbox.addWidget(body_splitter, 1)

        # --- Bottom Status Bar ---
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("background-color: #161820; color: #94A3B8; font-size: 12px; padding: 4px 10px;")

        self.lbl_status_msg = QtWidgets.QLabel("พร้อมทำงาน (System Ready)")
        self.status_bar.addWidget(self.lbl_status_msg)

    def _connect_signals(self):
        # Global E-Stop
        self.btn_header_estop.clicked.connect(self.bridge.emergency_stop)

        # Reconnect from badge
        self.badge_health.sig_reconnect_clicked.connect(self.bridge.reconnect_hardware)

        # Watchdog Health Updates to Badge
        self.bridge.sig_connection_health.connect(self.badge_health.update_health)
        self.bridge.sig_connection_changed.connect(self._on_connection_changed)
        self.bridge.sig_log.connect(self._on_log)

        # Sync grid teaching tab updates to mission tab grid widget and height previews
        self.tab_teach.sig_model_updated.connect(self.tab_pnp.sync_from_model)

    def _on_connection_changed(self, connected: bool, message: str):
        if connected:
            self.lbl_status_msg.setText(f"🟢 เชื่อมต่อกับ: {message}")
            self.lbl_status_msg.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            self.lbl_status_msg.setText(f"⚪ สถานะ: {message}")
            self.lbl_status_msg.setStyleSheet("color: #EF4444;")

    def _on_log(self, level: str, msg: str):
        if level in ["ERROR", "WARN"]:
            self.status_bar.showMessage(f"[{level}] {msg}", 6000)

    def closeEvent(self, event):
        """Clean shutdown when window is closed."""
        self.cam_widget.stop_camera()
        self.tab_pnp.controller.stop()
        self.bridge.stop()
        event.accept()
