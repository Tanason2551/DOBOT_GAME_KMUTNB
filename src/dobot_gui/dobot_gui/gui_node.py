#!/usr/bin/env python3
"""
Dobot GUI Node Entry Point
"""

import sys
import os

from .qt_compat import is_qt_available, QT_LIB, IMPORT_ERRORS

def main():
    if not is_qt_available():
        print("=" * 60)
        print("Error: No Qt GUI library found or failed to load!")
        if IMPORT_ERRORS:
            print("Import details:")
            for err in IMPORT_ERRORS:
                print(f"  - {err}")
        print("\nPlease install PySide6 and system OpenGL library by running:")
        print("    sudo apt install python3-pyside6 libgl1")
        print("or:")
        print("    pip install PySide6 pyserial --break-system-packages")
        print("============================================================")
        sys.exit(1)

    # Now import Qt widgets safely
    from .qt_compat import QtWidgets
    from .main_window import DobotMainWindow

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Dobot ROS 2 Control Suite")
    app.setOrganizationName("Robotics")

    window = DobotMainWindow()
    window.show()

    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())


if __name__ == "__main__":
    main()
