# Code for communicating with the MCio mod
from dataclasses import dataclass, asdict, field
from typing import Set, List, Tuple
import io
import pprint
import threading
import queue
import time

import numpy as np
import cv2
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

    def get_frame_with_cursor(self) -> Image:
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
    ## Control ##
    version: int = MCIO_PROTOCOL_VERSION
    sequence: int = 0           # sequence number
    key_reset: bool = False     # TODO: clear all presses

    ## Action ##

    # List of (key, action) pairs.
    # E.g., (glfw.KEY_W, glfw.PRESS) or (glfw.KEY_LEFT_SHIFT, glfw.RELEASE)
    # I don't think there's any reason to use glfw.REPEAT
    keys: List[Tuple[int, int]] = field(default_factory=list)

    # List of (button, action) pairs.
    # E.g., (glfw.MOUSE_BUTTON_1, glfw.PRESS) or (glfw.MOUSE_BUTTON_1, glfw.RELEASE)
    mouse_buttons: List[Tuple[int, int]] = field(default_factory=list)   # List of (button, action) pairs

    # List of (x, y) pairs. Using a list for consistency
    mouse_pos: List[Tuple[float, float]] = field(default_factory=list)

    def pack(self) -> bytes:
        pkt_dict = asdict(self)
        #print(pkt_dict)
        return cbor2.dumps(pkt_dict)
    

# Connections to MCio mod
class _Connection:
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

        # XXX zmq has this weird behavior that if you send a packet before it's connected
        # it just drops the packet. Pause here to give it a chance to connect. This only
        # works if minecraft is already running. Need to make a more reliable way of
        # handling this. See https://zguide.zeromq.org/docs/chapter5/ "slow joiner syndrome"
        time.sleep(1)

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

# Threads to handle zmq i/o.
class Controller:
    def __init__(self, host='localhost'):
        # Flag to signal threads to stop.
        self._running = threading.Event()
        self._running.set()

        self._action_queue = queue.Queue()
        self._state_queue = _LatestItemQueue()

        self._mcio_conn = _Connection()

        # Start threads
        self._state_thread = threading.Thread(target=self._state_thread_fn, name="StateThread")
        self._state_thread.daemon = True
        self._state_thread.start()

        self._action_thread = threading.Thread(target=self._action_thread_fn, name="ActionThread")
        self._action_thread.daemon = True
        self._action_thread.start()

    def send_and_recv(self, action: ActionPacket) -> StatePacket:
        # XXX TODO Send action then keep receiving until we receive state after the action
        ...
        self.send_action(action)
        state = self.recv_state()
        return state

    def send_action(self, action: ActionPacket):
        '''
        Send action to minecraft. Doesn't actually send. Places the packet on the queue
        to be sent by the action thread.
        '''
        self._action_queue.put(action)

    def recv_state(self) -> StatePacket:
        '''
        Returns the most recently received state. Blocks if nothing is available.
        '''
        state = self._state_queue.get()
        self._state_queue.task_done()
        return state

    def _action_thread_fn(self):
        ''' Loops. Pulls packets from the action_queue and sends to minecraft. '''
        print("ActionThread start")
        while self._running.is_set():
            action = self._action_queue.get()
            self._action_queue.task_done()
            if action is None:
                break   # Action None to signal exit
            self._mcio_conn.send_action(action)
        print("Action-Thread shut down")

    def _state_thread_fn(self):
        ''' Loops. Receives state packets from minecraft and places on state_queue'''
        print("StateThread start")
        while self._running.is_set():
            state = self._mcio_conn.recv_state()
            if state is None:
                continue    # Exiting or packet decode error
            self._state_queue.put(state)
        print("StateThread shut down")

    def shutdown(self):
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

    def put(self, item):
        try:
            # Discard the current item if the queue isn't empty
            self.get_nowait()
        except queue.Empty:
            pass
        super().put(item)

class Gym:
    ''' Stub in how gymn will work '''
    def __init__(self, name=None, render_mode="human"):
        self.name = name
        self.render_mode = render_mode
        self.ctrl = None
        self._last_action = None
        self._last_state = None
        self._window_width = None
        self._window_height = None

    def reset(self):
        if self.render_mode == 'human':
            cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        self.ctrl = Controller()
        # return observation, info

    def render(self):
        frame = self._last_state.get_frame_with_cursor()
        arr = np.asarray(frame)
        cv2_frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        height, width, _ = cv2_frame.shape
        if height != self._window_height or width != self._window_width:
            # On first frame or if size changed, resize window
            self._window_width = width
            self._window_height = height
            cv2.resizeWindow(self.name, width, height)
        cv2.imshow(self.name, cv2_frame)
        cv2.waitKey(1)
            
    def step(self, action):
        state = self.ctrl.send_and_recv(action)
        self._last_action = action
        self._last_state = state
        self.render()
        # return observation, reward, terminated, truncated, info
        return state