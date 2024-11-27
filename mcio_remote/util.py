import queue

class LatestItemQueue(queue.Queue):
    '''
        Threadsafe Queue that only saves the most recent item.
        Puts replace any item on the queue.
    '''
    def __init__(self):
        super().__init__(maxsize=1)

    def put(self, item) -> bool:
        ''' Return True if the previous packet had to be dropped '''
        dropped = False
        try:
            # Discard the current item if the queue isn't empty
            x = self.get_nowait()
            dropped = True
        except queue.Empty:
            pass

        super().put(item)
        return dropped

    def get(self, block=True, timeout=None):
        '''
        The same as Queue.get, except this automatically calls task_done()
        I'm not sure task_done() really matters for how we're using Queue.
        Can raise queue.Empty if non-blocking or timeout
        '''
        item = super().get(block=block, timeout=timeout)
        super().task_done()
        return item
