# Code for communicating with the MCio mod
import io
import logging
import pprint
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Final, Optional

import cbor2
import glfw  # type: ignore
import numpy as np
import zmq
import zmq.utils.monitor as zmon
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from . import types, util

LOG = logging.getLogger(__name__)

MCIO_PROTOCOL_VERSION: Final[int] = 2


@dataclass
class InventorySlot:
    slot: int
    id: str
    count: int


# Observation packets received from MCio
@dataclass
class ObservationPacket:
    ## Control ##
    version: int = MCIO_PROTOCOL_VERSION
    sequence: int = 0
    mode: str = ""  # "SYNC" or "ASYNC"
    last_action_sequence: int = (
        0  # This is the last action sequenced before this observation was generated
    )
    frame_sequence: int = 0  # Frame number since Minecraft started

    ## Observation ##
    frame: bytes = field(repr=False, default=b"")  # Exclude the frame from repr output.
    cursor_mode: int = (
        glfw.CURSOR_NORMAL
    )  # Either glfw.CURSOR_NORMAL (212993) or glfw.CURSOR_DISABLED (212995)
    cursor_pos: tuple[int, int] = field(default=(0, 0))  # x, y
    health: float = 0.0
    # Minecraft uses float player positions. This indicates the position within the block.
    player_pos: tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))
    player_pitch: float = 0
    player_yaw: float = 0
    inventory_main: list[InventorySlot] = field(default_factory=list)
    inventory_armor: list[InventorySlot] = field(default_factory=list)
    inventory_offhand: list[InventorySlot] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional["ObservationPacket"]:
        try:
            decoded_dict = cbor2.loads(data)
        except Exception as e:
            LOG.error(f"CBOR load error: {type(e).__name__}: {e}")
            return None

        try:
            obs = cls(**decoded_dict)
        except Exception as e:
            # This means the received packet doesn't match ObservationPacket.
            # It may not even be a dict.
            LOG.error(f"ObservationPacket decode error: {type(e).__name__}: {e}")
            if isinstance(decoded_dict, dict) and "frame" in decoded_dict:
                decoded_dict["frame"] = f"Frame len: {len(decoded_dict['frame'])}"
            LOG.error("Raw packet follows:")
            LOG.error(pprint.pformat(decoded_dict))
            return None

        if obs.version != MCIO_PROTOCOL_VERSION:
            LOG.error(
                f"MCio Protocol version mismatch: Observation packet = {obs.version}, expected = {MCIO_PROTOCOL_VERSION}"
            )
            return None

        return obs

    def __str__(self) -> str:
        # frame is excluded from repr. Add its size to str. Slow?
        frame = Image.open(io.BytesIO(self.frame))
        return f"{repr(self)} frame.size={frame.size}"

    def get_frame_type(self) -> str | None:
        img = Image.open(io.BytesIO(self.frame))
        return img.format  # "PNG" / "JPEG"

    def get_frame_with_cursor(self) -> NDArray[np.uint8]:
        # Convert frame PNG/JPEG bytes to image
        frame = Image.open(io.BytesIO(self.frame))
        if self.cursor_mode == glfw.CURSOR_NORMAL:
            # Add simulated cursor.
            draw = ImageDraw.Draw(frame)
            x, y = self.cursor_pos[0], self.cursor_pos[1]
            radius = 5
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill="red")
        return np.ascontiguousarray(frame)


# Action packets sent by the agent to MCio
@dataclass
class ActionPacket:
    ## Control ##
    version: int = MCIO_PROTOCOL_VERSION
    sequence: int = (
        0  # sequence number. This will be automatically set by send_action in Controller.
    )
    commands: list[str] = field(
        default_factory=list
    )  # Server commands to execute (teleport, time set, etc.). Do not include the /
    stop: bool = False  # Tell Minecraft to exit

    ## Action ##

    # List of (key, action) pairs.
    # E.g., (glfw.KEY_W, glfw.PRESS) or (glfw.KEY_LEFT_SHIFT, glfw.RELEASE)
    # I don't think there's any reason to use glfw.REPEAT
    keys: list[tuple[int, int]] = field(default_factory=list)

    # List of (button, action) pairs.
    # E.g., (glfw.MOUSE_BUTTON_1, glfw.PRESS) or (glfw.MOUSE_BUTTON_1, glfw.RELEASE)
    mouse_buttons: list[tuple[int, int]] = field(
        default_factory=list
    )  # List of (button, action) pairs

    # List of (x, y) pairs. Using a list for consistency
    cursor_pos: list[tuple[int, int]] = field(default_factory=list)

    def pack(self) -> bytes:
        pkt_dict = asdict(self)
        LOG.debug(pkt_dict)
        return cbor2.dumps(pkt_dict)


