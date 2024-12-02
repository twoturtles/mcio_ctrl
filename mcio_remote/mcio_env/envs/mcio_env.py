from typing import Literal, Sequence, Any

import gymnasium as gym
from gymnasium import spaces
import pygame
import numpy as np
from numpy.typing import NDArray
import glfw

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

NO_MOUSE_POS = np.array(
    [np.iinfo(np.int32).min, np.iinfo(np.int32).min], dtype=np.int32
)

# XXX gymnasium.utils.env_checker.check_env

class MCioEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        mcio_mode: Literal["sync", "async"] = "sync",
        render_mode: str | None = None,
    ):
        self.mcio_mode = mcio_mode
        self.width = width
        self.height = height
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
                    low=np.array(
                        [np.iinfo(np.int32).min, np.iinfo(np.int32).min], dtype=np.int32
                    ),
                    high=np.array(
                        [np.iinfo(np.int32).max, np.iinfo(np.int32).max], dtype=np.int32
                    ),
                ),
            }
        )

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

    def _get_obs(self):
        packet = self.ctrl.recv_observation()
        return self._packet_to_observation(packet)

    def _packet_to_observation(self, packet: network.ObservationPacket) -> dict:
        # Convert all fields to numpy arrays with correct dtypes
        self.last_frame = packet.get_frame_with_cursor()
        observation = {
            "frame": self.last_frame,
            "player_pos": nf32(packet.player_pos),
            "player_pitch": nf32(packet.player_pitch),
            "player_yaw": nf32(packet.player_yaw),
        }
        return observation

    def _send_action(self, action: dict | None = None):
        packet = self._action_to_packet(action)
        self.ctrl.send_action(packet)

    # Convert action space values to MCio/Minecraft values. Allow for empty actions.
    def _action_to_packet(self, action: dict | None = None) -> network.ActionPacket:
        packet = network.ActionPacket()
        if action is None:
            return packet

        # Convert action space keys to Minecraft (key, action) pairs
        if "keys" in action:
            keys = []
            for key, val in action["keys"].items():
                if val != NO_ACTION:
                    keys.append((int(key), val))
            packet.keys = keys

        # Convert action space mouse buttons to Minecraft (button, action) pairs
        if "mouse_buttons" in action:
            buttons = []
            for button, val in action["mouse_buttons"].items():
                if val != NO_ACTION:
                    buttons.append((int(button), val))
            packet.buttons = buttons

        # Convert mouse position
        if "mouse_pos" in action and not np.array_equal(
            action["mouse_pos"], NO_MOUSE_POS
        ):
            packet.mouse_pos = [tuple(action["mouse_pos"])]

        return packet

    def _get_info(self):
        return {}

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None):
        ''' valid options:
                commands: list of commands (Do not include the /)
        '''
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()
        # print(self.action_space.sample())
        # Send empty action to trigger an observation
        self._send_action()
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame_human()

        return observation, info

    def step(self, action: dict):
        self._send_action(action)

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
