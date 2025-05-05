"""Base class for MCio environments"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypedDict, TypeVar

import glfw  # type: ignore
import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from mcio_ctrl import controller, gui, instance, network, types

LOG = logging.getLogger(__name__)

# Reusable types
RenderFrame = TypeVar("RenderFrame")  # NDArray[np] shape = (height, width, channels)
ObsType = TypeVar("ObsType", bound=dict[str, Any])
ActType = TypeVar("ActType", bound=dict[str, Any])


class ResetOptions(TypedDict, total=False):
    """For now just commands
    valid options:
    commands: list[str]
        List of server commands to initialize the environment.
        E.g. teleport, time set, etc. Do not include the initial "/" in the commands.

        Note: Different command types seem to take different amounts of time to
        execute in Minecraft. You may want to use skip_steps() after commands to
        make sure they have taken effect. I've seen ~20 ticks before a "time
        set" command takes effect.
    """

    commands: list[str]


class MCioBaseEnv(gym.Env[ObsType, ActType], Generic[ObsType, ActType], ABC):
    """Base class for MCio environments

    Notes for subclasses:
        - Make sure you call super().__init__().
        - Set self.action_space and self.observation_space in the constructor.
        - Define _packet_to_observation(), _action_to_packet() and _process_step()
        - Optionally define _get_info()

    Some common state is also tracked and available for subclasses:
        - self.last_frame
        - self.last_cursor_pos
        - self.health
        - self.terminated
    """

    metadata = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 60,
    }

    def __init__(
        self, run_options: types.RunOptions, render_mode: str | None = None
    ) -> None:
        """Base constructor for MCio environments
        Args:
            run_options: Configuration options for MCio. If instance_name is set, a Minecraft
                instance will be started, otherwise the environment will connect to a previously launched instance.
                See mcio_ctrl.types.RunOptions
            render_mode: The rendering mode (human, rgb_array)

        """
        self.run_options = run_options
        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        # Common state tracking. Initialized in _reset_state(). Updated in _get_obs().
        self.last_frame: NDArray[np.uint8] | None
        self.last_cursor_pos: tuple[int, int]
        self.health: float
        self.terminated: bool
        self._reset_state()

        # These need closing when done. Handled in close().
        self.gui: gui.ImageStreamGui | None = None
        self.ctrl: controller.ControllerCommon | None = None
        self.launcher: instance.Launcher | None = None

        # Define spaces in subclasses
        self.action_space: gym.spaces.Space[ActType]
        self.observation_space: gym.spaces.Space[ObsType]

    ##
    # Define in subclasses

    @abstractmethod
    def _packet_to_observation(self, packet: network.ObservationPacket) -> ObsType:
        """Convert an ObservationPacket to the environment observation_space"""
        pass

    @abstractmethod
    def _action_to_packet(
        self, action: ActType, commands: list[str] | None = None
    ) -> network.ActionPacket:
        """Convert from the environment action_space to an ActionPacket"""
        pass

    @abstractmethod
    def _process_step(
        self, action: ActType, observation: ObsType
    ) -> tuple[int, bool, bool]:
        """Called during step() after the observation has been received.
        Returns (reward, terminated, truncated)
        Note: the base env will automatically set self.terminated if health reaches 0
        """
        pass

    def _get_info(self) -> dict[Any, Any]:
        """Optionally override this in subclasses. Used to return extra info from reset() and step()"""
        return {}

    ##
    # Internal methods

    def _get_obs(self) -> ObsType:
        """Receive an observation and pass it to the subclass.
        Updates self.last_frame self.last_cursor_pos"""
        assert self.ctrl is not None
        packet = self.ctrl.recv_observation()

        # Update common state
        self.last_frame = packet.get_frame_with_cursor()
        self.last_cursor_pos = packet.cursor_pos
        self.health = packet.health
        # For now, terminated just tracks health. It's left to users to call
        # reset when termination occurs
        if self.health == 0.0:
            self.terminated = True
        else:
            self.terminated = False

        # Call to subclass
        obs = self._packet_to_observation(packet)
        # assert obs in self.observation_space
        return obs

    def _send_action(self, action: ActType, commands: list[str] | None = None) -> None:
        # Call to subclass
        packet = self._action_to_packet(action, commands)
        # assert action in self.action_space
        assert self.ctrl is not None
        self.ctrl.send_action(packet)

    def _send_reset_action(self, options: ResetOptions) -> None:
        """Clear inputs and send initialization commands"""
        packet = network.ActionPacket(
            clear_input=True, commands=options.get("commands", [])
        )
        assert self.ctrl is not None
        self.ctrl.send_action(packet)

    def _reset_state(self) -> None:
        """Reset common state"""
        self.last_frame = None
        self.last_cursor_pos = (0, 0)
        self.health = 20.0
        self.terminated = False

    def reset(
        self,
        seed: int | None = None,
        *,
        options: ResetOptions | None = None,  # type: ignore[override]
    ) -> tuple[ObsType, dict[Any, Any]]:
        # We need the following line to seed self.np_random
        super().reset(seed=seed)
        options = options or ResetOptions()

        # For multiple resets, close any previous connections, etc.
        self.close()
        self._reset_state()

        if self.run_options.instance_name is not None:
            self.launcher = instance.Launcher(self.run_options)
            self.launcher.launch(wait=False)

        if self.run_options.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()

        # The reset action will trigger an initial observation
        self._send_reset_action(options)
        observation = self._get_obs()

        assert self.last_frame is not None
        wh_mc = self.last_frame.shape[0:2]
        wh_env = (self.run_options.height, self.run_options.width)
        if wh_mc != wh_env:
            LOG.warning(f"Frame-Size-Mismatch env={wh_env} mcio={wh_mc}")

        if self.terminated:
            observation = self._reset_terminated_hack()

        info = self._get_info()

        return observation, info

    def _reset_terminated_hack(self, max_steps: int = 10) -> ObsType:
        """With doImmediateRespawn set it still takes a few steps to respawn.
        This works around that by skipping steps until we go back to
        non-terminated.
        """
        assert max_steps > 0
        for _ in range(max_steps):
            if not self.terminated:
                break
            observation, *_ = self.skip_steps(1)
        else:
            raise RuntimeError(
                f"Environment remained terminated after {max_steps} steps."
            )

        return observation

    def step(
        self,
        action: ActType,
        *,
        options: ResetOptions | None = None,
    ) -> tuple[ObsType, int, bool, bool, dict[Any, Any]]:
        """Env step function. Includes extra options arg to allow command to be sent during step."""
        options = options or ResetOptions()

        self._send_action(action, options.get("commands"))
        observation = self._get_obs()
        reward, self.terminated, truncated = self._process_step(action, observation)
        info = self._get_info()

        return observation, reward, self.terminated, truncated, info

    def skip_steps(
        self, n_steps: int
    ) -> tuple[ObsType, int, bool, bool, dict[Any, Any]]:
        """Send empty actions and return the final observation. Use to skip over
        a number of steps/game ticks"""
        assert self.ctrl is not None
        pkt = network.ActionPacket()
        for i in range(n_steps):
            self.ctrl.send_action(pkt)
            observation = self._get_obs()
        # observation, reward, terminated, truncated, info
        return observation, 0, self.terminated, False, {}

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
        """This supports multiple closes / resets"""
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

    ##
    # Debug helpers

    def step_raw(self, pkt: network.ActionPacket) -> network.ObservationPacket:
        """Expose sending raw actions"""
        assert self.ctrl is not None
        self.ctrl.send_action(pkt)
        return self.ctrl.recv_observation()

    def toggle_f3(self) -> None:
        """Toggle the debug screen"""
        pkt = network.ActionPacket()
        f3 = types.InputID(types.InputType.KEY, glfw.KEY_F3)
        pkt.inputs = [
            types.InputEvent.from_id(f3, types.GlfwAction.PRESS),
            types.InputEvent.from_id(f3, types.GlfwAction.RELEASE),
        ]
        self.step_raw(pkt)
