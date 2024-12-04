from typing import Literal, List


from . import controller
from . import network
from . import gui


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
        self.ctrl = None
        self._window_width = None
        self._window_height = None

    def reset(self, commands: List[str] | None = None) -> network.ObservationPacket:
        if commands is None:
            commands = []
        if self.render_mode == "human":
            self.gui = gui.ImageStreamGui()
        if self.mcio_mode == "async":
            self.ctrl = controller.ControllerAsync()
        else:
            self.ctrl = controller.ControllerSync()
        action = network.ActionPacket(commands=commands)
        self.ctrl.send_action(action)
        observation = self.ctrl.recv_observation()
        self.render(observation)
        # TODO return observation, info
        return observation

    def render(self, observation: network.ObservationPacket):
        if self.render_mode == "human":
            frame = observation.get_frame_with_cursor()
            self.gui.poll()
            self.gui.show(frame)

    def step(self, action):
        self.ctrl.send_action(action)
        observation = self.ctrl.recv_observation()
        self.render(observation)
        # TODO return observation, reward, terminated, truncated, info
        return observation

    def close(self):
        # TODO
        ...
