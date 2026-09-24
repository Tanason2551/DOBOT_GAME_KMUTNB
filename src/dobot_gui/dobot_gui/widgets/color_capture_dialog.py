"""
Color Capture and Detection Modal Dialog
Provides interactive live viewfinder, 4-corner perspective adjustment pins,
automatic HSV color classification for the 3x3 arena, and safe color assignment.
"""

import time
from typing import Dict, List, Tuple, Optional, Any
from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from ..utils.color_detector import ColorDetector, GRID_SLOT_MAP
from dobot_driver.pnp import Grid3x3Model, COLOR_PALETTE
from .camera_widget import CameraWorker, detect_cameras, OPENCV_AVAILABLE

try:
    import cv2
    import numpy as np
except ImportError:
    pass


class InteractiveCornerViewfinder(QtWidgets.QLabel):
    """
    Video viewfinder supporting interactive drag-and-drop 4-corner pins
    and real-time perspective grid overlay.
    """

    sig_corners_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMouseTracking(True)

        self.current_qimage: Optional[QtGui.QImage] = None
        self.corners: List[List[float]] = ColorDetector.get_default_corners(640, 480, "birds_eye")
        self.mode = "birds_eye"
        self.active_pin_idx = -1
        self.hover_pin_idx = -1
        self.pin_radius = 13
        self.show_grid = True
        self.detected_results: Optional[Dict[int, Tuple[str, float]]] = None

        self.setStyleSheet("""
            background-color: #0A0B0E;
            border: 2px solid #28303F;
            border-radius: 8px;
        """)

    def set_frame(self, qimg: QtGui.QImage):
        """Update live video frame."""
        self.current_qimage = qimg
        self.update()

    def set_mode(self, mode: str):
        """Switch between 'top_view' and 'birds_eye'."""
        self.mode = mode
        self.corners = ColorDetector.get_default_corners(640, 480, mode)
        self.sig_corners_changed.emit(self.corners)
        self.update()

    def reset_corners(self):
        """Reset corners to default for current mode."""
        self.corners = ColorDetector.get_default_corners(640, 480, self.mode)
        self.sig_corners_changed.emit(self.corners)
        self.update()

    def set_detected_results(self, results: Optional[Dict[int, Tuple[str, float]]]):
        """Set detection results to draw overlay badges on cells."""
        self.detected_results = results
        self.update()

    def _get_transform_metrics(self) -> Tuple[float, float, float, float]:
        """Compute scale and offset of the 640x480 video within widget."""
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return 1.0, 1.0, 0.0, 0.0

        target_ratio = 640.0 / 480.0
        current_ratio = float(w) / float(h)

        if current_ratio > target_ratio:
            # Letterbox left and right
            scale = float(h) / 480.0
            display_w = 640.0 * scale
            display_h = float(h)
            offset_x = (w - display_w) / 2.0
            offset_y = 0.0
        else:
            # Letterbox top and bottom
            scale = float(w) / 640.0
            display_w = float(w)
            display_h = 480.0 * scale
            offset_x = 0.0
            offset_y = (h - display_h) / 2.0

        return scale, scale, offset_x, offset_y

    def _frame_to_widget(self, fx: float, fy: float) -> QtCore.QPointF:
        scale_x, scale_y, off_x, off_y = self._get_transform_metrics()
        return QtCore.QPointF(off_x + fx * scale_x, off_y + fy * scale_y)

    def _widget_to_frame(self, wx: float, wy: float) -> Tuple[float, float]:
        scale_x, scale_y, off_x, off_y = self._get_transform_metrics()
        if scale_x <= 0 or scale_y <= 0:
            return 0.0, 0.0
        fx = (wx - off_x) / scale_x
        fy = (wy - off_y) / scale_y
        return max(0.0, min(640.0, fx)), max(0.0, min(480.0, fy))

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton and self.mode == "birds_eye":
            pos = event.position() if hasattr(event, "position") else event.pos()
            # Hit test pins
            for i, (cx, cy) in enumerate(self.corners):
                wpt = self._frame_to_widget(cx, cy)
                dx = pos.x() - wpt.x()
                dy = pos.y() - wpt.y()
                if (dx * dx + dy * dy) <= (self.pin_radius * self.pin_radius * 1.8):
                    self.active_pin_idx = i
                    self.update()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        pos = event.position() if hasattr(event, "position") else event.pos()

        if self.active_pin_idx >= 0 and self.mode == "birds_eye":
            fx, fy = self._widget_to_frame(pos.x(), pos.y())
            self.corners[self.active_pin_idx] = [fx, fy]
            self.sig_corners_changed.emit(self.corners)
            self.update()
            return

        # Hover test
        hover_idx = -1
        if self.mode == "birds_eye":
            for i, (cx, cy) in enumerate(self.corners):
                wpt = self._frame_to_widget(cx, cy)
                dx = pos.x() - wpt.x()
                dy = pos.y() - wpt.y()
                if (dx * dx + dy * dy) <= (self.pin_radius * self.pin_radius * 1.8):
                    hover_idx = i
                    break

        if hover_idx != self.hover_pin_idx:
            self.hover_pin_idx = hover_idx
            self.setCursor(QtCore.Qt.PointingHandCursor if hover_idx >= 0 else QtCore.Qt.ArrowCursor)
            self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if self.active_pin_idx >= 0:
            self.active_pin_idx = -1
            self.sig_corners_changed.emit(self.corners)
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # 1. Draw base video frame
        scale_x, scale_y, off_x, off_y = self._get_transform_metrics()
        target_rect = QtCore.QRectF(off_x, off_y, 640.0 * scale_x, 480.0 * scale_y)

        if self.current_qimage is not None and not self.current_qimage.isNull():
            painter.drawImage(target_rect, self.current_qimage)
        else:
            painter.fillRect(target_rect, QtGui.QColor("#11131A"))
            painter.setPen(QtGui.QColor("#475569"))
            painter.setFont(QtGui.QFont("DejaVu Sans", 11, QtGui.QFont.Bold))
            painter.drawText(target_rect, QtCore.Qt.AlignCenter, "📹 รอสัญญาณภาพจากกล้อง...")

        # 2. Draw 3x3 Perspective Grid
        if self.show_grid and len(self.corners) == 4:
            pts = [self._frame_to_widget(cx, cy) for cx, cy in self.corners]

            # Draw outer quadrilateral
            pen_poly = QtGui.QPen(QtGui.QColor(59, 130, 246, 220), 2)
            painter.setPen(pen_poly)
            painter.drawPolygon(QtGui.QPolygonF(pts))

            # Interpolate 3x3 internal lines
            pen_grid = QtGui.QPen(QtGui.QColor(96, 165, 250, 160), 1, QtCore.Qt.DashLine)
            painter.setPen(pen_grid)

            def interp(pA, pB, t):
                return QtCore.QPointF(pA.x() + (pB.x() - pA.x()) * t, pA.y() + (pB.y() - pA.y()) * t)

            # Vertical grid dividers
            for u in [1.0 / 3.0, 2.0 / 3.0]:
                top_pt = interp(pts[0], pts[1], u)
                bot_pt = interp(pts[3], pts[2], u)
                painter.drawLine(top_pt, bot_pt)

            # Horizontal grid dividers
            for v in [1.0 / 3.0, 2.0 / 3.0]:
                left_pt = interp(pts[0], pts[3], v)
                right_pt = interp(pts[1], pts[2], v)
                painter.drawLine(left_pt, right_pt)

            # Draw cell labels & detection badges
            for (row, col), slot_id in GRID_SLOT_MAP.items():
                u_center = (col + 0.5) / 3.0
                v_center = (row + 0.5) / 3.0
                top_pt = interp(pts[0], pts[1], u_center)
                bot_pt = interp(pts[3], pts[2], u_center)
                c_pt = interp(top_pt, bot_pt, v_center)

                # Check if we have detection results
                badge_text = f"S{slot_id}" if slot_id != 9 else "Center"
                bg_color = QtGui.QColor(30, 41, 59, 190)
                fg_color = QtGui.QColor("#F1F5F9")

                if self.detected_results and slot_id in self.detected_results:
                    color_key, conf = self.detected_results[slot_id]
                    col_info = COLOR_PALETTE.get(color_key, {})
                    c_name = col_info.get("name", color_key)
                    badge_text = f"{badge_text}: {c_name} ({int(conf * 100)}%)"
                    hex_col = col_info.get("hex", "#3B82F6")
                    bg_color = QtGui.QColor(hex_col)
                    bg_color.setAlpha(220)
                    fg_color = QtGui.QColor("#000000" if color_key in ["yellow", "white", "cyan"] else "#FFFFFF")

                # Draw badge pill
                font = QtGui.QFont("DejaVu Sans", 8, QtGui.QFont.Bold)
                painter.setFont(font)
                metrics = QtGui.QFontMetrics(font)
                bw = metrics.horizontalAdvance(badge_text) + 12
                bh = 18
                rect_badge = QtCore.QRectF(c_pt.x() - bw / 2.0, c_pt.y() - bh / 2.0, bw, bh)

                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(bg_color)
                painter.drawRoundedRect(rect_badge, 4, 4)

                painter.setPen(fg_color)
                painter.drawText(rect_badge, QtCore.Qt.AlignCenter, badge_text)

            # 3. Draw 4 Corner Handles (if in bird's-eye view)
            if self.mode == "birds_eye":
                pin_names = ["1: บนซ้าย", "2: บนขวา", "3: ล่างขวา", "4: ล่างซ้าย"]
                for i, wpt in enumerate(pts):
                    is_active = (i == self.active_pin_idx)
                    is_hover = (i == self.hover_pin_idx)

                    r = self.pin_radius + (3 if is_active or is_hover else 0)
                    halo_col = QtGui.QColor(245, 158, 11, 235) if is_active else (QtGui.QColor(96, 165, 250, 220) if is_hover else QtGui.QColor(16, 185, 129, 210))

                    painter.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 2))
                    painter.setBrush(halo_col)
                    painter.drawEllipse(wpt, r, r)

                    # Text label
                    painter.setPen(QtGui.QColor("#FFFFFF"))
                    painter.setFont(QtGui.QFont("DejaVu Sans", 8, QtGui.QFont.Bold))
                    painter.drawText(QtCore.QRectF(wpt.x() - 40, wpt.y() - r - 16, 80, 14), QtCore.Qt.AlignCenter, pin_names[i])

        painter.end()


