import logging
import threading
from typing import Protocol

from . import network, types, util

LOG = logging.getLogger(__name__)


class ControllerCommon(Protocol):
    """Protocol for the fundamental controller interface shared by sync/async implementations"""

    _action_sequence_last_sent: int
    _mcio_conn: network._Connection

    def send_action(self, action: network.ActionPacket) -> None:
        """Send action to minecraft. Automatically sets action.sequence."""
        self._action_sequence_last_sent += 1
        action.sequence = self._action_sequence_last_sent
        self._mcio_conn.send_action(action)

    def send_stop(self) -> None:
        """Send a stop packet to Minecraft. This should cause Minecraft to cleanly exit."""
        self._mcio_conn.send_stop()

    def recv_observation(self) -> network.ObservationPacket: ...
    def close(self) -> None: ...


class ControllerSync(ControllerCommon):
    """
    Handles SYNC mode connections to Minecraft.
    Blocks in recv waiting for a new observation.
    """

    def __init__(
        self,
        *,
        action_port: int | None = None,
        observation_port: int | None = None,
        wait_for_connection: bool = True,
        connection_timeout: float | None = None,
    ):
        self._action_sequence_last_sent = 0
        self._mcio_conn = network._Connection(
            action_port=action_port,
            observation_port=observation_port,
            wait_for_connection=wait_for_connection,
            connection_timeout=connection_timeout,
        )
        self.check_mode = True

    def recv_observation(
        self, block: bool = True, timeout: float | None = None
    ) -> network.ObservationPacket:
        """Receive observation. Always blocks - ignores block and timeout args"""
        obs = self._mcio_conn.recv_observation(block=True)
        if obs is None:
            # Exiting or packet decode error
            return network.ObservationPacket()

        if self.check_mode:
            self.check_mode = False
            mode = types.MCioMode.SYNC
            if mode != obs.mode:
                LOG.warning(f"Mode-Mismatch controller={mode} mcio={obs.mode}")

        return obs

    def close(self) -> None:
        """Shut down the network connection"""
        self._mcio_conn.close()


class ControllerAsync(ControllerCommon):
    """
    Handles ASYNC mode connections to Minecraft
    """

    def __init__(
        self,
        *,
        action_port: int | None = None,
        observation_port: int | None = None,
        wait_for_connection: bool = True,
        connection_timeout: float | None = None,
    ):
        self._action_sequence_last_sent = 0

        self.process_counter = util.TrackPerSecond("ProcessObservationPPS")
        self.queued_counter = util.TrackPerSecond("QueuedActionsPPS")
        self.check_mode = True

        # Flag to signal observation thread to stop.
        self._running = threading.Event()
        self._running.set()

        self._observation_queue = util.LatestItemQueue[network.ObservationPacket]()
        self._mcio_conn = network._Connection(
            action_port=action_port,
            observation_port=observation_port,
            wait_for_connection=wait_for_connection,
            connection_timeout=connection_timeout,
        )

        # Start observation thread
        self._observation_thread = threading.Thread(
            target=self._observation_thread_fn, name="ObservationThread"
        )
        self._observation_thread.daemon = True
        self._observation_thread.start()

        LOG.info("Controller init complete")

    def recv_observation(
        self, block: bool = True, timeout: float | None = None
    ) -> network.ObservationPacket:
        """
        Returns the most recently received observation pulling it from the processing queue.
        Block and timeout are like queue.Queue.get().
        Can raise Empty exception if non-blocking or timeout is used.
        """
        # RECV 3
        observation = self._observation_queue.get(block=block, timeout=timeout)
        return observation

    def send_and_recv_match(
        self, action: network.ActionPacket, max_skip: int | None = 5
    ) -> network.ObservationPacket:
        """Send action to minecraft. Automatically sets action.sequence.
        This will ensure the next observation you receive came after this action.
        Since we're running in async mode, observations may be in flight that occurred
        before Minecraft processed this action.
        max_skip is the maximum number of observations to skip before giving up.
        Because the observations are stored in a LatestItemQueue, there shouldn't be
        many to skip - only observations that were in flight after the action was sent, but
        before Minecraft processed it. Generally we should only hit max_skip if something went
        wrong, like the action was dropped. This could happen, for example, when the agent
        starts before Minecraft.
        """
        self.send_action(action)
        wait_seq = self._action_sequence_last_sent
        n_skip = 0
        while True:
            observation = self._observation_queue.get()
            obs_action_seq = observation.last_action_sequence
            if obs_action_seq >= wait_seq:
                break
            n_skip += 1
            if max_skip is not None and n_skip >= max_skip:
                LOG.warning("Max-Skip")
                break
            LOG.debug(
                f"SKIPPING obs={observation.sequence} last_action={obs_action_seq} < waiting={wait_seq}"
            )
            # print(f"SKIPPING obs={observation.sequence} last_action={obs_action_seq} < waiting={wait_seq}")
        return observation

    def _observation_thread_fn(self) -> None:
        """Loops. Receives observation packets from minecraft and places on observation_queue"""
        LOG.info("ObservationThread start")
        while self._running.is_set():
            # RECV 2
            # I don't think we'll ever drop here. this is a short loop to recv the packet
            # and put it on the queue to be processed.
            observation = self._mcio_conn.recv_observation(block=True)
            if observation is None:
                continue  # Exiting or packet decode error

            if self.check_mode:
                self.check_mode = False
                mode = types.MCioMode.ASYNC
                if mode != observation.mode:
                    LOG.warning(
                        f"Mode-Mismatch controller={mode} mcio={observation.mode}"
                    )

            dropped = self._observation_queue.put(observation)
            if dropped:
                # This means the main (processing) thread isn't reading fast enough.
                # The first few are always dropped, presumably as we empty the initial zmq buffer
                # that built up during pause for "slow joiner syndrome".
                # XXX This should not longer happen since we're using push/pull? Change log level?
                LOG.debug("Dropped observation packet from processing queue")
                pass

        LOG.info("ObservationThread shut down")

    def close(self) -> None:
        """Shut down the network connection"""
        self._running.clear()
        self._mcio_conn.close()
        self._observation_thread.join()
