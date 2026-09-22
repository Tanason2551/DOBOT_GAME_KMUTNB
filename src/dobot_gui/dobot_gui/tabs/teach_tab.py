"""
Teach and Playback (Waypoints Sequencing) Tab
"""

import json
import time
from ..qt_compat import QtWidgets, QtCore, QtGui, Signal, QThread


class SequenceWorker(QThread):
    """Background worker executing the waypoint sequence smoothly without freezing UI."""

    sig_step_started = Signal(int)
    sig_finished = Signal()
    sig_log = Signal(str, str)

    def __init__(self, bridge, waypoints, loop_enabled=False):
        super().__init__()
        self.bridge = bridge
        self.waypoints = waypoints
        self.loop_enabled = loop_enabled
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        while self._is_running:
            for idx, pt in enumerate(self.waypoints):
                if not self._is_running:
                    break

                self.sig_step_started.emit(idx)
                self.sig_log.emit("CMD", f"Executing Point {idx+1}: {pt.get('name', 'P')} -> ({pt['x']:.1f}, {pt['y']:.1f}, {pt['z']:.1f})")

                # Move to coordinate
                self.bridge.send_ptp(pt["x"], pt["y"], pt["z"], pt["r"], mode=pt.get("mode", 2))

                # Allow travel time based on distance
                time.sleep(1.2)

                # Set end-effector states
                if "suction" in pt:
                    self.bridge.set_suction_cup(pt["suction"])
                if "gripper" in pt:
                    self.bridge.set_gripper(pt["gripper"])

                # Wait delay
                delay = float(pt.get("delay", 0.5))
                if delay > 0:
                    time.sleep(delay)

            if not self.loop_enabled or not self._is_running:
                break

        self.sig_finished.emit()


