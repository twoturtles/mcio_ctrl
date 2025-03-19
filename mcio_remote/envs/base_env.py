"""Base class for MCio environments"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypedDict, TypeVar

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from mcio_remote import controller, gui, instance, network
from mcio_remote.types import RunOptions

# Reusable types
RenderFrame = TypeVar("RenderFrame")  # NDArray[np] shape = (height, width, channels)
ObsType = TypeVar("ObsType", bound=Dict[str, Any])
ActType = TypeVar("ActType", bound=Dict[str, Any])


class ResetOptions(TypedDict, total=False):
    """For now just commands"""

    commands: list[str]  # List of Minecraft commands


class McioBaseEnv(gym.Env[ObsType, ActType], Generic[ObsType, ActType], ABC):
    """Base class for MCio environments"""

    metadata = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 60,
    }

    def __init__(
        self,
        run_options: RunOptions,
        *,
        launch: bool = False,
        render_mode: str | None = None,
    ):
        """Base constructor for MCio environments
        Sub-classes should call this and set up their action_space and observation_space.

        Args:
            run_options: Configuration options for MCio
            launch: Whether to launch a new Minecraft instance
            render_mode: The rendering mode (human, rgb_array)
        """
        self.run_options = run_options
        self.launch = launch
        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        # Common state tracking
        self.last_frame: NDArray[np.uint8] | None = None
        self.last_cursor_pos: tuple[int, int] = (0, 0)
        self.keys_pressed: set[str] = set()
        self.mouse_buttons_pressed: set[str] = set()

        # These need closing when done. Handled in close().
        self.gui: gui.ImageStreamGui | None = None
        self.ctrl: controller.ControllerCommon | None = None
        self.launcher: instance.Launcher | None = None

        # Define spaces in subclasses
        self.action_space: gym.spaces.Space[ActType]
        self.observation_space: gym.spaces.Space[ObsType]

    @abstractmethod
    def _packet_to_observation(self, packet: network.ObservationPacket) -> ObsType:
        pass

    @abstractmethod
    def _action_to_packet(
        self, action: ActType | None = None, commands: list[str] | None = None
    ) -> network.ActionPacket:
        pass

    def _get_obs(self) -> ObsType:
        assert self.ctrl is not None
        packet = self.ctrl.recv_observation()
        if packet is None:
            return {}
        return self._packet_to_observation(packet)

    def _send_action(
        self, action: ActType | None = None, commands: list[str] | None = None
    ) -> None:
        packet = self._action_to_packet(action, commands)
        assert self.ctrl is not None
        self.ctrl.send_action(packet)

    def _send_reset_action(self, options: ResetOptions) -> None:
        """Clear inputs and send initialization commands"""
        packet = network.ActionPacket(
            clear_input=True, commands=options.get("commands", [])
        )
        assert self.ctrl is not None
        self.ctrl.send_action(packet)

    def _get_info(self) -> dict[Any, Any]:
        return {}

    def reset(
        self,
        seed: int | None = None,
        *,
        options: ResetOptions | None = None,  # type: ignore[override]
    ) -> tuple[ObsType, dict[Any, Any]]:
        """valid options:
        commands: list[str] | None = None
            List of server commands to initialize the environment.
            E.g. teleport, time set, etc. Do not include the initial "/" in the commands.
        launcher_options: instance:LauncherOptions | None = None
            Minecraft launch options. Will skip launch if None.
        """
        # We need the following line to seed self.np_random
        super().reset(seed=seed)
        options = options or ResetOptions()

        if self.launch:
            # For multiple resets, close the previous connections, etc.
            if self.launcher is not None:
                self.close()
            self.launcher = instance.Launcher(self.run_options)
            self.launcher.launch(wait=False)

        if self.run_options.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()

        # The reset action will trigger any initial observation
        self._send_reset_action(options)
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame_human()

        return observation, info

    # NDArray[np.uint8] shape = (height, width, channels)
    # Gym's render returns a generic TypeVar("RenderFrame"), which is not very useful.
    def render(self) -> NDArray[np.uint8] | None:  # type: ignore[override]
        if self.render_mode == "human":
            self._render_frame_human()
        elif self.render_mode == "rgb_array":
            return self._render_frame_rgb_array()
        return None

    def _render_frame_rgb_array(self) -> NDArray[np.uint8] | None:
        return self.last_frame

    def _render_frame_human(self) -> None:
        if self.gui is None and self.render_mode == "human":
            self.gui = gui.ImageStreamGui(
                "MCio", width=self.run_options.width, height=self.run_options.height
            )
        if self.last_frame is None:
            return
        assert self.gui is not None
        self.gui.show(self.last_frame)

    def close(self) -> None:
        if self.gui is not None:
            self.gui.close()
            self.gui = None
        if self.ctrl is not None:
            if self.launcher is not None:
                # If we launched Minecraft, try for a clean exit.
                self.ctrl.send_stop()
            self.ctrl.close()
            self.ctrl = None
        if self.launcher is not None:
            self.launcher.close()
            self.launcher = None
