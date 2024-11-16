# Code for communicating with the MCio mod
from dataclasses import dataclass, asdict, field
from typing import Set, List, Tuple
import io
import pprint

import cbor2
import glfw
import zmq
from PIL import Image, ImageDraw

DEFAULT_HOST = "localhost"
DEFAULT_ACTION_PORT = 5556
DEFAULT_STATE_PORT = 5557
DEFAULT_ACTION_ADDR = f"tcp://{DEFAULT_HOST}:{DEFAULT_ACTION_PORT}"
DEFAULT_STATE_ADDR = f"tcp://{DEFAULT_HOST}:{DEFAULT_STATE_PORT}"

MCIO_PROTOCOL_VERSION = 0

# State packets received from MCio
@dataclass
class StatePacket:
    version: int = MCIO_PROTOCOL_VERSION
    sequence: int = 0
    frame_png: bytes = field(repr=False, default=b"")   # Exclude the frame from repr output.
    health: float = 0.0
    cursor_mode: int = glfw.CURSOR_NORMAL,  # Either glfw.CURSOR_NORMAL (212993) or glfw.CURSOR_DISABLED (212995)
    cursor_pos: Tuple[int, int] = field(default=(0, 0))     # x, y
    player_pos: Tuple[float, float, float] = field(default=(0., 0., 0.))
    player_pitch: float = 0
    player_yaw: float = 0
    inventory_main: List = field(default_factory=list)
    inventory_armor: List = field(default_factory=list)
    inventory_offhand: List = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> 'StatePacket':
        try:
            decoded_dict = cbor2.loads(data)
        except Exception as e:
            print(f"CBOR load error: {type(e).__name__}: {e}")
            return None

        try:
            rv = cls(**decoded_dict)
        except Exception as e:
            # This means the received packet doesn't match StatePacket
            print(f"StatePacket decode error: {type(e).__name__}: {e}")
            if 'frame_png' in decoded_dict:
                decoded_dict['frame_png'] = f"Frame len: {len(decoded_dict['frame_png'])}"
            print("Raw packet:")
            pprint.pprint(decoded_dict)
            return None

        return rv

    def __str__(self):
        # frame_png is excluded from repr. Add its size to str. Slow?
        frame = Image.open(io.BytesIO(self.frame_png))
        return f"{repr(self)} frame.size={frame.size}"

    def getFrameWithCursor(self):
        # Convert PNG bytes to image
        frame = Image.open(io.BytesIO(self.frame_png))
        if self.cursor_mode == glfw.CURSOR_NORMAL:
            # Add simulated cursor.
            draw = ImageDraw.Draw(frame)
            x, y = self.cursor_pos[0], self.cursor_pos[1]
            radius = 5
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill='red')
        return frame



# Action packets sent by the agent to MCio
@dataclass
class ActionPacket:
    # Control
    version: int = MCIO_PROTOCOL_VERSION
    sequence: int = 0           # sequence number
    key_reset: bool = False     # TODO: clear all presses

    # Action

    # List of (key, action) pairs.
    # E.g., (glfw.KEY_W, glfw.PRESS) or (glfw.KEY_LEFT_SHIFT, glfw.RELEASE)
    # I don't think there's any reason to use glfw.REPEAT
    keys: List[Tuple[int, int]] = field(default_factory=list)

    # List of (button, action) pairs.
    # E.g., (glfw.MOUSE_BUTTON_1, glfw.PRESS) or (glfw.MOUSE_BUTTON_1, glfw.RELEASE)
    mouse_buttons: List[Tuple[int, int]] = field(default_factory=list)   # List of (button, action) pairs

    # List of (x, y) pairs. Using a list for consistency
    mouse_pos: List[Tuple[int, int]] = field(default_factory=list)

    def pack(self) -> bytes:
        pkt_dict = asdict(self)
        print(pkt_dict)
        return cbor2.dumps(pkt_dict)
    

# Connections to MCio mod
class Connection:
    def __init__(self, action_addr=DEFAULT_ACTION_ADDR, state_addr=DEFAULT_STATE_ADDR):
        # Initialize ZMQ context
        self.zmq_context = zmq.Context()

        # Socket to send commands
        self.action_socket = self.zmq_context.socket(zmq.PUB)
        self.action_socket.bind(action_addr)
        
        # Socket to receive state updates
        self.state_socket = self.zmq_context.socket(zmq.SUB)
        self.state_socket.connect(state_addr)
        self.state_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def send_action(self, action:ActionPacket):
        self.action_socket.send(action.pack())

    def recv_state(self) -> StatePacket | None:
        try:
            pbytes = self.state_socket.recv()
        except zmq.error.ContextTerminated:
            return None
        
        # This may also return None if there was an unpack error.
        # XXX Maybe these errors should be separated. A context error can happen during shutdown.
        # We could continue after a parse error.
        return StatePacket.unpack(pbytes)

    # TODO add a simplified interface that encapsulates threads

    def close(self):
        self.action_socket.close()
        self.state_socket.close()
        self.zmq_context.term()

