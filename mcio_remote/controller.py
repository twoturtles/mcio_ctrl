import threading
import queue
import logging

from mcio_remote import network
from mcio_remote import LOG

class Controller:
    '''
    Handles the connections to minecraft. Uses two threads
    One pulls observation packets from the _Connection recv socket and places them on the
    _observation_queue. And one pulls action packets from the _action_queue and sends
    them through the _Connection send socket.
    Use send_action() and recv_observation() to safely send/recv packets.
    To use match_sequences you must use send_and_recv()
    '''
    def __init__(self, host='localhost'):
        self.observation_sequence_last_received = None
        self.observation_sequence_last_processed = None
        self.action_sequence_last_queued = 0

        self.process_counter = network.TrackPerSecond('ProcessObservationPPS')
        self.queued_counter = network.TrackPerSecond('QueuedActionsPPS')

        # Flag to signal threads to stop.
        self._running = threading.Event()
        self._running.set()

        self._action_queue = queue.Queue()
        self._observation_queue = _LatestItemQueue()

        # This briefly sleeps for zmq initialization.
        self._mcio_conn = network._Connection()

        # Start threads
        self._action_thread = threading.Thread(target=self._action_thread_fn, name="ActionThread")
        self._action_thread.daemon = True
        self._action_thread.start()

        self._observation_thread = threading.Thread(target=self._observation_thread_fn, name="ObservationThread")
        self._observation_thread.daemon = True
        self._observation_thread.start()

        LOG.info("Controller init complete")

    def send_and_recv(self, action: network.ActionPacket) -> network.ObservationPacket:
        ''' Wrapper around send_and_recv_check for those who only want the observation.  '''
        observation, _ = self.send_and_recv_check(action)
        return observation

    def send_and_recv_check(self, action: network.ActionPacket) -> tuple[network.ObservationPacket, bool]:
        '''
        Enqueue action and recv observation until the observation recorded after Minecraft completed the action.
        Return that observation and flag denoting if Minecraft restarted, in which case the action was
        likely lost and the observation is non-contiguous.
        '''
        action_seq = self.send_action(action)
        observation, restarted = self._recv_and_match(action_seq)
        return observation, restarted

    def send_action(self, action: network.ActionPacket) -> int:
        '''
        Send action to minecraft. Doesn't actually send. Places the packet on the queue
        to be sent by the action thread.
        Also updates action_sequence_last_queued
        Returns the sequence number used
        '''
        new_seq = self.action_sequence_last_queued + 1
        action.sequence = new_seq
        self.queued_counter.count()
        LOG.debug(f'Queue action: {action}')
        self._action_queue.put(action)
        self.action_sequence_last_queued = new_seq
        return new_seq

    def recv_observation(self, *args, **kwargs) -> network.ObservationPacket:
        ''' Wrapper around recv_check_observation for those who only want the observation.  '''
        observation, _ = self.recv_check_observation(*args, **kwargs)
        return observation

    def recv_check_observation(self, block=True, timeout=None) -> tuple[network.ObservationPacket, bool]:
        '''
        Returns the most recently received observation pulling it from the processing queue.
        block and timeout are like queue.Queue.get(). Can raise Empty exception if
        non-blocking or timeout is used.
        Also returns bool denoting if Minecraft was restarted.
        '''
        # RECV 4
        observation = self._observation_queue.get(block=block, timeout=timeout)
        self._observation_queue.task_done()

        restarted = False
        if self.observation_sequence_last_processed is None:
            LOG.info(f'Processing first observation packet: sequence={observation.sequence}')
        elif observation.sequence <= self.observation_sequence_last_processed:
            # Minecraft must have restarted
            LOG.warning('Minecraft restarted')
            restarted = True
        self._track_dropped("Process", observation, self.observation_sequence_last_processed)

        self.observation_sequence_last_processed = observation.sequence
        self.process_counter.count()

        return observation, restarted
    
    def _recv_and_match(self, action_sequence) -> tuple[network.ObservationPacket, bool]:
        # Keep receiving until we receive observation recorded after the action
        # Returns observation and bool denoting if Minecraft restarted.
        first_observation = self.observation_sequence_last_processed is None
        while True:
            observation, restarted = self.recv_check_observation(block=True)

            # Detect if the action we're trying to match was lost, in which case we'll never
            # get a match.
            if restarted:
                # Minecraft restarted. Just return this observation.
                # observation.last_action_sequence < action_sequence, but Minecraft probably
                # lost the action for action_sequence
                LOG.debug(f'Minecraft-Restart '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={observation.last_action_sequence} '
                        f'observation_sequence={observation.sequence}'
                        )
                return observation, True

            elif first_observation and action_sequence == 1 and observation.sequence == 0:
                # Minecraft started after agent. Just count this as another case of restarted?
                LOG.debug(f'Minecraft-Start-Last '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={observation.last_action_sequence} '
                        f'observation_sequence={observation.sequence}'
                        )
                return observation, False

            # Now handling normal cases
            elif observation.last_action_sequence >= action_sequence:
                # Received an up-to-date observation. Return it.

                # XXX If the agent restarts we'll mistakenly process any observations that were in flight
                # E.g., Use-Observation last_sent=1 server_last_processed=256
                LOG.debug(f'Use-Observation '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={observation.last_action_sequence} '
                        f'observation_sequence={observation.sequence}'
                )
                break

            else:
                # This is skipping through observations that were in flight before Minecraft
                # received the action.
                LOG.debug(f'Skip-Observation '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={observation.last_action_sequence} '
                        f'observation_sequence={observation.sequence}'
                        )
                # Continue loop
        
        return observation, False

    def _action_thread_fn(self):
        ''' Loops. Pulls packets from the action_queue and sends to minecraft. '''
        LOG.info("ActionThread start")
        while self._running.is_set():
            action = self._action_queue.get()
            self._action_queue.task_done()
            if action is None:
                break   # Action None to signal exit
            self._mcio_conn.send_action(action)
        LOG.info("Action-Thread shut down")

    def _observation_thread_fn(self):
        ''' Loops. Receives observation packets from minecraft and places on observation_queue'''
        LOG.info("ObservationThread start")
        while self._running.is_set():
            # RECV 2
            observation = self._mcio_conn.recv_observation()
            if observation is None:
                continue    # Exiting or packet decode error

            # I don't think we'll ever drop here. This is a short loop to recv the packet
            # and put it on the queue to be processed. Check to make sure.
            if self.observation_sequence_last_received is None:
                LOG.info(f'Recv first observation packet: sequence={observation.sequence}')
            self._track_dropped("Recv", observation, self.observation_sequence_last_received)
            self.observation_sequence_last_received = observation.sequence

            dropped = self._observation_queue.put(observation)
            if dropped:
                # This means the main (processing) thread isn't reading fast enough. 
                # The first few are always dropped, presumably as we empty the initial zmq buffer
                # that built up during pause for "slow joiner syndrome". Once that's done
                # any future drops will be logged by the processing thread.
                LOG.debug('Dropped observation packet from processing queue')
                pass

        LOG.info("ObservationThread shut down")

    def _track_dropped(self, tag:str, observation:network.ObservationPacket, last_sequence:int):
        ''' Calculations to see if we've dropped any observation packets '''
        if last_sequence == None or observation.sequence <= last_sequence:
            # Start / Reset
            pass
        elif observation.sequence > last_sequence + 1:
            # Dropped
            n_dropped = observation.sequence - last_sequence - 1
            LOG.info(f'Observation packets dropped: tag={tag} n_dropped={n_dropped}')

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
