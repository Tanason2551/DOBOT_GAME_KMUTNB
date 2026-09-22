"""
Live Camera Monitor Widget
Renders real-time video feed from ROS 2 (/camera/image_raw) or direct OpenCV,
with center crosshair and 3x3 arena alignment grid overlay.
"""

import os
import glob
import struct
import time
import threading
from ..qt_compat import QtWidgets, QtCore, QtGui, Signal

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def detect_cameras():
    """
    Detect available V4L2 video capture devices and their human-readable card names.
    Filters out metadata nodes on Linux.
    """
    cameras = []
    video_devices = sorted(
        glob.glob('/dev/video*'),
        key=lambda x: int(''.join(filter(str.isdigit, x)) or 0)
    )

    VIDIOC_QUERYCAP = 0x80685600
    V4L2_CAP_VIDEO_CAPTURE = 0x00000001
    V4L2_CAP_DEVICE_CAPS = 0x80000000

    for dev_path in video_devices:
        dev_name = os.path.basename(dev_path)
        digits = ''.join(filter(str.isdigit, dev_name))
        if not digits:
            continue
        idx = int(digits)

        card_name = f"Camera {idx}"
        is_capture = True

        # Try standard V4L2 ioctl query
        try:
            import fcntl
            fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
            buf = bytearray(104)
            fcntl.ioctl(fd, VIDIOC_QUERYCAP, buf)
            os.close(fd)
            driver, card, bus, ver, caps, dev_caps = struct.unpack('16s32s32sIII12x', buf)
            card_str = card.split(b'\x00')[0].decode('utf-8', 'ignore').strip()
            if card_str:
                card_name = card_str
            actual_caps = dev_caps if (caps & V4L2_CAP_DEVICE_CAPS) else caps
            is_capture = bool(actual_caps & V4L2_CAP_VIDEO_CAPTURE)
        except Exception:
            # Fallback to sysfs inspection
            name_path = f"/sys/class/video4linux/{dev_name}/name"
            if os.path.exists(name_path):
                try:
                    with open(name_path, "r", encoding="utf-8") as f:
                        card_name = f.read().strip()
                except Exception:
                    pass
            idx_path = f"/sys/class/video4linux/{dev_name}/index"
            if os.path.exists(idx_path):
                try:
                    with open(idx_path, "r") as f:
                        if f.read().strip() != '0':
                            is_capture = False
                except Exception:
                    pass

        if is_capture:
            cameras.append((idx, f"[{idx}] {card_name}"))

    if not cameras:
        cameras.append((0, "Camera 0 (Default)"))
    return cameras


