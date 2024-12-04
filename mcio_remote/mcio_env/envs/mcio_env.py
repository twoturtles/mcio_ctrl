from typing import Literal, Sequence, Any

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from numpy.typing import NDArray
import glfw

from mcio_remote import controller, network, gui

##
# Defines used in creating spaces

# Define the subset of all keys/buttons that we're using
# Automate the mapping?
MINECRAFT_KEYS = {
    "W": glfw.KEY_W,
    "A": glfw.KEY_A,
    "S": glfw.KEY_S,
    "D": glfw.KEY_D,
    "E": glfw.KEY_E,
    "SPACE": glfw.KEY_SPACE,
    "L_SHIFT": glfw.KEY_LEFT_SHIFT,
}

MINECRAFT_MOUSE_BUTTONS = {
    "LEFT": glfw.MOUSE_BUTTON_LEFT,
    "RIGHT": glfw.MOUSE_BUTTON_RIGHT,
}

# key / button states in action spaces
NO_PRESS = np.int64(0)
PRESS = np.int64(1)

CURSOR_REL_BOUND_DEFAULT = 1000
NO_CURSOR_REL = np.array((0.0, 0.0), dtype=np.float32)

# XXX gymnasium.utils.env_checker.check_env

# XXX env width/height must match minecraft. Automate?


class MCioEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        cursor_rel_bound: int = CURSOR_REL_BOUND_DEFAULT,
        mcio_mode: Literal["sync", "async"] = "sync",
        render_mode: str | None = None,
    ):
        self.width = width
        self.height = height
        self.cursor_rel_bound = cursor_rel_bound
        self.mcio_mode = mcio_mode

        self.last_frame: NDArray[np.uint8] = None
        self.gui = None
        self.last_cursor_pos: tuple[int, int] = (0, 0)
        self.keys_pressed: set[str] = set()
        self.mouse_buttons_pressed: set[str] = set()

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
                # For keys and mouse buttons, 1 = pressed, 0 = not pressed
                "keys": spaces.Dict(
                    {key: spaces.Discrete(2) for key in MINECRAFT_KEYS.keys()}
                ),
                "mouse_buttons": spaces.Dict(
                    {
                        button: spaces.Discrete(2)
                        for button in MINECRAFT_MOUSE_BUTTONS.keys()
                    }
                ),
                # Mouse movement relative to the current position
                # Change to minerl camera setup?
                "cursor_pos_rel": spaces.Box(
                    low=-cursor_rel_bound,
                    high=cursor_rel_bound,
                    shape=(2,),
                ),
            }
        )

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

    # Is there a better way to get a noop? Wrappers?
    # E.g., noop = env.unwrapped.get_noop_action() XXX Don't require unwrapped
    def get_noop_action(self) -> dict[str, Any]:
        action = {}

        action["keys"] = {}
        for name in MINECRAFT_KEYS.keys():
            action["keys"][name] = NO_PRESS

        action["mouse_buttons"] = {}
        for name in MINECRAFT_MOUSE_BUTTONS.keys():
            action["mouse_buttons"][name] = NO_PRESS

        action["cursor_pos_rel"] = NO_CURSOR_REL

        assert action in self.action_space
        return action

    def _get_obs(self):
        packet = self.ctrl.recv_observation()
        return self._packet_to_observation(packet)

    def _send_action(
        self, action: dict | None = None, commands: list[str] | None = None
    ):
        packet = self._action_to_packet(action, commands)
        self.ctrl.send_action(packet)

    def _packet_to_observation(self, packet: network.ObservationPacket) -> dict:
        """Convert an ObservationPacket to the environment observation_space
        XXX Sets self.last_frame and self.last_cursor_pos as side-effects"""
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

    # XXX I think missing keys/buttons should translate to NO_PRESS. But what is noop then?
    # Convert action space values to MCio/Minecraft values. Allow for empty/noop actions.
    def _action_to_packet(
        self, action: dict | None = None, commands: list[str] | None = None
    ) -> network.ActionPacket:
        """Convert from the environment action_space to an ActionPacket"""
        packet = network.ActionPacket()
        if action is None and commands is None:  # noop
            return packet

        action = action or {}
        commands = commands or []
        packet.commands = commands

        # Convert action_space key indices to Minecraft (key, action) pairs
        if "keys" in action:
            packet.keys = self._space_map_to_packet(
                action["keys"], MINECRAFT_KEYS, self.keys_pressed
            )
            packet.keys.sort()

        # Convert action_space mouse button indices to Minecraft (button, action) pairs
        if "mouse_buttons" in action:
            packet.mouse_buttons = self._space_map_to_packet(
                action["mouse_buttons"],
                MINECRAFT_MOUSE_BUTTONS,
                self.mouse_buttons_pressed,
            )
            packet.mouse_buttons.sort()

        # Convert cursor position
        if "cursor_pos_rel" in action:
            rel_arr = action["cursor_pos_rel"]
            if not np.array_equal(rel_arr, NO_CURSOR_REL):
                dx, dy = rel_arr
                cursor_pos = (
                    int(self.last_cursor_pos[0] + int(dx)),
                    int(self.last_cursor_pos[1] + int(dy)),
                )
                packet.cursor_pos = [cursor_pos]

        return packet

    def _space_map_to_packet(
        self,
        space_dict: dict[str, np.int64],
        conv_dict: dict[str, int],
        pressed_set: set[str],
    ) -> list[tuple[int, int]]:
        """Map keys and buttons in the action space to Minecraft press/release
        Also updates self.keys_pressed and self.mouse_buttons_pressed"""
        pairs = []
        for name, action in space_dict.items():
            pressed = bool(action)  # 1 = pressed, 0 = not pressed
            assert name in conv_dict  # in MINECRAFT_KEYS or MINECRAFT_MOUSE_BUTTONS
            glfw_code = conv_dict[name]
            if pressed == (name in pressed_set):
                # No change. Should continued pressing generate REPEAT?
                continue
            if pressed:
                pair = (glfw_code, glfw.PRESS)
                pressed_set.add(name)
            else:
                pair = (glfw_code, glfw.RELEASE)
                pressed_set.remove(name)
            pairs.append(pair)

        return pairs

    def _get_reset_action(self) -> dict[str, Any]:
        action = {}

        action["keys"] = {}
        for name in MINECRAFT_KEYS.keys():
            action["keys"][name] = NO_PRESS

        action["mouse_buttons"] = {}
        for name in MINECRAFT_MOUSE_BUTTONS.keys():
            action["mouse_buttons"][name] = NO_PRESS

        # Move cursor back to (0, 0). Make configurable - face East, etc.?
        action["cursor_pos_rel"] = np.array(
            (-self.last_cursor_pos[0], -self.last_cursor_pos[1]), dtype=np.float32
        )

        assert action in self.action_space
        return action

    def _get_info(self):
        return {}

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None):
        """valid options:
        commands: list of server commands to initialize the environment.
            E.g. teleport, time set, etc. Do not include the initial "/" in the commands.
        """
        # We need the following line to seed self.np_random
        super().reset(seed=seed)
        options = options or {}

        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()

        commands = options.get("commands")
        # Send reset action with initialization commands to trigger an observation
        self._send_action(self._get_reset_action(), commands)
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame_human()

        return observation, info

    def step(self, action: dict):
        if action not in self.action_space:
            raise ValueError(f"Invalid action: {action}")
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
        if self.gui is None and self.render_mode == "human":
            self.gui = gui.ImageStreamGui("MCio", width=self.width, height=self.height)
        if self.last_frame is None:
            return
        self.gui.poll()
        self.gui.show(self.last_frame)

    def close(self):
        if self.gui is not None:
            self.gui.cleanup()


##
# Helper functions


def _nf32(seq: Sequence | int | float) -> NDArray[np.float32]:
    """Convert to np.float32 arrays. Turns single values into 1D arrays."""
    if isinstance(seq, (int, float)):
        seq = [float(seq)]
    seq = [np.float32(val) for val in seq]
    a = np.array(seq, dtype=np.float32)
    return a
