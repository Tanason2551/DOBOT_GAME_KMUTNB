"""
Qt Compatibility Layer
Seamlessly supports PySide6, PyQt6, and PyQt5.
"""

import sys

QT_LIB = None
IMPORT_ERRORS = []

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Signal, Slot, QThread, QTimer, Qt
    QT_LIB = "PySide6"
except Exception as e:
    IMPORT_ERRORS.append(f"PySide6: {e}")
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QThread, QTimer, Qt
        QT_LIB = "PyQt6"
    except Exception as e6:
        IMPORT_ERRORS.append(f"PyQt6: {e6}")
        try:
            from PyQt5 import QtCore, QtGui, QtWidgets
            from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, QThread, QTimer, Qt
            QT_LIB = "PyQt5"
        except Exception as e5:
            IMPORT_ERRORS.append(f"PyQt5: {e5}")

if QT_LIB is None:
    QtWidgets = None
    QtCore = None
    QtGui = None
    Signal = lambda *args, **kwargs: None
    Slot = lambda *args, **kwargs: None
    class QThread:
        pass
    class QTimer:
        pass
    class Qt:
        pass

def is_qt_available() -> bool:
    return QT_LIB is not None
