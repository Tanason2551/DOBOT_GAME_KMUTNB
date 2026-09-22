"""
Interactive 3x3 Grid Widget with Cube Color Badges & Center Tower Stacking Visualizer
"""

from ..qt_compat import QtWidgets, QtCore, QtGui, Signal
from dobot_driver.pnp.grid_model import Grid3x3Model, SlotData, COLOR_PALETTE


class SlotTileWidget(QtWidgets.QFrame):
    """Individual tile for a perimeter slot on the 3x3 grid."""

    sig_clicked = Signal(int)

    def __init__(self, slot: SlotData, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.is_selected = False
        self._setup_ui()

    def _setup_ui(self):
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumSize(95, 95)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        self.lbl_id = QtWidgets.QLabel(f"S{self.slot.slot_id}")
        self.lbl_id.setStyleSheet("font-weight: 800; font-size: 13px; color: #94A3B8;")
        self.lbl_id.setAlignment(QtCore.Qt.AlignCenter)

        # Color Indicator Box
        self.lbl_color_cube = QtWidgets.QLabel("⬛")
        self.lbl_color_cube.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_color_cube.setStyleSheet("font-size: 24px;")

        self.lbl_status = QtWidgets.QLabel("มีลูกบาศก์")
        self.lbl_status.setStyleSheet("font-size: 10px; color: #10B981;")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.lbl_id)
        layout.addWidget(self.lbl_color_cube)
        layout.addWidget(self.lbl_status)

        self.update_appearance()

    def update_appearance(self):
        color_info = COLOR_PALETTE.get(self.slot.color, COLOR_PALETTE["red"])
        hex_col = color_info["hex"]

        if self.slot.has_cube:
            self.lbl_color_cube.setText("■")
            self.lbl_color_cube.setStyleSheet(f"color: {hex_col}; font-size: 28px;")
            self.lbl_status.setText(color_info["name"])
            self.lbl_status.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {hex_col};")
            bg_color = "#1E222D"
            border_color = hex_col if self.is_selected else "#2E3446"
        else:
            self.lbl_color_cube.setText("□")
            self.lbl_color_cube.setStyleSheet("color: #475569; font-size: 24px;")
            self.lbl_status.setText("หยิบไปแล้ว")
            self.lbl_status.setStyleSheet("font-size: 10px; color: #64748B;")
            bg_color = "#14161E"
            border_color = "#334155"

        border_w = "2px" if self.is_selected else "1px"
        self.setStyleSheet(f"""
            SlotTileWidget {{
                background-color: {bg_color};
                border: {border_w} solid {border_color};
                border-radius: 8px;
            }}
            SlotTileWidget:hover {{
                border: 2px solid #3B82F6;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.sig_clicked.emit(self.slot.slot_id)
        super().mousePressEvent(event)


class CenterStackTileWidget(QtWidgets.QFrame):
    """Special Center tile showing real-time 3D-like stacked layers."""

    sig_clicked = Signal(int)

    def __init__(self, slot: SlotData, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.stacked_layers = []
        self._setup_ui()

    def _setup_ui(self):
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumSize(110, 110)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(3)
        self.layout.setAlignment(QtCore.Qt.AlignBottom)

        self.lbl_header = QtWidgets.QLabel("🏢 CENTER STACK")
        self.lbl_header.setStyleSheet("font-weight: 800; font-size: 11px; color: #F59E0B;")
        self.lbl_header.setAlignment(QtCore.Qt.AlignCenter)

        self.stack_container = QtWidgets.QVBoxLayout()
        self.stack_container.setSpacing(2)
        self.stack_container.setAlignment(QtCore.Qt.AlignBottom)

        self.lbl_count = QtWidgets.QLabel("0 Layers")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8;")
        self.lbl_count.setAlignment(QtCore.Qt.AlignCenter)

        self.layout.addWidget(self.lbl_header)
        self.layout.addLayout(self.stack_container, 1)
        self.layout.addWidget(self.lbl_count)

        self.setStyleSheet("""
            CenterStackTileWidget {
                background-color: #181B24;
                border: 2px dashed #F59E0B;
                border-radius: 8px;
            }
            CenterStackTileWidget:hover {
                border: 2px solid #FBBF24;
            }
        """)

    def update_stack(self, stacked_layers: list):
        """Redraw stacked colored bars from bottom to top."""
        self.stacked_layers = stacked_layers
        # Clear existing layer bars
        while self.stack_container.count():
            item = self.stack_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not stacked_layers:
            empty_lbl = QtWidgets.QLabel("พื้นที่วางซ้อน\n(ว่าง)")
            empty_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.stack_container.addWidget(empty_lbl)
            self.lbl_count.setText("0 Layers")
        else:
            # Render each layer as a colored horizontal bar (top layer at top, bottom at bottom)
            for idx, color_key in enumerate(reversed(stacked_layers)):
                layer_num = len(stacked_layers) - idx
                color_info = COLOR_PALETTE.get(color_key, COLOR_PALETTE["red"])
                hex_col = color_info["hex"]

                bar = QtWidgets.QLabel(f"L{layer_num}: {color_info['name']}")
                bar.setFixedHeight(18)
                bar.setAlignment(QtCore.Qt.AlignCenter)
                bar.setStyleSheet(f"""
                    background-color: {hex_col};
                    color: #FFFFFF;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 3px;
                """)
                self.stack_container.addWidget(bar)

            self.lbl_count.setText(f"{len(stacked_layers)} Layers")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.sig_clicked.emit(self.slot.slot_id)
        super().mousePressEvent(event)


class Grid3x3Widget(QtWidgets.QWidget):
    """Complete 3x3 interactive arena grid component."""

    sig_slot_selected = Signal(int)

    def __init__(self, grid_model: Grid3x3Model, parent=None):
        super().__init__(parent)
        self.grid_model = grid_model
        self.tiles: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        grid = QtWidgets.QGridLayout(self)
        grid.setSpacing(8)
        grid.setContentsMargins(4, 4, 4, 4)

        # Place tiles in 3x3 grid
        for slot_id, slot in self.grid_model.slots.items():
            if slot_id == 9:
                center_tile = CenterStackTileWidget(slot)
                center_tile.sig_clicked.connect(self._on_tile_clicked)
                self.tiles[slot_id] = center_tile
                grid.addWidget(center_tile, slot.row, slot.col)
            else:
                tile = SlotTileWidget(slot)
                tile.sig_clicked.connect(self._on_tile_clicked)
                self.tiles[slot_id] = tile
                grid.addWidget(tile, slot.row, slot.col)

    def _on_tile_clicked(self, slot_id: int):
        # Deselect others
        for s_id, tile in self.tiles.items():
            if hasattr(tile, "is_selected"):
                tile.is_selected = (s_id == slot_id)
                tile.update_appearance()
        self.sig_slot_selected.emit(slot_id)

    def refresh(self):
        """Update all tiles with current model data."""
        for slot_id, slot in self.grid_model.slots.items():
            tile = self.tiles.get(slot_id)
            if slot_id == 9 and isinstance(tile, CenterStackTileWidget):
                tile.update_stack(self.grid_model.stacked_layers)
            elif isinstance(tile, SlotTileWidget):
                tile.slot = slot
                tile.update_appearance()
