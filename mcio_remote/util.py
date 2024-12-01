import time
import queue

from . import logger

LOG = logger.LOG.get_logger(__name__)


class LatestItemQueue(queue.Queue):
    """
    Threadsafe Queue that only saves the most recent item.
    Puts replace any item on the queue.
    """

    def __init__(self):
        super().__init__(maxsize=1)

    def put(self, item) -> bool:
        """Return True if the previous packet had to be dropped"""
        dropped = False
        try:
            # Discard the current item if the queue isn't empty
            self.get_nowait()
            dropped = True
        except queue.Empty:
            pass

        super().put(item)
        return dropped

    def get(self, block=True, timeout=None):
        """
        The same as Queue.get, except this automatically calls task_done()
        I'm not sure task_done() really matters for how we're using Queue.
        Can raise queue.Empty if non-blocking or timeout
        """
        item = super().get(block=block, timeout=timeout)
        super().task_done()
        return item


class TrackPerSecond:
    def __init__(self, name: str, log_time: float = 10.0):
        self.name = name
        self.log_time = log_time
        self.start = time.time()
        self.item_count = 0

    def count(self):
        end = time.time()
        self.item_count += 1
        if end - self.start >= self.log_time:
            per_sec = self.item_count / (end - self.start)
            LOG.info(f"{self.name}: {per_sec:.1f}")
            self.item_count = 0
            self.start = end