class CameraWorker(QtCore.QThread):
    """Background thread fetching frames from OpenCV or ROS 2."""

    sig_frame_ready = Signal(QtGui.QImage, int, int, float)
    sig_camera_error = Signal(str)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self._running = False
        self.cap = None

    def run(self):
        if not OPENCV_AVAILABLE:
            self.sig_camera_error.emit("OpenCV ไม่ได้ติดตั้งในระบบ")
            return

        self._running = True
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else 0)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)
        except Exception as e:
            self.sig_camera_error.emit(f"เกิดข้อผิดพลาดในการเปิดกล้อง: {e}")
            return

        if not self.cap.isOpened():
            self.sig_camera_error.emit(f"ไม่สามารถเปิดกล้อง ID: {self.camera_index} ได้ (อาจถูกโปรแกรมอื่นใช้งานอยู่ หรือถูกถอดออก)")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        prev_time = time.time()
        fps = 30.0
        consecutive_read_failures = 0

        while self._running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                consecutive_read_failures += 1
                if consecutive_read_failures > 30:
                    self.sig_camera_error.emit(f"สัญญาณภาพจากกล้อง ID: {self.camera_index} ขาดหาย")
                    break
                time.sleep(0.05)
                continue

            consecutive_read_failures = 0

            # Calculate FPS
            now = time.time()
            dt = now - prev_time
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)
            prev_time = now

            if len(frame.shape) == 2:
                h, w = frame.shape
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
                ch = 3
            else:
                h, w, ch = frame.shape
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            bytes_per_line = ch * w
            qimg = QtGui.QImage(rgb_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            self.sig_frame_ready.emit(qimg.copy(), w, h, fps)
            time.sleep(0.025)

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def stop(self):
        self._running = False
        self.wait(1000)


class CameraWidget(QtWidgets.QWidget):
    """Video feed viewer with camera selection, crosshair, grid overlay, and controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.is_active = False
        self.show_crosshair = True
        self.show_grid = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Video Display Label
        self.lbl_video = QtWidgets.QLabel()
        self.lbl_video.setMinimumSize(260, 160)
        self.lbl_video.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.lbl_video.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_video.setStyleSheet("""
            QLabel {
                background-color: #0A0B0E;
                border: 1px solid #2D3748;
                border-radius: 8px;
                color: #64748B;
                font-size: 12px;
            }
        """)
        self.lbl_video.setText("📹 กล้องปิดอยู่\n(กดปุ่ม 'เปิดกล้อง' ด้านล่างเพื่อแสดงภาพสด)")
        layout.addWidget(self.lbl_video, 1)

        # Controls Layout
        ctrl_layout = QtWidgets.QVBoxLayout()
        ctrl_layout.setSpacing(4)

        # Row 1: Camera device dropdown, refresh button, start/stop button
        row_cam = QtWidgets.QHBoxLayout()
        row_cam.setSpacing(6)

        lbl_cam = QtWidgets.QLabel("📷 กล้อง:")
        lbl_cam.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")

        self.combo_camera = QtWidgets.QComboBox()
        self.combo_camera.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.combo_camera.setFixedHeight(28)
        self.combo_camera.setToolTip("เลือกอุปกรณ์กล้องที่ต้องการเปิดดู")
        self.combo_camera.currentIndexChanged.connect(self._on_camera_selection_changed)

        self.btn_refresh_cams = QtWidgets.QPushButton("🔄")
        self.btn_refresh_cams.setFixedSize(28, 28)
        self.btn_refresh_cams.setToolTip("สแกนค้นหากล้องใหม่")
        self.btn_refresh_cams.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_refresh_cams.clicked.connect(self._refresh_cameras)

        self.btn_toggle_cam = QtWidgets.QPushButton("▶️ เปิดกล้อง")
        self.btn_toggle_cam.setFixedHeight(28)
        self.btn_toggle_cam.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_toggle_cam.clicked.connect(self._toggle_camera)

        row_cam.addWidget(lbl_cam)
        row_cam.addWidget(self.combo_camera, 1)
        row_cam.addWidget(self.btn_refresh_cams)
        row_cam.addWidget(self.btn_toggle_cam)

        # Row 2: Overlays (Crosshair, Grid) & Status Info
        row_opts = QtWidgets.QHBoxLayout()
        row_opts.setSpacing(8)

        self.chk_crosshair = QtWidgets.QCheckBox("🎯 กากบาท")
        self.chk_crosshair.setChecked(True)
        self.chk_crosshair.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.chk_crosshair.stateChanged.connect(lambda s: setattr(self, "show_crosshair", s == 2))

        self.chk_grid = QtWidgets.QCheckBox("▦ 3x3 Grid")
        self.chk_grid.setChecked(True)
        self.chk_grid.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.chk_grid.stateChanged.connect(lambda s: setattr(self, "show_grid", s == 2))

        self.lbl_cam_info = QtWidgets.QLabel("Status: Idle")
        self.lbl_cam_info.setStyleSheet("color: #94A3B8; font-size: 11px;")

        row_opts.addWidget(self.chk_crosshair)
        row_opts.addWidget(self.chk_grid)
        row_opts.addStretch()
        row_opts.addWidget(self.lbl_cam_info)

        ctrl_layout.addLayout(row_cam)
        ctrl_layout.addLayout(row_opts)
        layout.addLayout(ctrl_layout)

        # Populate camera dropdown
        self._refresh_cameras()

    def _refresh_cameras(self):
        current_data = self.get_selected_camera_index()
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()

        cams = detect_cameras()
        selected_idx = 0
        for i, (cam_id, name) in enumerate(cams):
            self.combo_camera.addItem(name, cam_id)
            if current_data is not None and cam_id == current_data:
                selected_idx = i

        self.combo_camera.setCurrentIndex(selected_idx)
        self.combo_camera.blockSignals(False)

    def get_selected_camera_index(self) -> int:
        data = self.combo_camera.currentData()
        return int(data) if data is not None else 0

    def _on_camera_selection_changed(self, index: int):
        if self.is_active:
            self.stop_camera()
            self.start_camera()

    def _toggle_camera(self):
        if self.is_active:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        if not OPENCV_AVAILABLE:
            self.lbl_video.setText("⚠️ OpenCV ไม่ได้ติดตั้ง\nกรุณาติดตั้งผ่าน pip install opencv-python")
            return

        cam_id = self.get_selected_camera_index()
        self.is_active = True
        self.btn_toggle_cam.setText("⏹️ ปิดกล้อง")
        self.btn_toggle_cam.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #B91C1C; }
        """)
        self.lbl_cam_info.setText("Connecting...")
        self.lbl_video.setText(f"📹 กำลังเชื่อมต่อกล้อง ID {cam_id}...")

        self.worker = CameraWorker(camera_index=cam_id)
        self.worker.sig_frame_ready.connect(self._on_frame_ready)
        self.worker.sig_camera_error.connect(self._on_camera_error)
        self.worker.start()

    def stop_camera(self):
        self.is_active = False
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.btn_toggle_cam.setText("▶️ เปิดกล้อง")
        self.btn_toggle_cam.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.lbl_video.setText("📹 กล้องปิดอยู่\n(กดปุ่ม 'เปิดกล้อง' เพื่อเริ่มแสดงผล)")
        self.lbl_cam_info.setText("Status: Idle")

    def _on_camera_error(self, err_msg: str):
        self.is_active = False
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.btn_toggle_cam.setText("▶️ เปิดกล้อง")
        self.btn_toggle_cam.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.lbl_video.setText(f"⚠️ {err_msg}\nกรุณาเลือกกล้องอื่น หรือตรวจสอบการเชื่อมต่อ")
        self.lbl_cam_info.setText("Error")

    def _on_frame_ready(self, qimg: QtGui.QImage, width: int, height: int, fps: float):
        # Draw overlay lines
        painter = QtGui.QPainter(qimg)
        pen_reticle = QtGui.QPen(QtGui.QColor(0, 255, 128, 180), 1)
        pen_grid = QtGui.QPen(QtGui.QColor(59, 130, 246, 120), 1, QtCore.Qt.DashLine)

        cx, cy = width // 2, height // 2

        # 3x3 Grid Overlay
        if self.show_grid:
            painter.setPen(pen_grid)
            box_size = 240
            left, top = cx - box_size // 2, cy - box_size // 2
            step = box_size // 3
            # Draw outer box
            painter.drawRect(left, top, box_size, box_size)
            # Internal lines
            painter.drawLine(left + step, top, left + step, top + box_size)
            painter.drawLine(left + 2 * step, top, left + 2 * step, top + box_size)
            painter.drawLine(left, top + step, left + box_size, top + step)
            painter.drawLine(left, top + 2 * step, left + box_size, top + 2 * step)

        # Center Crosshair
        if self.show_crosshair:
            painter.setPen(pen_reticle)
            painter.drawLine(cx - 20, cy, cx + 20, cy)
            painter.drawLine(cx, cy - 20, cx, cy + 20)
            painter.drawEllipse(QtCore.QPoint(cx, cy), 8, 8)

        painter.end()

        # Scale to fit label
        pixmap = QtGui.QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaled(
            self.lbl_video.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.lbl_video.setPixmap(scaled_pixmap)
        self.lbl_cam_info.setText(f"{width}x{height} | {fps:.1f} FPS")

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
