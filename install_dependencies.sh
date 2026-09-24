#!/usr/bin/env bash
# Installation script for Dobot Control Suite dependencies

echo "=== Installing Dobot ROS 2 Suite Dependencies ==="

# Python dependencies
python3 -m pip install --upgrade pip
python3 -m pip install PySide6 pyserial

# Add user to dialout group for USB Serial permission
echo "Checking USB Serial permissions..."
if ! groups $USER | grep -q '\bdialout\b'; then
    echo "Adding $USER to 'dialout' group to access /dev/ttyUSB*..."
    sudo usermod -a -G dialout $USER
    echo "NOTE: You may need to log out and log back in for serial group permissions to take effect."
fi

# Make run script executable
chmod +x run_gui.sh
chmod +x run_gui.py

echo "=== Dependencies installed successfully! ==="
