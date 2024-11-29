from typing import Literal, TypedDict

import gymnasium as gym
from gymnasium import spaces
import pygame
import numpy as np
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
ACTIONS = [
    NO_ACTION,
    glfw.PRESS,
    glfw.RELEASE
]


class MCioEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(self, width=640, height=480,
                 mcio_mode: Literal["sync", "async"] = "sync",
                 render_mode=None):
        self.mcio_mode = mcio_mode
        self.window_size = 512  # The size of the PyGame window

        inf32 = np.float32(np.inf)
        self.observation_space = spaces.Dict(
            {
                # shape = (height, width, channels)
                'frame': spaces.Box(
                    low=0,
                    high=255,
                    shape=(height, width, 3),
                    dtype=np.uint8
                ),

                'player_pos': spaces.Box(
                    low=np.array([-inf32, -inf32, -inf32]),
                    high=np.array([inf32, inf32, inf32]),
                    dtype=np.float32
                ),

                'player_pitch': spaces.Box(low=-90.0, high=90.0, shape=(), dtype=np.float32),
                'player_yaw': spaces.Box(low=-180.0, high=180.0, shape=(), dtype=np.float32),
            }
        )

        self.action_space = spaces.Dict({
            'keys': spaces.Dict({
                str(key): spaces.Discrete(len(ACTIONS))
                for key in MINECRAFT_KEYS
            }),

            # Mouse button actions
            'mouse_buttons': spaces.Dict({
                str(button): spaces.Discrete(len(ACTIONS))
                for button in MINECRAFT_MOUSE_BUTTONS
            }),

            # Mouse position - assuming screen coordinates
            'mouse_pos': spaces.Box(
                low=np.array([0, 0]),
                high=np.array([width, height]),
                dtype=np.float32
            )
        })

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        """
        If human-rendering is used, `self.window` will be a reference
        to the window that we draw to. `self.clock` will be a clock that is used
        to ensure that the environment is rendered at the correct framerate in
        human-mode. They will remain `None` until human-mode is used for the
        first time.
        """
        self.window = None
        self.clock = None

    def _packet_to_observation(self, packet:mcio.ObservationPacket) -> dict:
        # Convert all fields to numpy arrays with correct dtypes
        observation = {
            'frame': packet.get_frame_with_cursor(),
            'player_pos': np.array(packet.player_pos, dtype=np.float32),
            'player_pitch': np.array(packet.player_pitch, dtype=np.float32),
            'player_yaw': np.array(packet.player_yaw, dtype=np.float32),
        }
        return observation

    def _action_to_packet(self, action:dict) -> mcio.ActionPacket:
        packet = mcio.ActionPacket()

        # Convert key actions to (key, action) pairs
        keys = []
        for key, val in action['keys'].items():
            if val != NO_ACTION:
                keys.append((int(key), val))
        packet.keys = keys

        # Convert mouse button actions to (button, action) pairs
        buttons = []
        for button, val in action['mouse_buttons'].items():
            if val != NO_ACTION:
                buttons.append((int(button), val))
        packet.buttons = buttons

        # Convert mouse position
        if not np.array_equal(action['mouse_pos'], [0, 0]):  # Only include if moved
            packet.mouse_pos = [(float(action['mouse_pos'][0]), float(action['mouse_pos'][1]))]

        return packet

    def _get_obs(self):
        packet = self.ctrl.recv_observation()
        return self._packet_to_observation(packet)

    def _get_info(self):
        return {}

    def reset(self, seed=None, options=None):
        # We need the following line to seed self.np_random
        super().reset(seed=seed)

        if self.mcio_mode == 'async':
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()
        # Send empty action to trigger an observation
        action = network.ActionPacket()
        self.ctrl.send_action(action)
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, info

    def step(self, action):
        print(action)
        action = network.ActionPacket()
        self.ctrl.send_action(action)

        observation = self._get_obs()
        reward = 0
        terminated = False
        truncated = False
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, reward, terminated, truncated, info

    def render(self):
        if self.render_mode == "rgb_array":
            return self._render_frame()

    def _render_frame(self):
        if self.window is None and self.render_mode == "human":
            pygame.init()
            pygame.display.init()
            self.window = pygame.display.set_mode((self.window_size, self.window_size))
        if self.clock is None and self.render_mode == "human":
            self.clock = pygame.time.Clock()

        canvas = pygame.Surface((self.window_size, self.window_size))
        canvas.fill((255, 255, 255))
        pix_square_size = (
            self.window_size / self.size
        )  # The size of a single grid square in pixels

        # First we draw the target
        pygame.draw.rect(
            canvas,
            (255, 0, 0),
            pygame.Rect(
                pix_square_size * self._target_location,
                (pix_square_size, pix_square_size),
            ),
        )
        # Now we draw the agent
        pygame.draw.circle(
            canvas,
            (0, 0, 255),
            (self._agent_location + 0.5) * pix_square_size,
            pix_square_size / 3,
        )

        # Finally, add some gridlines
        for x in range(self.size + 1):
            pygame.draw.line(
                canvas,
                0,
                (0, pix_square_size * x),
                (self.window_size, pix_square_size * x),
                width=3,
            )
            pygame.draw.line(
                canvas,
                0,
                (pix_square_size * x, 0),
                (pix_square_size * x, self.window_size),
                width=3,
            )

        if self.render_mode == "human":
            # The following line copies our drawings from `canvas` to the visible window
            self.window.blit(canvas, canvas.get_rect())
            pygame.event.pump()
            pygame.display.update()

            # We need to ensure that human-rendering occurs at the predefined framerate.
            # The following line will automatically add a delay to
            # keep the framerate stable.
            self.clock.tick(self.metadata["render_fps"])
        else:  # rgb_array
            return np.transpose(
                np.array(pygame.surfarray.pixels3d(canvas)), axes=(1, 0, 2)
            )

    def close(self):
        if self.window is not None:
            pygame.display.quit()
            pygame.quit()
