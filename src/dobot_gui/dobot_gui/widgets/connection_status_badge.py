"""
Connection Health Status Badge Widget
Displays real-time connection state, latency (Ping ms), update rate (Hz),
and quick reconnect action.
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal


class ConnectionStatusBadge(QtWidgets.QWidget):
    """Visual header badge indicating Dobot <-> ROS2 communication health."""

    sig_reconnect_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Background styling
        self.setStyleSheet("""
            ConnectionStatusBadge {
                background-color: #1A1D26;
                border: 1px solid #2E3446;
                border-radius: 8px;
            }
        """)

        # LED Indicator
        self.lbl_led = QtWidgets.QLabel("●")
        self.lbl_led.setStyleSheet("color: #EF4444; font-size: 16px;")
        layout.addWidget(self.lbl_led)

        # Status & Model Text
        text_box = QtWidgets.QVBoxLayout()
        text_box.setSpacing(1)
        self.lbl_model = QtWidgets.QLabel("Dobot: Disconnected")
        self.lbl_model.setStyleSheet("font-weight: bold; font-size: 12px; color: #F1F5F9;")
        self.lbl_metrics = QtWidgets.QLabel("Ping: -- ms | 0.0 Hz")
        self.lbl_metrics.setStyleSheet("font-size: 11px; color: #94A3B8;")
        text_box.addWidget(self.lbl_model)
        text_box.addWidget(self.lbl_metrics)
        layout.addLayout(text_box)

        # Reconnect button
        self.btn_reconnect = QtWidgets.QPushButton("🔄 Reconnect")
        self.btn_reconnect.setFixedHeight(26)
        self.btn_reconnect.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_reconnect.clicked.connect(self.sig_reconnect_clicked.emit)
        layout.addWidget(self.btn_reconnect)

    def update_health(self, is_connected: bool, model_name: str, latency_ms: float = 0.0, rate_hz: float = 0.0):
        """Update visual badge with latest health metrics."""
        if is_connected:
            if latency_ms > 100.0:
                self.lbl_led.setStyleSheet("color: #F59E0B; font-size: 16px;")  # Yellow
                self.lbl_model.setText(f"{model_name} (High Latency)")
            else:
                self.lbl_led.setStyleSheet("color: #10B981; font-size: 16px;")  # Green
                self.lbl_model.setText(f"{model_name}")
            self.lbl_metrics.setText(f"Ping: {latency_ms:.1f} ms | {rate_hz:.1f} Hz")
        else:
            self.lbl_led.setStyleSheet("color: #EF4444; font-size: 16px;")      # Red
            self.lbl_model.setText(f"{model_name} (Disconnected)")
            self.lbl_metrics.setText("Connection Lost | 0.0 Hz")
