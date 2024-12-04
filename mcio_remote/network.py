# Code for communicating with the MCio mod
from dataclasses import dataclass, asdict, field
from typing import Optional
import io
import pprint
import time

import cbor2
import glfw
import zmq
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from . import util
from . import logger

LOG = logger.LOG.get_logger(__name__)


DEFAULT_HOST = "localhost"
DEFAULT_ACTION_PORT = 4001  # 4ction
DEFAULT_OBSERVATION_PORT = 8001  # 8bservation
DEFAULT_ACTION_ADDR = f"tcp://{DEFAULT_HOST}:{DEFAULT_ACTION_PORT}"
DEFAULT_OBSERVATION_ADDR = f"tcp://{DEFAULT_HOST}:{DEFAULT_OBSERVATION_PORT}"

MCIO_PROTOCOL_VERSION = 0


# Observation packets received from MCio
@dataclass
class ObservationPacket:
    ## Control ##
    version: int = MCIO_PROTOCOL_VERSION
    mode: str = ""  # "SYNC" or "ASYNC"
    sequence: int = 0
    last_action_sequence: int = (
        0  # This is the last action sequenced before this observation was generated
    )
    frame_sequence: int = 0  # Frame number since Minecraft started

    ## Observation ##
    frame_png: bytes = field(
        repr=False, default=b""
    )  # Exclude the frame from repr output.
    health: float = 0.0
    cursor_mode: int = (
        glfw.CURSOR_NORMAL
    )  # Either glfw.CURSOR_NORMAL (212993) or glfw.CURSOR_DISABLED (212995)
    cursor_pos: tuple[int, int] = field(default=(0, 0))  # x, y
    # Minecraft uses float player positions. This indicates the position within the block.
    player_pos: tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))
    player_pitch: float = 0
    player_yaw: float = 0
    inventory_main: list = field(default_factory=list)
    inventory_armor: list = field(default_factory=list)
    inventory_offhand: list = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional["ObservationPacket"]:
        try:
            decoded_dict = cbor2.loads(data)
        except Exception as e:
            LOG.error(f"CBOR load error: {type(e).__name__}: {e}")
            return None

        try:
            rv = cls(**decoded_dict)
        except Exception as e:
            # This means the received packet doesn't match ObservationPacket
            LOG.error(f"ObservationPacket decode error: {type(e).__name__}: {e}")
            if "frame_png" in decoded_dict:
                decoded_dict["frame_png"] = (
                    f"Frame len: {len(decoded_dict['frame_png'])}"
                )
            LOG.error("Raw packet:")
            LOG.error(pprint.pformat(decoded_dict))
            return None

        return rv

    def __str__(self) -> str:
        # frame_png is excluded from repr. Add its size to str. Slow?
        frame = Image.open(io.BytesIO(self.frame_png))
        return f"{repr(self)} frame.size={frame.size}"

    def get_frame_with_cursor(self) -> NDArray[np.uint8]:
        # Convert PNG bytes to image
        frame = Image.open(io.BytesIO(self.frame_png))
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


# Connections to MCio mod. Used by Controller.
class _Connection:
    def __init__(
        self,
        action_addr: str = DEFAULT_ACTION_ADDR,
        observation_addr: str = DEFAULT_OBSERVATION_ADDR,
    ):
        # Initialize ZMQ context
        self.zmq_context = zmq.Context()

        # Socket to send commands
        self.action_socket = self.zmq_context.socket(zmq.PUB)
        self.action_socket.bind(action_addr)

        # Socket to receive observation updates
        self.observation_socket = self.zmq_context.socket(zmq.SUB)
        self.observation_socket.connect(observation_addr)
        self.observation_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.recv_counter = util.TrackPerSecond("RecvObservationPPS")
        self.send_counter = util.TrackPerSecond("SendActionPPS")

        # XXX zmq has this weird behavior that if you send a packet before it's connected
        # it just drops the packet. Pause here to give it a chance to connect. This only
        # works if minecraft is already running. Need to make a more reliable way of
        # handling this. See https://zguide.zeromq.org/docs/chapter5/ "slow joiner syndrome"
        time.sleep(0.5)

    def send_action(self, action: ActionPacket) -> None:
        """
        Send action through zmq socket. Should not block. (Unless zmq buffer is full?)
        """
        self.send_counter.count()
        self.action_socket.send(action.pack())

    def recv_observation(self) -> ObservationPacket | None:
        """
        Receives observation from zmq socket. Blocks until a observation packet is returned
        """
        try:
            # RECV 1
            pbytes = self.observation_socket.recv()
        except zmq.error.ContextTerminated:
            return None

        # This may also return None if there was an unpack error.
        # XXX Maybe these errors should be separated. A context error can happen during shutdown.
        # We could continue after a parse error.
        observation = ObservationPacket.unpack(pbytes)
        self.recv_counter.count()
        LOG.debug(observation)
        return observation

    def close(self) -> None:
        self.action_socket.close()
        self.observation_socket.close()
        self.zmq_context.term()
