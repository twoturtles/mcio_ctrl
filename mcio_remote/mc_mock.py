"""Used for testing. Simulate MCio running on Minecraft."""

import logging
import multiprocessing as mp
from multiprocessing.synchronize import Event as mpEvent
from typing import Any

import zmq

from . import network, types, util

LOG = logging.getLogger(__name__)


class GenerateObservation(mp.Process):
    """Inherit from this class to generate custom observations"""

    def __init__(
        self,
        mp_ctx: mp.context.BaseContext,
        running: mpEvent,
        log_level: int,
        options: dict[Any, Any] | None = None,
    ) -> None:
        super().__init__()
        self.running = running
        self.mp_ctx = mp_ctx
        self.log_level = log_level
        self.initialize(options)

    def run(self) -> None:
        util.logging_init(level=self.log_level)
        context = zmq.Context()
        socket = context.socket(zmq.PUSH)
        socket.bind(f"tcp://{types.DEFAULT_HOST}:{types.DEFAULT_OBSERVATION_PORT}")

        LOG.info(f"{mp.current_process().name} started")
        while self.running.is_set():
            try:
                obs = self.generate_observation()
                socket.send(obs.pack())
            except Exception as e:
                LOG.error(f"Error in observation generation: {e}")

        socket.close()
        context.term()
        LOG.info(f"{mp.current_process().name} done")

    def initialize(self, options: dict[Any, Any] | None) -> None:
        """Override for custom initialization"""
        pass

    def generate_observation(self) -> network.ObservationPacket:
        """Override for custom observation generation"""
        return network.ObservationPacket()


class ProcessAction(mp.Process):
    """Inherit from this class to do custom processing of actions"""

    def __init__(
        self,
        mp_ctx: mp.context.BaseContext,
        running: mpEvent,
        log_level: int,
        options: dict[Any, Any] | None = None,
    ) -> None:
        super().__init__()
        self.running = running
        self.mp_ctx = mp_ctx
        self.log_level = log_level
        self.initialize(options)

    def run(self) -> None:
        util.logging_init(level=self.log_level)
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.bind(f"tcp://{types.DEFAULT_HOST}:{types.DEFAULT_ACTION_PORT}")

        LOG.info(f"{mp.current_process().name} started")
        while self.running.is_set():
            try:
                pbytes = socket.recv()
                act = network.ActionPacket.unpack(pbytes)
                self.process_action(act)
            except Exception as e:
                LOG.error(f"Error in action processing: {e}")

        socket.close()
        context.term()
        LOG.info(f"{mp.current_process().name} done")

    def initialize(self, options: dict[Any, Any] | None) -> None:
        """Override for custom initialization"""
        pass

    def process_action(self, action: network.ActionPacket) -> None:
        """Override for custom action processing"""
        pass


class MockMinecraft:
    """
    Provide the Minecraft side of the MCio connection for testing. Uses multiprocessing to avoid the GIL
    """

    def __init__(
        self,
        generate_observation_class: type[GenerateObservation] = GenerateObservation,
        observation_options: dict[Any, Any] | None = None,
        process_action_class: type[ProcessAction] = ProcessAction,
        action_options: dict[Any, Any] | None = None,
    ) -> None:
        """
        Override the process classes to use custom behavior. These classes are spawned
        as separate processes.
        Args:
            generate_observation_class: Class to generate observations
            observation_options: Options to pass to the observation class initialize()
            process_action_class: Class to process actions
            action_options: Options to pass to the action class initialize()
        """
        mp_ctx = mp.get_context("spawn")

        self.running = mp_ctx.Event()
        self.running.set()

        # Use the provided classes to create sub-processes
        log_level = LOG.getEffectiveLevel()
        self.obs_process = generate_observation_class(
            mp_ctx, self.running, log_level, options=observation_options
        )
        self.action_process = process_action_class(
            mp_ctx, self.running, log_level, options=action_options
        )

        # spawn start calls run() in process class instance
        self.obs_process.start()
        self.action_process.start()

    def close(self) -> None:
        self.running.clear()
        self.obs_process.join()
        self.action_process.join()