class TeachTab(QtWidgets.QWidget):
    """Teach & Playback interface for programming waypoints and automated routines."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

        self._curr_x = 220.0
        self._curr_y = 0.0
        self._curr_z = 50.0
        self._curr_r = 0.0
        self._curr_suction = False
        self._curr_gripper = False

        self._seq_worker = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # Top Control Bar
        top_bar = QtWidgets.QHBoxLayout()
        self.btn_record = QtWidgets.QPushButton("📍 บันทึกตำแหน่งปัจจุบัน (Record Point)")
        self.btn_record.setObjectName("btn_action_green")
        self.btn_record.setMinimumHeight(38)

        self.btn_move_to_selected = QtWidgets.QPushButton("🎯 ไปยังจุดที่เลือก (Go to Selected)")
        self.btn_move_to_selected.setMinimumHeight(38)

        self.btn_up = QtWidgets.QPushButton("▲ ขึ้น")
        self.btn_down = QtWidgets.QPushButton("▼ ลง")
        self.btn_delete = QtWidgets.QPushButton("🗑️ ลบจุด")
        self.btn_clear = QtWidgets.QPushButton("Clear All")

        top_bar.addWidget(self.btn_record)
        top_bar.addWidget(self.btn_move_to_selected)
        top_bar.addSpacing(10)
        top_bar.addWidget(self.btn_up)
        top_bar.addWidget(self.btn_down)
        top_bar.addWidget(self.btn_delete)
        top_bar.addWidget(self.btn_clear)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Waypoint Table
        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "#", "ชื่อจุด (Label)", "X (mm)", "Y (mm)", "Z (mm)", "R (°)", "Delay (s)", "End-Effector"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Bottom Playback Bar
        bottom_bar = QtWidgets.QHBoxLayout()
        self.btn_play = QtWidgets.QPushButton("▶️ เริ่มทำงานตามลำดับ (Run Sequence)")
        self.btn_play.setObjectName("btn_action_green")
        self.btn_play.setMinimumHeight(40)

        self.btn_stop_seq = QtWidgets.QPushButton("⏹️ หยุดการทำงาน (Stop)")
        self.btn_stop_seq.setEnabled(False)
        self.btn_stop_seq.setMinimumHeight(40)

        self.chk_loop = QtWidgets.QCheckBox("🔄 วนซ้ำต่อเนื่อง (Loop Mode)")
        self.chk_loop.setStyleSheet("font-weight: bold; color: #60A5FA;")

        self.btn_save = QtWidgets.QPushButton("💾 บันทึกไฟล์ (Save JSON)")
        self.btn_load = QtWidgets.QPushButton("📂 เปิดไฟล์ (Load JSON)")

        bottom_bar.addWidget(self.btn_play)
        bottom_bar.addWidget(self.btn_stop_seq)
        bottom_bar.addSpacing(15)
        bottom_bar.addWidget(self.chk_loop)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_save)
        bottom_bar.addWidget(self.btn_load)
        layout.addLayout(bottom_bar)

    def _connect_signals(self):
        self.btn_record.clicked.connect(self._record_point)
        self.btn_move_to_selected.clicked.connect(self._move_to_selected)
        self.btn_up.clicked.connect(self._move_row_up)
        self.btn_down.clicked.connect(self._move_row_down)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_clear.clicked.connect(self._clear_all)

        self.btn_play.clicked.connect(self._start_sequence)
        self.btn_stop_seq.clicked.connect(self._stop_sequence)
        self.btn_save.clicked.connect(self._save_file)
        self.btn_load.clicked.connect(self._load_file)

        self.bridge.sig_pose_updated.connect(self._on_pose_update)
        self.bridge.sig_status_updated.connect(self._on_status_update)

    def _on_pose_update(self, x, y, z, r, j1, j2, j3, j4):
        self._curr_x, self._curr_y, self._curr_z, self._curr_r = x, y, z, r

    def _on_status_update(self, status: dict):
        self._curr_suction = status.get("suction_state", False)
        self._curr_gripper = status.get("gripper_state", False)

    def _record_point(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        effector_str = "None"
        if self._curr_suction:
            effector_str = "Suction: ON"
        elif self._curr_gripper:
            effector_str = "Gripper: GRIP"

        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"Waypoint {row + 1}"))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{self._curr_x:.1f}"))
        self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{self._curr_y:.1f}"))
        self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{self._curr_z:.1f}"))
        self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{self._curr_r:.1f}"))
        self.table.setItem(row, 6, QtWidgets.QTableWidgetItem("0.5"))
        self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(effector_str))

        self.table.selectRow(row)

    def _get_row_data(self, row: int) -> dict:
        name = self.table.item(row, 1).text()
        x = float(self.table.item(row, 2).text())
        y = float(self.table.item(row, 3).text())
        z = float(self.table.item(row, 4).text())
        r = float(self.table.item(row, 5).text())
        delay = float(self.table.item(row, 6).text())
        eff = self.table.item(row, 7).text()
        suction = "Suction: ON" in eff
        gripper = "Gripper: GRIP" in eff

        return {
            "name": name,
            "x": x, "y": y, "z": z, "r": r,
            "delay": delay,
            "suction": suction,
            "gripper": gripper,
            "mode": 2
        }

    def _move_to_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            pt = self._get_row_data(row)
            self.bridge.send_ptp(pt["x"], pt["y"], pt["z"], pt["r"], mode=2)
            self.bridge.set_suction_cup(pt["suction"])
            self.bridge.set_gripper(pt["gripper"])

    def _move_row_up(self):
        row = self.table.currentRow()
        if row > 0:
            data_prev = self._get_row_data(row - 1)
            data_curr = self._get_row_data(row)
            self._set_row_data(row - 1, data_curr)
            self._set_row_data(row, data_prev)
            self.table.selectRow(row - 1)

    def _move_row_down(self):
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount() - 1:
            data_next = self._get_row_data(row + 1)
            data_curr = self._get_row_data(row)
            self._set_row_data(row + 1, data_curr)
            self._set_row_data(row, data_next)
            self.table.selectRow(row + 1)

    def _set_row_data(self, row: int, data: dict):
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(data["name"]))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{data['x']:.1f}"))
        self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{data['y']:.1f}"))
        self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{data['z']:.1f}"))
        self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{data['r']:.1f}"))
        self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(f"{data['delay']:.1f}"))
        eff = "Suction: ON" if data.get("suction") else ("Gripper: GRIP" if data.get("gripper") else "None")
        self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(eff))

    def _delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            # Re-index
            for r in range(self.table.rowCount()):
                self.table.item(r, 0).setText(str(r + 1))

    def _clear_all(self):
        self.table.setRowCount(0)

    def _start_sequence(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีจุด Waypoint ในตาราง กรุณากดบันทึกจุดก่อน")
            return

        waypoints = [self._get_row_data(r) for r in range(self.table.rowCount())]
        self._seq_worker = SequenceWorker(self.bridge, waypoints, loop_enabled=self.chk_loop.isChecked())
        self._seq_worker.sig_step_started.connect(self._on_seq_step)
        self._seq_worker.sig_finished.connect(self._on_seq_finished)

        self.btn_play.setEnabled(False)
        self.btn_stop_seq.setEnabled(True)
        self._seq_worker.start()

    def _stop_sequence(self):
        if self._seq_worker:
            self._seq_worker.stop()
            self._seq_worker.wait(1000)
            self._seq_worker = None
        self.btn_play.setEnabled(True)
        self.btn_stop_seq.setEnabled(False)

    def _on_seq_step(self, step_idx: int):
        self.table.selectRow(step_idx)

    def _on_seq_finished(self):
        self.btn_play.setEnabled(True)
        self.btn_stop_seq.setEnabled(False)

    def _save_file(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "บันทึกไฟล์ Waypoints", "dobot_sequence.json", "JSON Files (*.json)")
        if path:
            pts = [self._get_row_data(r) for r in range(self.table.rowCount())]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(pts, f, indent=2, ensure_ascii=False)

    def _load_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "เปิดไฟล์ Waypoints", "", "JSON Files (*.json)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                pts = json.load(f)
            self.table.setRowCount(0)
            for p in pts:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(row + 1)))
                self._set_row_data(row, p)
