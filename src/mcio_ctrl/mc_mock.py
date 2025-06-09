"""Used for testing. Simulate MCio running on Minecraft."""

import enum
import logging
import multiprocessing as mp
import os
from typing import Any

import zmq

from . import network, types, util

LOG = logging.getLogger(__name__)


class _SocketProcessor(mp.Process):
    """
    Base class for fake Minecraft processes handling ZMQ communication.
    Don't use this directly. Subclass from GenerateObservation or ProcessAction instead.
    """

    class ProcessType(enum.Enum):
        OBSERVATION = enum.auto()
        ACTION = enum.auto()

    # Assigned in module subclasses
    _process_type: ProcessType

    def __init__(
        self,
        mp_ctx: mp.context.BaseContext,
        log_level: int,
        initialize_options: dict[Any, Any] | None = None,
    ) -> None:
        super().__init__()
        self.mp_ctx = mp_ctx
        self.log_level = log_level

        self.initialize(initialize_options)

    def run(self) -> None:
        util.logging_init(level=self.log_level)
        name = mp.current_process().name
        LOG.info(f"Starting-Subprocess name={name} pid={os.getpid()}")

        match self._process_type:
            case self.ProcessType.OBSERVATION:
                socket_type = zmq.PUSH
                port = types.DEFAULT_OBSERVATION_PORT
            case self.ProcessType.ACTION:
                socket_type = zmq.PULL
                port = types.DEFAULT_ACTION_PORT
            case _:
                raise ValueError(f"Invalid process type: {self._process_type}")

        context = zmq.Context()
        socket = context.socket(socket_type)
        socket.bind(f"tcp://{types.DEFAULT_HOST}:{port}")

        try:
            while True:
                try:
                    self._process(socket)
                except Exception as e:
                    LOG.error(f"Error in process loop: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            LOG.info(f"Stopping-Subprocess name={name} pid={os.getppid()}")
            socket.close()
            context.term()

    def _process(self, socket: zmq.SyncSocket) -> None:
        match self._process_type:
            case self.ProcessType.OBSERVATION:
                obs = self.generate_observation()
                socket.send(obs.pack())
            case self.ProcessType.ACTION:
                pbytes = socket.recv()
                act = network.ActionPacket.unpack(pbytes)
                self.process_action(act)

    def initialize(self, options: dict[Any, Any] | None) -> None:
        raise NotImplementedError()

    def generate_observation(self) -> network.ObservationPacket:
        raise NotImplementedError()

    def process_action(self, action: network.ActionPacket) -> None:
        raise NotImplementedError()


class GenerateObservation(_SocketProcessor):
    _process_type = _SocketProcessor.ProcessType.OBSERVATION

    def initialize(self, options: dict[Any, Any] | None) -> None:
        """Override for custom initialization"""
        pass

    def generate_observation(self) -> network.ObservationPacket:
        """Override for custom observation generation"""
        return network.ObservationPacket()


class ProcessAction(_SocketProcessor):
    _process_type = _SocketProcessor.ProcessType.ACTION

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

        # Use the provided classes to create sub-processes
        log_level = LOG.getEffectiveLevel()
        self.obs_process = generate_observation_class(
            mp_ctx, log_level, initialize_options=observation_options
        )
        self.action_process = process_action_class(
            mp_ctx, log_level, initialize_options=action_options
        )

        # spawn start calls run() in process class instance
        LOG.info(f"Starting-Mock-Minecraft parent-pid={os.getpid()}")
        self.obs_process.start()
        self.action_process.start()

    def close(self) -> None:
        LOG.info("Stopping-Mock-Minecraft")
        self.obs_process.terminate()
        self.obs_process.join()
        self.action_process.terminate()
        self.action_process.join()