class _Connection:
    """Connections to MCio mod. Used by Controller.
    Don't use this directly, use ControllerSync or ControllerAsync."""

    def __init__(
        self,
        *,
        action_port: int | None = None,
        observation_port: int | None = None,
        wait_for_connection: bool = True,  # Block until connection is established
        connection_timeout: (
            float | None
        ) = None,  # Only used when wait_for_connection is True
    ):
        action_port = action_port or types.DEFAULT_ACTION_PORT
        observation_port = observation_port or types.DEFAULT_OBSERVATION_PORT

        LOG.info("Connecting to Minecraft")
        # Initialize ZMQ context
        self.zmq_context = zmq.Context()

        # Socket to send commands
        self.action_socket = self.zmq_context.socket(zmq.PUSH)
        action_monitor = self.action_socket.get_monitor_socket()
        self.action_socket.connect(f"tcp://{types.DEFAULT_HOST}:{action_port}")
        self.action_connected = threading.Event()

        # Socket to receive observation updates
        self.observation_socket = self.zmq_context.socket(zmq.PULL)
        observation_monitor = self.observation_socket.get_monitor_socket()
        self.observation_socket.connect(
            f"tcp://{types.DEFAULT_HOST}:{observation_port}"
        )
        self.observation_connected = threading.Event()

        # Start monitor thread
        self._running = threading.Event()
        self._running.set()
        self.monitor_thread = threading.Thread(
            target=self._monitor_thread_fn,
            args=(action_monitor, observation_monitor),
            name="MonitorThread",
            daemon=True,
        )
        self.monitor_thread.start()

        # Wait for both connections to be established
        if wait_for_connection:
            if not self._wait_for_connections(connection_timeout):
                raise TimeoutError(
                    f"Failed to connect to Minecraft within timeout: {connection_timeout}s"
                )
            LOG.info("Minecraft connections established")

        self.recv_counter = util.TrackPerSecond("RecvObservationPPS")
        self.send_counter = util.TrackPerSecond("SendActionPPS")

    def send_action(self, action: ActionPacket) -> None:
        """
        Send action through zmq socket. Does not block.

        There's a zmq bug that causes send to not block if there
        is room in the queue even if there is no connection.
        In that case the packet is placed on zmq's internal queue.
        https://github.com/zeromq/libzmq/issues/3248
        To avoid confusion, this never blocks.
        """
        self.send_counter.count()
        try:
            self.action_socket.send(action.pack(), zmq.DONTWAIT)
        except zmq.Again as e:
            # Will only happen if ZMQ's queue is full
            LOG.error(f"ZMQ error in send_action: {e.errno}: {e}")

    def recv_observation(self, block: bool = True) -> ObservationPacket | None:
        """
        Receives observation from zmq socket.
        """
        while self._running.is_set():
            try:
                # RECV 1
                pbytes = self.observation_socket.recv(zmq.DONTWAIT)
            except zmq.ContextTerminated:
                # Shutting down
                return None
            except zmq.Again:
                if not block:
                    # Non-blocking, nothing available
                    return None
                # Blocking, need to try again.
                # Doing our own sleep so we can do a clean shutdown on close()
                # XXX Turn into poll
                time.sleep(0.01)
            else:
                # recv returned
                # This may also return None if there was an unpack error.
                observation = ObservationPacket.unpack(pbytes)
                self.recv_counter.count()
                LOG.debug(observation)
                return observation

        # Loop exited
        return None

    def close(self) -> None:
        LOG.info("Closing connections")
        self._running.clear()
        self.action_socket.close()
        self.observation_socket.close()
        self.zmq_context.term()

    def _wait_for_connections(self, connection_timeout: float | None = None) -> bool:
        start = time.time()
        last_log = start
        while self._running.is_set():
            now = time.time()
            if self.action_connected.is_set() and self.observation_connected.is_set():
                return True
            if now - last_log >= 1.0:
                LOG.info(f"Waiting for connections... {int(now-start)}s")
                last_log = now
            if connection_timeout is not None:
                if now - start >= connection_timeout:
                    return False
            self.action_connected.wait(timeout=0.01)
            self.observation_connected.wait(timeout=0.01)
        return False

    def _process_monitor_event(
        self,
        label: str,
        monitor: zmq.SyncSocket,
        conn_flag: threading.Event,
        event_map: dict[int, str],
    ) -> None:
        """Process a single event for _monitor_thread_fn()"""
        # recv_monitor_event() returns dict of
        # {"event":int, "value":int, "endpoint":str}
        # Only care about the event
        # See http://api.zeromq.org/4-2:zmq-socket-monitor
        ev = zmon.recv_monitor_message(monitor, zmq.NOBLOCK)
        event = ev["event"]
        if event == zmq.EVENT_CONNECTED:
            LOG.info(f"{label} socket connected {event_map[event]}")
            conn_flag.set()
        elif conn_flag.is_set() and event in [zmq.EVENT_DISCONNECTED, zmq.EVENT_CLOSED]:
            # XXX Close socket / signal user?
            LOG.info(f"{label} socket disconnected: {event_map[event]}")
            conn_flag.clear()
        else:
            LOG.debug(f"{label} socket event: {event_map[event]}")

    def _monitor_thread_fn(
        self, action_monitor: zmq.SyncSocket, observation_monitor: zmq.SyncSocket
    ) -> None:

        LOG.info("MonitorThread started")
        event_map = get_zmq_event_names()

        poller = zmq.Poller()
        poller.register(action_monitor, zmq.POLLIN)
        poller.register(observation_monitor, zmq.POLLIN)

        while self._running.is_set():
            # returns list of (socket, poll_event_mask)
            # with dict() this is {socket: poll_event_mask}
            # Only care about socket here since the only event
            # we're listening for is POLLIN.
            try:
                poll_events = dict(poller.poll())
            except zmq.ContextTerminated:
                break  # exiting

            if action_monitor in poll_events:
                self._process_monitor_event(
                    "Action", action_monitor, self.action_connected, event_map
                )
            if observation_monitor in poll_events:
                self._process_monitor_event(
                    "Observation",
                    observation_monitor,
                    self.observation_connected,
                    event_map,
                )

        action_monitor.close()
        observation_monitor.close()
        LOG.info("MonitorThread done")


def get_zmq_event_names() -> dict[int, str]:
    """This is ugly, but it's how the zmq examples do it"""
    events: dict[int, str] = {}
    for name in dir(zmq):
        if name.startswith("EVENT_"):
            value = getattr(zmq, name)
            events[value] = name
    return events