class ColorCaptureDialog(QtWidgets.QDialog):
    """
    Two-column Dialog preventing overlapping between the Camera Viewfinder and Color Scan components.
    Left: Interactive Camera Viewfinder with 4-corner perspective pins.
    Right: 3x3 Arena Slot Grid, Dropdowns, Action Buttons, and Strict Data Protection.
    """

    sig_colors_applied = Signal(dict)

    def __init__(self, grid_model: Grid3x3Model, camera_widget=None, target_slot_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.grid_model = grid_model
        self.camera_widget = camera_widget
        self.target_slot_id = target_slot_id

        self.setWindowTitle("📸 สแกนและตรวจจับสีลูกบาศก์บนสนาม 3x3 (Camera Color Detection)")
        self.resize(1020, 620)
        self.setMinimumSize(880, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #12141C;
                color: #E2E8F0;
            }
            QLabel {
                font-size: 11px;
                color: #CBD5E1;
            }
            QGroupBox {
                border: 1px solid #28303F;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                color: #60A5FA;
                font-size: 11px;
            }
        """)

        self.current_frame_bgr = None
        self.is_frozen = False
        self.detected_colors: Dict[int, str] = {}
        self.worker: Optional[CameraWorker] = None
        self._using_shared_camera = False

        self._setup_ui()
        self._load_saved_calibration()
        self._start_viewfinder_stream()

    def _setup_ui(self):
        root_vbox = QtWidgets.QVBoxLayout(self)
        root_vbox.setContentsMargins(14, 10, 14, 10)
        root_vbox.setSpacing(8)

        # Header Title Bar
        header = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel("📸 สแกนและตรวจจับสีลูกบาศก์บนสนาม 3x3 ด้วยกล้อง (Camera Color Detection)")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #60A5FA;")
        sub_lbl = QtWidgets.QLabel("ลากหมุด 4 มุมครอบสนาม แล้วกดแคปเจอร์เพื่อวิเคราะห์สี โดยพิกัดกลไกของแขนกล (X, Y, Z, R) จะคงเดิม 100%")
        sub_lbl.setStyleSheet("font-size: 10px; color: #94A3B8;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)
        header.addStretch()

        root_vbox.addLayout(header)

        # Main Body: Two Columns (Left = Camera Viewfinder, Right = 3x3 Color Results & Actions)
        body_layout = QtWidgets.QHBoxLayout()
        body_layout.setSpacing(12)

        # ==========================================
        # LEFT COLUMN: Interactive Camera Viewfinder
        # ==========================================
        left_box = QtWidgets.QVBoxLayout()
        left_box.setSpacing(6)

        # Viewfinder Container
        self.viewfinder = InteractiveCornerViewfinder(self)
        self.viewfinder.sig_corners_changed.connect(self._on_corners_changed)
        left_box.addWidget(self.viewfinder, 1)

        # Viewfinder Toolbar: Camera Selector & Pin / Mode Controls
        view_toolbar = QtWidgets.QHBoxLayout()
        view_toolbar.setSpacing(6)

        lbl_c = QtWidgets.QLabel("📷 กล้อง:")
        lbl_c.setStyleSheet("font-weight: bold; color: #94A3B8; font-size: 11px;")
        self.combo_cam = QtWidgets.QComboBox()
        self.combo_cam.setFixedHeight(26)
        self.combo_cam.setMinimumWidth(150)
        cams = detect_cameras()
        active_cam_idx = self.camera_widget.get_selected_camera_index() if self.camera_widget else 0
        sel_idx = 0
        for i, (cid, cname) in enumerate(cams):
            self.combo_cam.addItem(cname, cid)
            if cid == active_cam_idx:
                sel_idx = i
        self.combo_cam.setCurrentIndex(sel_idx)
        self.combo_cam.currentIndexChanged.connect(self._on_camera_device_changed)

        view_toolbar.addWidget(lbl_c)
        view_toolbar.addWidget(self.combo_cam)

        self.btn_grp_mode = QtWidgets.QButtonGroup(self)
        self.rb_birds_eye = QtWidgets.QRadioButton("📐 มุมเฉียง")
        self.rb_top_view = QtWidgets.QRadioButton("🔲 มุมตรง 90°")
        self.rb_birds_eye.setChecked(True)
        self.rb_birds_eye.setStyleSheet("font-size: 10px; color: #CBD5E1;")
        self.rb_top_view.setStyleSheet("font-size: 10px; color: #CBD5E1;")
        self.btn_grp_mode.addButton(self.rb_birds_eye)
        self.btn_grp_mode.addButton(self.rb_top_view)
        view_toolbar.addWidget(self.rb_birds_eye)
        view_toolbar.addWidget(self.rb_top_view)

        self.btn_reset_pins = QtWidgets.QPushButton("🔄 รีเซ็ตหมุด 4 มุม")
        self.btn_reset_pins.setFixedHeight(26)
        self.btn_reset_pins.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        self.btn_reset_pins.setToolTip("คืนค่าตำแหน่งหมุด 4 มุมกลับสู่ค่าตั้งต้น")
        self.btn_reset_pins.clicked.connect(self.viewfinder.reset_corners)
        view_toolbar.addWidget(self.btn_reset_pins)

        left_box.addLayout(view_toolbar)

        self.lbl_view_info = QtWidgets.QLabel("💡 ลากหมุดสีเหลือง 4 จุด (1..4) ให้ครอบมุมทั้ง 4 ของสนามตาราง 3x3 บนภาพสด")
        self.lbl_view_info.setStyleSheet("color: #F59E0B; font-size: 10px; font-weight: bold;")
        left_box.addWidget(self.lbl_view_info)

        body_layout.addLayout(left_box, 3)

        # ==========================================
        # RIGHT COLUMN: 3x3 Color Results & Actions
        # ==========================================
        right_box = QtWidgets.QVBoxLayout()
        right_box.setSpacing(8)

        # 3x3 Grid Color Results
        self.grp_results = QtWidgets.QGroupBox("🎨 ผลการตรวจจับสีสนาม 3x3 (Detected Colors)")
        grid_results = QtWidgets.QGridLayout(self.grp_results)
        grid_results.setContentsMargins(6, 8, 6, 6)
        grid_results.setSpacing(5)

        self.slot_preview_combos: Dict[int, QtWidgets.QComboBox] = {}
        self.slot_conf_labels: Dict[int, QtWidgets.QLabel] = {}

        for (r, c), slot_id in GRID_SLOT_MAP.items():
            cell_frame = QtWidgets.QFrame()
            cell_frame.setStyleSheet("""
                QFrame {
                    background-color: #0E1015;
                    border: 1px solid #232733;
                    border-radius: 4px;
                }
            """)
            cf_layout = QtWidgets.QVBoxLayout(cell_frame)
            cf_layout.setContentsMargins(4, 3, 4, 3)
            cf_layout.setSpacing(2)

            if slot_id == 9:
                # Center Slot (Target Stacking Tower)
                lbl_name = QtWidgets.QLabel("🏢 Center")
                lbl_name.setAlignment(QtCore.Qt.AlignCenter)
                lbl_name.setStyleSheet("font-weight: bold; font-size: 10px; color: #F59E0B;")
                lbl_desc = QtWidgets.QLabel("จุดวางซ้อน")
                lbl_desc.setAlignment(QtCore.Qt.AlignCenter)
                lbl_desc.setStyleSheet("font-size: 9px; color: #64748B;")
                cf_layout.addWidget(lbl_name)
                cf_layout.addWidget(lbl_desc)
            else:
                slot_obj = self.grid_model.get_slot(slot_id)
                lbl_name = QtWidgets.QLabel(f"S{slot_id}")
                lbl_name.setAlignment(QtCore.Qt.AlignCenter)
                lbl_name.setStyleSheet("font-weight: bold; font-size: 10px; color: #94A3B8;")

                combo = QtWidgets.QComboBox()
                combo.setFixedHeight(22)
                combo.setStyleSheet("font-size: 10px; padding: 1px;")
                for k, info in COLOR_PALETTE.items():
                    combo.addItem(info["name"], k)
                if slot_obj:
                    idx = combo.findData(slot_obj.color)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                lbl_conf = QtWidgets.QLabel("รอสแกน")
                lbl_conf.setAlignment(QtCore.Qt.AlignCenter)
                lbl_conf.setStyleSheet("font-size: 9px; color: #64748B;")

                cf_layout.addWidget(lbl_name)
                cf_layout.addWidget(combo)
                cf_layout.addWidget(lbl_conf)

                self.slot_preview_combos[slot_id] = combo
                self.slot_conf_labels[slot_id] = lbl_conf

            grid_results.addWidget(cell_frame, r, c)

        right_box.addWidget(self.grp_results)

        # Action Buttons
        actions_box = QtWidgets.QVBoxLayout()
        actions_box.setSpacing(6)

        self.btn_capture = QtWidgets.QPushButton("📸 ถ่ายภาพ & วิเคราะห์สี (Capture & Scan)")
        self.btn_capture.setFixedHeight(36)
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_capture.clicked.connect(self._on_capture_clicked)
        actions_box.addWidget(self.btn_capture)

        row_sub_actions = QtWidgets.QHBoxLayout()
        row_sub_actions.setSpacing(6)

        self.btn_retake = QtWidgets.QPushButton("🔄 ถ่ายภาพใหม่")
        self.btn_retake.setFixedHeight(30)
        self.btn_retake.setEnabled(False)
        self.btn_retake.setStyleSheet("font-size: 11px;")
        self.btn_retake.clicked.connect(self._on_retake_clicked)
        row_sub_actions.addWidget(self.btn_retake)

        self.btn_apply = QtWidgets.QPushButton("✅ บันทึกสีลงตาราง")
        self.btn_apply.setFixedHeight(30)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #334155; color: #64748B; }
        """)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        row_sub_actions.addWidget(self.btn_apply)

        actions_box.addLayout(row_sub_actions)

        self.btn_cancel = QtWidgets.QPushButton("❌ ยกเลิก")
        self.btn_cancel.setFixedHeight(28)
        self.btn_cancel.setStyleSheet("background-color: #1E293B; color: #94A3B8; font-size: 11px;")
        self.btn_cancel.clicked.connect(self.reject)
        actions_box.addWidget(self.btn_cancel)

        right_box.addLayout(actions_box)

        # Safety Assurance Banner
        safety_banner = QtWidgets.QFrame()
        safety_banner.setStyleSheet("""
            background-color: #0F172A;
            border: 1px solid #1E293B;
            border-radius: 4px;
            padding: 4px 6px;
        """)
        sb_layout = QtWidgets.QHBoxLayout(safety_banner)
        sb_layout.setContentsMargins(4, 2, 4, 2)
        lbl_safe = QtWidgets.QLabel(
            "🔒 <b>ความปลอดภัย:</b> ระบบบันทึกเฉพาะค่าสีลงโมเดล โดยไม่แตะต้องพิกัดกลไก (X, Y, Z, R) 100%"
        )
        lbl_safe.setStyleSheet("color: #60A5FA; font-size: 9px;")
        lbl_safe.setWordWrap(True)
        sb_layout.addWidget(lbl_safe)
        right_box.addWidget(safety_banner)

        body_layout.addLayout(right_box, 2)

        root_vbox.addLayout(body_layout, 1)

        # Mode toggles
        self.rb_birds_eye.toggled.connect(self._on_mode_toggled)

    def _load_saved_calibration(self):
        corners, mode = ColorDetector.load_corners(640, 480)
        self.viewfinder.corners = corners
        self.viewfinder.mode = mode
        if mode == "top_view":
            self.rb_top_view.setChecked(True)
        else:
            self.rb_birds_eye.setChecked(True)

    def _start_viewfinder_stream(self):
        if not OPENCV_AVAILABLE:
            return

        # Check if parent or passed CameraWidget is active and streaming
        if self.camera_widget and hasattr(self.camera_widget, "is_active") and self.camera_widget.is_active and self.camera_widget.worker:
            self._using_shared_camera = True
            self.camera_widget.worker.sig_frame_ready.connect(self._on_stream_frame)
            # Try to grab current frame immediately
            bgr = self.camera_widget.get_current_bgr_frame()
            if bgr is not None:
                self.current_frame_bgr = bgr
            return

        # Otherwise launch independent CameraWorker
        cam_id = self.combo_cam.currentData()
        if cam_id is None:
            cam_id = 0

        self._using_shared_camera = False
        self.worker = CameraWorker(camera_index=cam_id)
        self.worker.sig_frame_ready.connect(self._on_stream_frame)
        self.worker.start()

    def _on_stream_frame(self, qimg: QtGui.QImage, width: int, height: int, fps: float):
        if not self.is_frozen:
            # Grab BGR frame from worker
            if self.worker:
                bgr = self.worker.get_last_bgr_frame()
                if bgr is not None:
                    self.current_frame_bgr = bgr
            elif self.camera_widget:
                bgr = self.camera_widget.get_current_bgr_frame()
                if bgr is not None:
                    self.current_frame_bgr = bgr

            self.viewfinder.set_frame(qimg)

    def _on_camera_device_changed(self):
        self._stop_current_stream()
        self.is_frozen = False
        self.btn_retake.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_capture.setEnabled(True)
        self.viewfinder.set_detected_results(None)
        self._start_viewfinder_stream()

    def _on_mode_toggled(self):
        mode = "birds_eye" if self.rb_birds_eye.isChecked() else "top_view"
        self.viewfinder.set_mode(mode)
        self.btn_reset_pins.setEnabled(mode == "birds_eye")
        if mode == "birds_eye":
            self.lbl_view_info.setText("💡 โหมดมุมเฉียง: ลากหมุด 4 มุม (1..4) ให้ทาบขอบกระดาน 3x3 บนภาพสด")
        else:
            self.lbl_view_info.setText("💡 โหมดมุมมองตรง: จัดตำแหน่งกล้องให้อยู่ตรงกึ่งกลางกระดาน 90°")

    def _on_corners_changed(self, corners: list):
        mode = "birds_eye" if self.rb_birds_eye.isChecked() else "top_view"
        ColorDetector.save_corners(corners, mode=mode)

    def _on_capture_clicked(self):
        """Freeze current frame and run color detection."""
        if self.current_frame_bgr is None:
            # Try capturing a single frame if worker hasn't provided one yet
            if self.camera_widget:
                self.current_frame_bgr = self.camera_widget.get_current_bgr_frame()

        if self.current_frame_bgr is None:
            QtWidgets.QMessageBox.warning(self, "แจ้งเตือน", "ยังไม่ได้รับสัญญาณภาพจากกล้อง กรุณารอสักครู่หรือกดเปิดกล้อง")
            return

        self.is_frozen = True
        self.btn_capture.setEnabled(False)
        self.btn_retake.setEnabled(True)
        self.btn_apply.setEnabled(True)

        # Run detection
        corners = self.viewfinder.corners
        results = ColorDetector.detect_grid_colors(self.current_frame_bgr, corners)
        self.viewfinder.set_detected_results(results)

        # Populate preview comboboxes and confidence labels
        for slot_id, (color_key, conf) in results.items():
            if slot_id in self.slot_preview_combos:
                combo = self.slot_preview_combos[slot_id]
                idx = combo.findData(color_key)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.detected_colors[slot_id] = color_key

            if slot_id in self.slot_conf_labels:
                col_name = COLOR_PALETTE.get(color_key, {}).get("name", color_key)
                self.slot_conf_labels[slot_id].setText(f"{int(conf * 100)}%")
                self.slot_conf_labels[slot_id].setStyleSheet("font-size: 9px; color: #10B981; font-weight: bold;")

    def _on_retake_clicked(self):
        """Unfreeze and return to live stream."""
        self.is_frozen = False
        self.viewfinder.set_detected_results(None)
        self.btn_capture.setEnabled(True)
        self.btn_retake.setEnabled(False)
        self.btn_apply.setEnabled(False)
        for lbl in self.slot_conf_labels.values():
            lbl.setText("รอสแกน")
            lbl.setStyleSheet("font-size: 9px; color: #64748B;")

    def _on_apply_clicked(self):
        """
        Apply detected/confirmed colors to Grid3x3Model.
        Strict contract: Only updates slot.color. Never touches x, y, z, r coordinates.
        """
        final_colors: Dict[int, str] = {}
        for s_id, combo in self.slot_preview_combos.items():
            col_key = combo.currentData()
            final_colors[s_id] = col_key
            # Update model safely
            self.grid_model.set_slot_color(s_id, col_key)

        self.sig_colors_applied.emit(final_colors)
        self.accept()

    def _stop_current_stream(self):
        if self._using_shared_camera and self.camera_widget and hasattr(self.camera_widget, "worker") and self.camera_widget.worker:
            try:
                self.camera_widget.worker.sig_frame_ready.disconnect(self._on_stream_frame)
            except Exception:
                pass
            self._using_shared_camera = False

        if self.worker:
            self.worker.stop()
            self.worker = None

    def closeEvent(self, event):
        self._stop_current_stream()
        super().closeEvent(event)
