import time
import asyncio
from loguru import logger


class HzCounter:
    def __init__(self, interval):
        self.interval = interval
        self.count = 0
        self.start_time = time.perf_counter()

    async def update(self):
        self.count += 1
        now = time.perf_counter()
        if now - self.start_time >= self.interval:
            frequency = self.count / (now - self.start_time)
            logger.info(f"Loop frequency: {frequency:.2f} Hz")
            self.start_time = now
            self.count = 0
