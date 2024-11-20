import threading
import queue
import logging

from mcio_remote import network
from mcio_remote import LOG

class Controller:
    '''
    Handles the connections to minecraft. Uses two threads
    One pulls state packets from the _Connection recv socket and places them on the
    _state_queue. And one pulls action packets from the _action_queue and sends
    them through the _Connection send socket.
    Use send_action() and recv_state() to safely send/recv packets.
    To use match_sequences you must use send_and_recv()
    '''
    def __init__(self, host='localhost'):
        self.state_sequence_last_received = None
        self.state_sequence_last_processed = None
        self.action_sequence_last_queued = 0

        self.process_counter = network.TrackPerSecond('ProcessStatePPS')
        self.queued_counter = network.TrackPerSecond('QueuedActionsPPS')

        # Flag to signal threads to stop.
        self._running = threading.Event()
        self._running.set()

        self._action_queue = queue.Queue()
        self._state_queue = _LatestItemQueue()

        # This briefly sleeps for zmq initialization.
        self._mcio_conn = network._Connection()

        # Start threads
        self._action_thread = threading.Thread(target=self._action_thread_fn, name="ActionThread")
        self._action_thread.daemon = True
        self._action_thread.start()

        self._state_thread = threading.Thread(target=self._state_thread_fn, name="StateThread")
        self._state_thread.daemon = True
        self._state_thread.start()

        LOG.info("Controller init complete")

    def send_and_recv(self, action: network.ActionPacket) -> network.StatePacket:
        ''' Wrapper around send_and_recv_check for those who only want the state.  '''
        state, _ = self.send_and_recv_check(action)
        return state

    def send_and_recv_check(self, action: network.ActionPacket) -> tuple[network.StatePacket, bool]:
        '''
        Enqueue action and recv state until the state recorded after Minecraft completed the action.
        Return that state and flag denoting if Minecraft restarted, in which case the action was
        likely lost and the state is non-contiguous.
        '''
        action_seq = self.send_action(action)
        state, restarted = self._recv_and_match(action_seq)
        return state, restarted

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

    def recv_state(self, *args, **kwargs) -> network.StatePacket:
        ''' Wrapper around recv_check_state for those who only want the state.  '''
        state, _ = self.recv_check_state(*args, **kwargs)
        return state

    def recv_check_state(self, block=True, timeout=None) -> tuple[network.StatePacket, bool]:
        '''
        Returns the most recently received state pulling it from the processing queue.
        block and timeout are like queue.Queue.get(). Can raise Empty exception if
        non-blocking or timeout is used.
        Also returns bool denoting if Minecraft was restarted.
        '''
        # RECV 4
        state = self._state_queue.get(block=block, timeout=timeout)
        self._state_queue.task_done()

        restarted = False
        if self.state_sequence_last_processed is None:
            LOG.info(f'Processing first state packet: sequence={state.sequence}')
        elif state.sequence <= self.state_sequence_last_processed:
            # Minecraft must have restarted
            LOG.warning('Minecraft restarted')
            restarted = True
        self._track_dropped("Process", state, self.state_sequence_last_processed)

        self.state_sequence_last_processed = state.sequence
        self.process_counter.count()

        return state, restarted
    
    def _recv_and_match(self, action_sequence) -> tuple[network.StatePacket, bool]:
        # Keep receiving until we receive state recorded after the action
        # Returns state and bool denoting if Minecraft restarted.
        first_state = self.state_sequence_last_processed is None
        while True:
            state, restarted = self.recv_check_state(block=True)

            # Detect if the action we're trying to match was lost, in which case we'll never
            # get a match.
            if restarted:
                # Minecraft restarted. Just return this state.
                # state.last_action_sequence < action_sequence, but Minecraft probably
                # lost the action for action_sequence
                LOG.debug(f'Minecraft-Restart '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={state.last_action_sequence} '
                        f'state_sequence={state.sequence}'
                        )
                return state, True

            elif first_state and action_sequence == 1 and state.sequence == 0:
                # Minecraft started after agent. Just count this as another case of restarted?
                LOG.debug(f'Minecraft-Start-Last '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={state.last_action_sequence} '
                        f'state_sequence={state.sequence}'
                        )
                return state, False

            # Now handling normal cases
            elif state.last_action_sequence >= action_sequence:
                # Received an up-to-date state. Return it.

                # XXX If the agent restarts we'll mistakenly process any states that were in flight
                # E.g., Use-State last_sent=1 server_last_processed=256
                LOG.debug(f'Use-State '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={state.last_action_sequence} '
                        f'state_sequence={state.sequence}'
                )
                break

            else:
                # This is skipping through states that were in flight before Minecraft
                # received the action.
                LOG.debug(f'Skip-State '
                        f'last_sent={self.action_sequence_last_queued} '
                        f'server_last_processed={state.last_action_sequence} '
                        f'state_sequence={state.sequence}'
                        )
                # Continue loop
        
        return state, False

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

    def _state_thread_fn(self):
        ''' Loops. Receives state packets from minecraft and places on state_queue'''
        LOG.info("StateThread start")
        while self._running.is_set():
            # RECV 2
            state = self._mcio_conn.recv_state()
            if state is None:
                continue    # Exiting or packet decode error

            # I don't think we'll ever drop here. This is a short loop to recv the packet
            # and put it on the queue to be processed. Check to make sure.
            if self.state_sequence_last_received is None:
                LOG.info(f'Recv first state packet: sequence={state.sequence}')
            self._track_dropped("Recv", state, self.state_sequence_last_received)
            self.state_sequence_last_received = state.sequence

            dropped = self._state_queue.put(state)
            if dropped:
                # This means the main (processing) thread isn't reading fast enough. 
                # The first few are always dropped, presumably as we empty the initial zmq buffer
                # that built up during pause for "slow joiner syndrome". Once that's done
                # any future drops will be logged by the processing thread.
                LOG.debug('Dropped state packet from processing queue')
                pass

        LOG.info("StateThread shut down")

    def _track_dropped(self, tag:str, state:network.StatePacket, last_sequence:int):
        ''' Calculations to see if we've dropped any state packets '''
        if last_sequence == None or state.sequence <= last_sequence:
            # Start / Reset
            pass
        elif state.sequence > last_sequence + 1:
            # Dropped
            n_dropped = state.sequence - last_sequence - 1
            LOG.info(f'State packets dropped: tag={tag} n_dropped={n_dropped}')

    def shutdown(self):
        # XXX
        '''
        self._running.clear()
        self._mcio_conn.close()

        self._state_thread.join()
        # Send empty action to unblock ActionThread
        self._action_queue.put(None)
        self._action_thread.join()
        '''
        ...


class _LatestItemQueue(queue.Queue):
    ''' 
        Queue that only saves the most recent item.
        Puts replace any item on the queue.
        If the agents gets behind on state, just keep the most recent.
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
