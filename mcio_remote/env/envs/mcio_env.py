from typing import Literal, Sequence

import gymnasium as gym
from gymnasium import spaces
import pygame
import numpy as np
from numpy.typing import NDArray
import glfw

import mcio_remote as mcio
from mcio_remote import controller, network

# Define the subset of all keys/buttons that we're using
MINECRAFT_KEYS = [
    glfw.KEY_W,
    glfw.KEY_A,
    glfw.KEY_S,
    glfw.KEY_D,
    glfw.KEY_SPACE,
    glfw.KEY_LEFT_SHIFT,
]

MINECRAFT_MOUSE_BUTTONS = [
    glfw.MOUSE_BUTTON_LEFT,
    glfw.MOUSE_BUTTON_RIGHT,
]

NO_ACTION = -1
ACTIONS = [NO_ACTION, glfw.PRESS, glfw.RELEASE]


class MCioEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(
        self,
        width=640,
        height=480,
        mcio_mode: Literal["sync", "async"] = "sync",
        render_mode=None,
    ):
        self.mcio_mode = mcio_mode
        self.width = width
        self.height = height
        self.last_most_pos = (None, None)
        self.last_frame = None
        self.window = None

        self.observation_space = spaces.Dict(
            {
                "frame": spaces.Box(
                    low=0,
                    high=255,
                    # shape = (height, width, channels)
                    shape=(height, width, 3),
                    dtype=np.uint8,
                ),
                "player_pos": spaces.Box(
                    low=nf32([-np.inf, -np.inf, -np.inf]),
                    high=nf32([np.inf, np.inf, np.inf]),
                ),
                "player_pitch": spaces.Box(low=nf32(-90), high=nf32(90)),
                "player_yaw": spaces.Box(low=nf32(-180), high=nf32(180)),
            }
        )

        self.action_space = spaces.Dict(
            {
                "keys": spaces.Dict(
                    {str(key): spaces.Discrete(len(ACTIONS)) for key in MINECRAFT_KEYS}
                ),
                # Mouse button actions
                "mouse_buttons": spaces.Dict(
                    {
                        str(button): spaces.Discrete(len(ACTIONS))
                        for button in MINECRAFT_MOUSE_BUTTONS
                    }
                ),
                "mouse_pos": spaces.Box(
                    low=nf32([-np.inf, -np.inf]), high=nf32([np.inf, np.inf])
                ),
            }
        )

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

    def _get_obs(self):
        packet = self.ctrl.recv_observation()
        return self._packet_to_observation(packet)

    def _packet_to_observation(self, packet: mcio.ObservationPacket) -> dict:
        # Convert all fields to numpy arrays with correct dtypes
        self.last_frame = packet.get_frame_with_cursor()
        observation = {
            "frame": self.last_frame,
            "player_pos": nf32(packet.player_pos),
            "player_pitch": nf32(packet.player_pitch),
            "player_yaw": nf32(packet.player_yaw),
        }
        return observation

    def _send_action(self, action: dict):
        packet = self._action_to_packet(action)
        self.ctrl.send_action(packet)

    def _action_to_packet(self, action: dict) -> mcio.ActionPacket:
        packet = mcio.ActionPacket()

        # Convert key actions to (key, action) pairs
        keys = []
        for key, val in action["keys"].items():
            if val != NO_ACTION:
                keys.append((int(key), val))
        packet.keys = keys

        # Convert mouse button actions to (button, action) pairs
        buttons = []
        for button, val in action["mouse_buttons"].items():
            if val != NO_ACTION:
                buttons.append((int(button), val))
        packet.buttons = buttons

        # Convert mouse position
        print(action["mouse_pos"])
        # XXX
        if not np.array_equal(action["mouse_pos"], [0, 0]):  # Only include if moved
            packet.mouse_pos = [
                (float(action["mouse_pos"][0]), float(action["mouse_pos"][1]))
            ]

        return packet

    def _get_info(self):
        return {}

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()
        # print(self.action_space.sample())
        # Send empty action to trigger an observation
        self._send_action({"keys": {}, "mouse_buttons": {}, "mouse_pos": nf32([0, 0])})
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame_human()

        return observation, info

    def step(self, action):
        action = network.ActionPacket()
        self.ctrl.send_action(action)

        observation = self._get_obs()
        reward = 0
        terminated = False
        truncated = False
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame_human()

        return observation, reward, terminated, truncated, info

    def render(self):
        if self.render_mode == "human":
            self._render_frame_human()
        elif self.render_mode == "rgb_array":
            return self._render_frame_rgb_array()

    def _render_frame_rgb_array(): ...

    def _render_frame_human(self):
        if self.window is None and self.render_mode == "human":
            pygame.init()
            pygame.display.init()
            self.window = pygame.display.set_mode((self.width, self.height))

        if self.last_frame is None:
            return

        # numpy shape is (height, width, channels),
        # pygame wants (width, height, channels)
        frame = np.transpose(self.last_frame, (1, 0, 2))
        surface = pygame.surfarray.make_surface(frame)

        # Draw the surface to the window
        self.window.blit(surface, (0, 0))

        # Update the display
        pygame.event.pump()
        pygame.display.flip()

    def close(self):
        if self.window is not None:
            pygame.display.quit()
            pygame.quit()


def nf32(seq: Sequence | int | float) -> NDArray[np.float32]:
    """Convert to np.float32 arrays. Turns single values into 1D arrays."""
    if isinstance(seq, (int, float)):
        seq = [float(seq)]
    seq = [np.float32(val) for val in seq]
    a = np.array(seq, dtype=np.float32)
    return a
