from typing import Literal

from . import controller, gui, network


class GymLite:
    """
    Stub in how gymn will work. Higher level interface than Controller.
    Useful for testing, otherwise use the real gymnasium env in mcio_env.py.
    """

    def __init__(
        self,
        name: str | None = None,
        render_mode: str | None = "human",
        mcio_mode: Literal["sync", "async"] = "sync",
    ):
        self.name = name
        self.render_mode = render_mode
        self.mcio_mode = mcio_mode
        self.ctrl: controller.ControllerCommon | None = None

    def reset(self, commands: list[str] | None = None) -> network.ObservationPacket:
        if commands is None:
            commands = []
        if self.render_mode == "human":
            self.gui = gui.ImageStreamGui()

        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()

        assert self.ctrl is not None

        action = network.ActionPacket(commands=commands)
        self.ctrl.send_action(action)
        observation = self.ctrl.recv_observation()
        self.render(observation)
        # TODO return observation, info
        return observation

    def render(self, observation: network.ObservationPacket) -> None:
        if self.render_mode == "human":
            frame = observation.get_frame_with_cursor()
            self.gui.show(frame)

    def step(self, action: network.ActionPacket) -> network.ObservationPacket:
        assert self.ctrl is not None
        self.ctrl.send_action(action)
        observation = self.ctrl.recv_observation()
        self.render(observation)
        # TODO return observation, reward, terminated, truncated, info
        return observation

    def close(self) -> None:
        # TODO
        ...
