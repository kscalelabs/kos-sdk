import time
from loguru import logger

class HzCounter:
    def __init__(self, interval=1.0):
        self.interval = interval              
        self.count = 0
        self.last_time = time.perf_counter()
    
    def update(self):
        self.count += 1
        now = time.perf_counter()
        elapsed = now - self.last_time
        if elapsed >= self.interval:
            frequency = self.count / elapsed
            logger.info(f"Control loop frequency: {frequency:.2f} Hz")
            self.count = 0
            self.last_time = now
