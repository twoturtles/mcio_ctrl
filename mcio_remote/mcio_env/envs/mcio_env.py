from typing import Literal, Sequence, Any

import gymnasium as gym
from gymnasium import spaces
import pygame
import numpy as np
from numpy.typing import NDArray
import glfw

from mcio_remote import controller, network

##
# Helper functions


def _nf32(seq: Sequence | int | float) -> NDArray[np.float32]:
    """Convert to np.float32 arrays. Turns single values into 1D arrays."""
    if isinstance(seq, (int, float)):
        seq = [float(seq)]
    seq = [np.float32(val) for val in seq]
    a = np.array(seq, dtype=np.float32)
    return a


def _nf2dint(val: np.int32) -> NDArray[np.float32]:
    """Create the closest 2D Box bound for the passed in val"""
    return np.array([val, val], dtype=np.float32)


def _space_to_pairs(
    space_dict: dict[str, np.int64], conv_list: list[int]
) -> list[tuple[int, int]]:
    """Convert gym Discrete Dict (keys or buttons) into pairs to send MCio"""
    pairs = []
    for kb_str, action_idx in space_dict.items():
        kb = int(kb_str)
        action = ACTIONS[int(action_idx)]
        if action != NO_ACTION:
            pairs.append((kb, action))
    return pairs


def _key_space_to_pairs(key_space_dict: dict[str, np.int64]) -> list[tuple[int, int]]:
    return _space_to_pairs(key_space_dict, MINECRAFT_KEYS)


def _mb_space_to_pairs(
    mouse_button_space_dict: dict[str, np.int64]
) -> list[tuple[int, int]]:
    return _space_to_pairs(mouse_button_space_dict, MINECRAFT_MOUSE_BUTTONS)


##
# Defines used in creating spaces

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

NO_ACTION = None
ACTIONS = [NO_ACTION, glfw.RELEASE, glfw.PRESS]

CURSOR_REL_BOUND_DEFAULT = 1000
NO_CURSOR_REL = (0, 0)

# XXX gymnasium.utils.env_checker.check_env

# XXX env width/height must match minecraft. Automate?


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
        self.last_cursor_pos = (0, 0)

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
                    low=_nf32([-np.inf, -np.inf, -np.inf]),
                    high=_nf32([np.inf, np.inf, np.inf]),
                ),
                "player_pitch": spaces.Box(low=_nf32(-90), high=_nf32(90)),
                "player_yaw": spaces.Box(low=_nf32(-180), high=_nf32(180)),
            }
        )

        self.action_space = spaces.Dict(
            {
                "keys": spaces.Dict(
                    {str(key): spaces.Discrete(len(ACTIONS)) for key in MINECRAFT_KEYS}
                ),
                "mouse_buttons": spaces.Dict(
                    {
                        str(button): spaces.Discrete(len(ACTIONS))
                        for button in MINECRAFT_MOUSE_BUTTONS
                    }
                ),
                # Mouse movement relative to the current position
                "cursor_pos_rel": spaces.Box(
                    low=_nf2dint(-CURSOR_REL_BOUND_DEFAULT),
                    high=_nf2dint(CURSOR_REL_BOUND_DEFAULT),
                ),
            }
        )

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

    def _get_obs(self):
        packet = self.ctrl.recv_observation()
        return self._packet_to_observation(packet)

    def _send_action(self, action: dict | None = None):
        packet = self._action_to_packet(action)
        self.ctrl.send_action(packet)

    def _packet_to_observation(self, packet: network.ObservationPacket) -> dict:
        """Convert an ObservationPacket to the environment observation_space"""
        # Convert all fields to numpy arrays with correct dtypes
        self.last_frame = packet.get_frame_with_cursor()
        self.last_cursor_pos = packet.player_pos
        observation = {
            "frame": self.last_frame,
            "player_pos": _nf32(packet.player_pos),
            "player_pitch": _nf32(packet.player_pitch),
            "player_yaw": _nf32(packet.player_yaw),
        }
        return observation

    # Convert action space values to MCio/Minecraft values. Allow for empty actions.
    def _action_to_packet(self, action: dict | None = None) -> network.ActionPacket:
        """Convert from the environment action_space to an ActionPacket"""
        packet = network.ActionPacket()
        if action is None:
            return packet

        # Convert action_space key indices to Minecraft (key, action) pairs
        if "keys" in action:
            packet.keys = _key_space_to_pairs(action["keys"])

        # Convert action_space mouse button indices to Minecraft (button, action) pairs
        if "mouse_buttons" in action:
            packet.mouse_buttons = _mb_space_to_pairs(action["mouse_buttons"])

        # Convert cursor position
        if "cursor_pos_rel" in action:
            dx, dy = action["cursor_pos_rel"]
            if (dx, dy) != NO_CURSOR_REL:
                cursor_pos = (
                    self.last_cursor_pos[0] + int(dx),
                    self.last_cursor_pos[1] + int(dy),
                )
                packet.cursor_pos = cursor_pos

        return packet

    def _get_info(self):
        return {}

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None):
        """valid options:
        commands: list of server commands to initialize the environment.
            E.g. teleport, time set, etc. Do not include the initial "/" in the commands.
        """
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()

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
