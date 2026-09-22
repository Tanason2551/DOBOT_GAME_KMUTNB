"""
Modern Dark Theme Styling for Dobot Desktop GUI (Compact & Proportional Fonts)
"""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #121318;
    color: #E2E8F0;
    font-family: 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 11px;
}

QWidget {
    color: #E2E8F0;
    font-size: 11px;
}

QTabWidget::pane {
    border: 1px solid #232733;
    background-color: #16171E;
    border-radius: 6px;
    padding: 6px;
}

QTabBar::tab {
    background: #1C1E26;
    color: #94A3B8;
    padding: 7px 16px;
    margin-right: 3px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 600;
    font-size: 11px;
}

QTabBar::tab:selected {
    background: #2563EB;
    color: #FFFFFF;
}

QTabBar::tab:hover:!selected {
    background: #252834;
    color: #F1F5F9;
}

QGroupBox {
    border: 1px solid #28303F;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    background-color: #181A22;
    font-weight: bold;
    font-size: 11px;
    color: #60A5FA;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    background-color: #181A22;
}

QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 11px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #1D4ED8;
}

QPushButton:pressed {
    background-color: #1E40AF;
}

QPushButton:disabled {
    background-color: #2D3748;
    color: #64748B;
}

QPushButton#btn_estop {
    background-color: #DC2626;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 800;
    padding: 6px 16px;
    border-radius: 6px;
}

QPushButton#btn_estop:hover {
    background-color: #B91C1C;
}

QPushButton#btn_estop:pressed {
    background-color: #991B1B;
}

QPushButton#btn_action_green {
    background-color: #059669;
}

QPushButton#btn_action_green:hover {
    background-color: #047857;
}

QPushButton#btn_action_amber {
    background-color: #D97706;
}

QPushButton#btn_action_amber:hover {
    background-color: #B45309;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0F1015;
    border: 1px solid #2D3748;
    border-radius: 4px;
    padding: 4px 8px;
    color: #F8FAFC;
    font-size: 11px;
    selection-background-color: #2563EB;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #3B82F6;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background-color: #181A22;
    border: 1px solid #2D3748;
    selection-background-color: #2563EB;
    color: #F8FAFC;
    font-size: 11px;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #2D3748;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #3B82F6;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #60A5FA;
    border: 2px solid #181A22;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #93C5FD;
}

QTableWidget {
    background-color: #0F1015;
    border: 1px solid #242B38;
    gridline-color: #181A22;
    border-radius: 5px;
    color: #E2E8F0;
    font-size: 11px;
}

QHeaderView::section {
    background-color: #181A22;
    color: #94A3B8;
    padding: 4px 6px;
    border: 1px solid #242B38;
    font-weight: 600;
    font-size: 11px;
}

QTableWidget::item:selected {
    background-color: #1D4ED8;
    color: #FFFFFF;
}

QTextEdit, QPlainTextEdit {
    background-color: #0B0C10;
    border: 1px solid #242B38;
    border-radius: 5px;
    color: #A7F3D0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
}

QScrollBar:vertical {
    background: #0F1015;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #2D3748;
    min-height: 16px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3B82F6;
}
"""
