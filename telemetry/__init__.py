"""
Telemetry module for monitoring and logging robot performance.
"""

import time
import asyncio
from loguru import logger


class HzCounter:
    """Class to track and report execution frequency."""

    def __init__(self, name="", window_size=100, interval=5.0):
        """Initialize the Hz counter.

        Args:
            name: Name of the counter for logging
            window_size: Number of samples to use for calculating average Hz
            interval: Reporting interval in seconds
        """
        self.name = name
        self.window_size = window_size
        self.timestamps = []
        self.last_report_time = time.time()
        self.report_interval = interval  # Report interval in seconds

    def tick(self):
        """Record a tick and update the timestamps list."""
        now = time.time()
        self.timestamps.append(now)

        # Keep only the most recent window_size timestamps
        if len(self.timestamps) > self.window_size:
            self.timestamps = self.timestamps[-self.window_size :]

        # Report Hz periodically
        if now - self.last_report_time > self.report_interval:
            self.report_hz()
            self.last_report_time = now

    async def update(self):
        """Async version of tick for compatibility with async code."""
        self.tick()
        return

    def get_hz(self):
        """Calculate the current frequency in Hz."""
        if len(self.timestamps) < 2:
            return 0.0

        # Calculate time difference between first and last timestamp
        time_diff = self.timestamps[-1] - self.timestamps[0]
        if time_diff <= 0:
            return 0.0

        # Calculate Hz based on number of ticks and time difference
        count = len(self.timestamps) - 1
        return count / time_diff

    def report_hz(self):
        """Log the current Hz."""
        hz = self.get_hz()
        if self.name:
            logger.info(f"{self.name} running at {hz:.2f} Hz")
        else:
            logger.info(f"Running at {hz:.2f} Hz")
