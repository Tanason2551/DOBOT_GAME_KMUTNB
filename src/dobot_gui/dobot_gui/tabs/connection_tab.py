"""
Connection and System Configuration Tab
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from dobot_driver.hardware.magician_driver import DobotMagicianDriver


class ConnectionTab(QtWidgets.QWidget):
    """Tab for setting up robot connection, communication parameters, and speed limits."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Left Column: Connection & Motion Parameters
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(14)

        # Group: Hardware Connection
        grp_conn = QtWidgets.QGroupBox("การเชื่อมต่อแขนกล (Robot Connection)")
        conn_layout = QtWidgets.QFormLayout(grp_conn)
        conn_layout.setSpacing(10)
        conn_layout.setContentsMargins(14, 14, 14, 14)

        # Model Selector
        self.combo_model = QtWidgets.QComboBox()
        self.combo_model.addItems([
            "Auto-Detect (ตรวจจับพอร์ตอัตโนมัติ)",
            "Dobot Magician / Lite (4-DOF USB Serial)",
            "Simulation Mode (จำลองเสมือนจริง)"
        ])
        conn_layout.addRow("เลือกรุ่นแขนกล (Model):", self.combo_model)

        # Serial Port & Refresh
        port_box = QtWidgets.QHBoxLayout()
        self.combo_port = QtWidgets.QComboBox()
        self.combo_port.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.btn_refresh_ports = QtWidgets.QPushButton("🔄 Scan")
        self.btn_refresh_ports.setToolTip("ค้นหาพอร์ต Serial / USB ที่เชื่อมต่ออยู่")
        self.btn_refresh_ports.setFixedWidth(70)
        port_box.addWidget(self.combo_port)
        port_box.addWidget(self.btn_refresh_ports)
        conn_layout.addRow("พอร์ต USB/Serial:", port_box)

        # Baudrate
        self.combo_baud = QtWidgets.QComboBox()
        self.combo_baud.addItems(["115200", "57600", "9600"])
        conn_layout.addRow("Baud Rate:", self.combo_baud)

        # Connect / Disconnect Buttons
        btn_box = QtWidgets.QHBoxLayout()
        self.btn_connect = QtWidgets.QPushButton("⚡ Connect Robot")
        self.btn_connect.setObjectName("btn_action_green")
        self.btn_connect.setMinimumHeight(36)

        self.btn_disconnect = QtWidgets.QPushButton("🔌 Disconnect")
        self.btn_disconnect.setMinimumHeight(36)
        self.btn_disconnect.setEnabled(False)

        btn_box.addWidget(self.btn_connect)
        btn_box.addWidget(self.btn_disconnect)
        conn_layout.addRow("", btn_box)

        # Connection Status Badge
        status_box = QtWidgets.QHBoxLayout()
        self.lbl_status_icon = QtWidgets.QLabel("●")
        self.lbl_status_icon.setStyleSheet("color: #EF4444; font-size: 16px;")
        self.lbl_status_text = QtWidgets.QLabel("สถานะ: ยังไม่ได้เชื่อมต่อ (Disconnected)")
        self.lbl_status_text.setStyleSheet("font-weight: bold; color: #94A3B8;")
        status_box.addWidget(self.lbl_status_icon)
        status_box.addWidget(self.lbl_status_text)
        status_box.addStretch()
        conn_layout.addRow("สถานะระบบ:", status_box)

        left_panel.addWidget(grp_conn)

        # Group: Motion & Speed Parameters
        grp_params = QtWidgets.QGroupBox("การตั้งค่าความเร็ว & อัตราเร่ง (Motion Parameters)")
        params_layout = QtWidgets.QFormLayout(grp_params)
        params_layout.setSpacing(12)
        params_layout.setContentsMargins(14, 14, 14, 14)

        # Velocity Ratio
        vel_box = QtWidgets.QHBoxLayout()
        self.slider_vel = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_vel.setRange(1, 100)
        self.slider_vel.setValue(50)
        self.lbl_vel_val = QtWidgets.QLabel("50 %")
        self.lbl_vel_val.setFixedWidth(45)
        vel_box.addWidget(self.slider_vel)
        vel_box.addWidget(self.lbl_vel_val)
        params_layout.addRow("ความเร็ว (Velocity):", vel_box)

        # Acceleration Ratio
        acc_box = QtWidgets.QHBoxLayout()
        self.slider_acc = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_acc.setRange(1, 100)
        self.slider_acc.setValue(50)
        self.lbl_acc_val = QtWidgets.QLabel("50 %")
        self.lbl_acc_val.setFixedWidth(45)
        acc_box.addWidget(self.slider_acc)
        acc_box.addWidget(self.lbl_acc_val)
        params_layout.addRow("อัตราเร่ง (Accel):", acc_box)

        # Apply Speed Button
        self.btn_apply_speed = QtWidgets.QPushButton("บันทึกการตั้งค่าความเร็ว")
        params_layout.addRow("", self.btn_apply_speed)

        # System Calibration & Alarms
        action_box = QtWidgets.QHBoxLayout()
        self.btn_home = QtWidgets.QPushButton("🏠 Home Calibration")
        self.btn_home.setObjectName("btn_action_amber")
        self.btn_clear_alarms = QtWidgets.QPushButton("🛡️ Clear Alarms / Reset")
        action_box.addWidget(self.btn_home)
        action_box.addWidget(self.btn_clear_alarms)
        params_layout.addRow("การจัดการระบบ:", action_box)

        left_panel.addWidget(grp_params)
        left_panel.addStretch()
        layout.addLayout(left_panel, 1)

        # Right Column: Model Guide & Hardware Detection Helper
        grp_guide = QtWidgets.QGroupBox("คำแนะนำในการตรวจสอบรุ่นของ Dobot (Model Identification Guide)")
        guide_layout = QtWidgets.QVBoxLayout(grp_guide)
        guide_layout.setContentsMargins(14, 14, 14, 14)

        guide_text = QtWidgets.QTextBrowser()
        guide_text.setStyleSheet("background-color: #0F1015; border: 1px solid #2D3748; padding: 10px; border-radius: 6px;")
        guide_text.setHtml("""
        <h3 style="color: #60A5FA; margin-top: 0;">คำแนะนำการเชื่อมต่อแขนกล Dobot:</h3>
        
        <div style="margin-bottom: 12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
            <b style="color: #34D399; font-size: 14px;">1. Dobot Magician / Magician Lite (4-DOF USB Serial)</b>
            <ul style="color: #CBD5E1; margin: 4px 0 0 16px;">
                <li><b>การเชื่อมต่อ:</b> เสียบสาย <b>USB (Type-B ทรงเหลี่ยม หรือ Micro-USB)</b> เข้าคอมพิวเตอร์</li>
                <li><b>พอร์ต Serial:</b> กดปุ่ม <b>"🔄 Scan"</b> เพื่อค้นหาพอร์ต เช่น <code>/dev/ttyUSB0</code> หรือ <code>/dev/ttyACM0</code></li>
                <li><b>Baud Rate:</b> ตั้งค่าเริ่มต้นที่ <code>115200</code></li>
                <li><b>สิทธิ์พอร์ต:</b> ตรวจสอบว่า User อยู่ในกลุ่ม <code>dialout</code> แล้ว</li>
            </ul>
        </div>

        <div style="margin-bottom: 12px;">
            <b style="color: #60A5FA; font-size: 14px;">2. Simulation Mode (โหมดจำลอง)</b>
            <ul style="color: #CBD5E1; margin: 4px 0 0 16px;">
                <li>ใช้งานได้ทันที<b>โดยไม่ต้องต่อหุ่นยนต์จริง</b> สำหรับทดสอบหน้าจอ UI และตรรกะการซ้อนลูกบาศก์</li>
                <li>จำลองการเคลื่อนที่ Kinematics, ค่าพิกัด, สัญญาณ ROS 2 ครบถ้วน 100%</li>
            </ul>
        </div>
        """)
        guide_layout.addWidget(guide_text)
        layout.addWidget(grp_guide, 1)

        self._refresh_ports()

    def _connect_signals(self):
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        self.btn_apply_speed.clicked.connect(self._on_apply_speed)
        self.btn_home.clicked.connect(self._on_home)
        self.btn_clear_alarms.clicked.connect(self._on_clear_alarms)

        self.slider_vel.valueChanged.connect(lambda v: self.lbl_vel_val.setText(f"{v} %"))
        self.slider_acc.valueChanged.connect(lambda v: self.lbl_acc_val.setText(f"{v} %"))

        self.bridge.sig_connection_changed.connect(self._on_connection_changed)

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = DobotMagicianDriver.scan_ports()
        if ports:
            self.combo_port.addItems(ports)
        else:
            self.combo_port.addItem("ไม่พบพอร์ต Serial (ใช้ Simulation ได้)")

    def _on_connect_clicked(self):
        model_idx = self.combo_model.currentIndex()
        model_map = {
            0: "auto",
            1: "magician",
            2: "mock"
        }
        model_type = model_map.get(model_idx, "auto")

        port = self.combo_port.currentText()
        if "ไม่พบ" in port:
            port = ""

        baud = int(self.combo_baud.currentText())

        self.bridge.connect_hardware(model_type, port=port, baudrate=baud)

    def _on_disconnect_clicked(self):
        self.bridge.disconnect_hardware()

    def _on_connection_changed(self, connected: bool, message: str):
        if connected:
            self.lbl_status_icon.setStyleSheet("color: #10B981; font-size: 16px;")
            self.lbl_status_text.setText(f"เชื่อมต่อสำเร็จ: {message}")
            self.lbl_status_text.setStyleSheet("font-weight: bold; color: #10B981;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            self.lbl_status_icon.setStyleSheet("color: #EF4444; font-size: 16px;")
            self.lbl_status_text.setText(f"สถานะ: ไม่ได้เชื่อมต่อ ({message})")
            self.lbl_status_text.setStyleSheet("font-weight: bold; color: #EF4444;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def _on_apply_speed(self):
        vel = float(self.slider_vel.value())
        acc = float(self.slider_acc.value())
        self.bridge.set_speed(vel, acc)

    def _on_home(self):
        self.bridge.home()

    def _on_clear_alarms(self):
        self.bridge.clear_alarms()
