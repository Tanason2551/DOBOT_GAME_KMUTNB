#!/usr/bin/env python3
"""
Dobot Connection Watchdog and Health Diagnostics
Provides heartbeat monitoring, round-trip latency measurement (Ping ms),
communication timeout detection, safety interlock, and auto-reconnect.
"""

import time
import threading
from typing import Callable, Optional, Dict, Any


class ConnectionWatchdog:
    """Monitors connection health between ROS 2 / host and Dobot hardware."""

    STATE_DISCONNECTED = "DISCONNECTED"
    STATE_CONNECTING = "CONNECTING"
    STATE_CONNECTED = "CONNECTED"
    STATE_WARNING = "WARNING"
    STATE_TIMEOUT = "TIMEOUT"

    def __init__(self, driver, timeout_sec: float = 1.0, ping_rate_hz: float = 10.0):
        self.driver = driver
        self.timeout_sec = timeout_sec
        self.ping_interval = 1.0 / max(1.0, ping_rate_hz)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Metrics
        self.state = self.STATE_DISCONNECTED
        self.latency_ms = 0.0
        self.actual_rate_hz = 0.0
        self.last_successful_ping = 0.0
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_dropped = 0

        # Callbacks
        self.on_timeout_callbacks: list[Callable[[], None]] = []
        self.on_state_change_callbacks: list[Callable[[str, Dict[str, Any]], None]] = []

        # Auto-reconnect configuration
        self.auto_reconnect = True
        self._reconnect_interval = 2.0
        self._last_reconnect_attempt = 0.0

    def start(self):
        """Start the watchdog monitoring loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the watchdog loop."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def add_timeout_callback(self, cb: Callable[[], None]):
        """Register callback for safety interlock when communication times out."""
        self.on_timeout_callbacks.append(cb)

    def add_state_change_callback(self, cb: Callable[[str, Dict[str, Any]], None]):
        """Register callback for state transitions."""
        self.on_state_change_callbacks.append(cb)

    def _set_state(self, new_state: str):
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            status = self.get_health_status()
            for cb in self.on_state_change_callbacks:
                try:
                    cb(new_state, status)
                except Exception:
                    pass

    def _watchdog_loop(self):
        last_cycle_time = time.time()
        cycle_count = 0
        rate_timer = time.time()

        while self._running:
            start_ping = time.time()

            if self.driver and self.driver.is_connected:
                self.packets_sent += 1
                try:
                    # Query pose as lightweight heartbeat
                    t0 = time.time()
                    pose = self.driver.get_pose()
                    t1 = time.time()

                    if pose is not None and len(pose) == 8:
                        self.packets_received += 1
                        self.latency_ms = (t1 - t0) * 1000.0
                        self.last_successful_ping = time.time()

                        if self.latency_ms > 150.0:
                            self._set_state(self.STATE_WARNING)
                        else:
                            self._set_state(self.STATE_CONNECTED)
                    else:
                        self.packets_dropped += 1
                except Exception:
                    self.packets_dropped += 1

                # Check timeout
                time_since_last_success = time.time() - self.last_successful_ping
                if time_since_last_success > self.timeout_sec:
                    if self.state != self.STATE_TIMEOUT:
                        self._set_state(self.STATE_TIMEOUT)
                        # Trigger Safety Interlock
                        for cb in self.on_timeout_callbacks:
                            try:
                                cb()
                            except Exception:
                                pass
            else:
                self._set_state(self.STATE_DISCONNECTED)
                # Auto-reconnect attempt
                if self.auto_reconnect and (time.time() - self._last_reconnect_attempt > self._reconnect_interval):
                    self._last_reconnect_attempt = time.time()
                    try:
                        self._set_state(self.STATE_CONNECTING)
                        # Try reconnecting
                        if hasattr(self.driver, "_port") and self.driver._port:
                            success = self.driver.connect(port=self.driver._port)
                        else:
                            success = self.driver.connect()
                        if success:
                            self.last_successful_ping = time.time()
                            self._set_state(self.STATE_CONNECTED)
                    except Exception:
                        self._set_state(self.STATE_DISCONNECTED)

            # Calculate actual loop rate (Hz)
            cycle_count += 1
            if time.time() - rate_timer >= 1.0:
                self.actual_rate_hz = cycle_count / (time.time() - rate_timer)
                cycle_count = 0
                rate_timer = time.time()

            # Sleep remaining interval
            elapsed = time.time() - start_ping
            sleep_time = max(0.005, self.ping_interval - elapsed)
            time.sleep(sleep_time)

    def get_health_status(self) -> Dict[str, Any]:
        """Return snapshot of connection health and diagnostics."""
        loss_rate = 0.0
        if self.packets_sent > 0:
            loss_rate = (self.packets_dropped / self.packets_sent) * 100.0

        return {
            "state": self.state,
            "is_connected": (self.state in [self.STATE_CONNECTED, self.STATE_WARNING]),
            "latency_ms": round(self.latency_ms, 1),
            "actual_rate_hz": round(self.actual_rate_hz, 1),
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "packet_loss_percent": round(loss_rate, 1),
            "last_ping_ago_sec": round(time.time() - self.last_successful_ping, 2) if self.last_successful_ping > 0 else -1
        }
