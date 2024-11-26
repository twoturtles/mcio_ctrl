import threading
import queue
import logging

from mcio_remote import network
from mcio_remote import LOG

class ControllerSync:
    '''
    Handles SYNC mode connections to Minecraft.
    Blocks in recv waiting for a new observation.
    '''
    # XXX Implement context manager
    def __init__(self, host='localhost'):
        self.action_sequence_last_sent = 0

        # This briefly sleeps for zmq initialization.
        self._mcio_conn = network._Connection()

    def send_action(self, action: network.ActionPacket):
        ''' Send action to minecraft. Automatically sets action.sequence.  '''
        self.action_sequence_last_sent += 1
        action.sequence = self.action_sequence_last_sent
        self._mcio_conn.send_action(action)

    def recv_observation(self) -> network.ObservationPacket:
        ''' Receive observation. Blocks '''
        return self._mcio_conn.recv_observation()

    def close(self):
        ''' Shut down the network connection '''
        self._mcio_conn.close()
        self._mcio_conn = None

class ControllerAsync:
    '''
    Handles ASYNC mode connections to Minecraft
    '''
    def __init__(self, host='localhost'):
        self.action_sequence_last_sent = 0

        self.process_counter = network.TrackPerSecond('ProcessObservationPPS')
        self.queued_counter = network.TrackPerSecond('QueuedActionsPPS')

        # Flag to signal observation thread to stop.
        self._running = threading.Event()
        self._running.set()

        self._observation_queue = _LatestItemQueue()

        # This briefly sleeps for zmq initialization.
        self._mcio_conn = network._Connection()

        # Start observation thread
        self._observation_thread = threading.Thread(target=self._observation_thread_fn, name="ObservationThread")
        self._observation_thread.daemon = True
        self._observation_thread.start()

        LOG.info("Controller init complete")

    def send_action(self, action: network.ActionPacket):
        '''
        Send action to minecraft. Automatically sets action.sequence.
        Returns the sequence number used
        '''
        self.action_sequence_last_sent += 1
        action.sequence = self.action_sequence_last_sent
        self._mcio_conn.send_action(action)
        return self.action_sequence_last_sent

    def recv_observation(self, block=True, timeout=None) -> network.ObservationPacket:
        '''
        Returns the most recently received observation pulling it from the processing queue.
        Block and timeout are like queue.Queue.get(). 
        Can raise Empty exception if non-blocking or timeout is used.
        '''
        # RECV 3
        observation = self._observation_queue.get(block=block, timeout=timeout)
        self._observation_queue.task_done()
        return observation

    def _observation_thread_fn(self):
        ''' Loops. Receives observation packets from minecraft and places on observation_queue'''
        LOG.info("ObservationThread start")
        while self._running.is_set():
            # RECV 2
            # I don't think we'll ever drop here. this is a short loop to recv the packet
            # and put it on the queue to be processed.
            observation = self._mcio_conn.recv_observation()
            if observation is None:
                continue    # Exiting or packet decode error

            dropped = self._observation_queue.put(observation)
            if dropped:
                # This means the main (processing) thread isn't reading fast enough. 
                # The first few are always dropped, presumably as we empty the initial zmq buffer
                # that built up during pause for "slow joiner syndrome".
                LOG.debug('Dropped observation packet from processing queue')
                pass

        LOG.info("ObservationThread shut down")

    def shutdown(self):
        # XXX
        '''
        self._running.clear()
        self._mcio_conn.close()

        self._observation_thread.join()
        # Send empty action to unblock ActionThread
        self._action_queue.put(None)
        self._action_thread.join()
        '''
        ...


class _LatestItemQueue(queue.Queue):
    ''' 
        Queue that only saves the most recent item.
        Puts replace any item on the queue.
        If the agents gets behind on observation, just keep the most recent.
    '''
    def __init__(self):
        super().__init__(maxsize=1)

    def put(self, item) -> bool:
        ''' Return True if the previous packet had to be dropped '''
        # RECV 3
        dropped = False
        try:
            # Discard the current item if the queue isn't empty
            x = self.get_nowait()
            dropped = True
        except queue.Empty:
            pass

        super().put(item)
        return dropped
