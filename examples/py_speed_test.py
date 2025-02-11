"""Speed test the python side (mcio_remote)"""

import argparse
import sys

import numpy as np
from tqdm import tqdm

import mcio_remote as mcio


class SpeedTest:

    def __init__(
        self, steps: int | None = None, frame_height: int = 854, frame_width: int = 480
    ) -> None:
        self.steps = steps or sys.maxsize
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.obs_sequence = 0

        # Prepare the fake observation as much as possible outside the loop
        self.base_obs = mcio.network.ObservationPacket()
        self.base_obs.frame_height = frame_height
        self.base_obs.frame_width = frame_width
        self.frame_array = np.zeros((frame_height * frame_width * 3,), dtype=np.uint8)
        self.base_obs.frame = self.frame_array.tobytes()
        self.base_obs.frame_type = mcio.network.FrameType.RAW

    def run(self) -> None:
        # frame_shape = (0, 0, 3)  # 10754.7 fps
        # frame_shape = (480, 854, 3)  # 1370.8 fps
        # frame_shape = (1000, 2000, 3)  # 59.3 fps

        # gui = mcio.gui.ImageStreamGui(height=self.frame_height, width=self.frame_width)

        self.mm = mcio.network.MockMinecraft(
            use_threads=True,
            get_observation_cb=self.get_obs,
            process_action_cb=self.process_action,
        )
        self.ctrl = mcio.controller.ControllerSync()

        # Time the generate action / process observation loop
        for i in tqdm(range(self.steps)):
            self.ctrl.send_action(mcio.network.ActionPacket())
            # obs_send.frame[i % len(obs_send.frame)] = 255
            # obs_send.frame = np.zeros(frame_shape, dtype=np.uint8).tobytes()
            # frame = np.zeros(frame_shape, dtype=np.uint8)
            # frame[i % len(frame)] = 255
            # obs_send.frame = frame.tobytes()

            _ = self.ctrl.recv_observation()
            # frame = obs_recv.get_frame_with_cursor()
            # gui.show(frame)

    def run2(self) -> None:
        mm = mcio.network.MockMinecraft(use_threads=False)
        ctrl = mcio.controller.ControllerSync()

        obs = mcio.network.ObservationPacket()
        frame_shape = (0, 0, 3)  # 10754.7 fps
        # frame_shape = (480, 854, 3)  # 1370.8 fps
        # frame_shape = (1000, 2000, 3)  # 59.3 fps
        obs.frame = np.zeros(frame_shape, dtype=np.uint8).tobytes()
        obs.frame_height = frame_shape[0]
        obs.frame_width = frame_shape[1]
        obs.frame_type = mcio.network.FrameType.RAW
        print(len(obs.frame))

        # gui = mcio.gui.ImageStreamGui(height=frame_shape[0], width=frame_shape[1])

        for i in tqdm(range(self.steps)):
            ctrl.send_action(mcio.network.ActionPacket())
            mm.recv_action()

            mm.send_observation(obs)
            obs = ctrl.recv_observation()
            # frame = obs.get_frame_with_cursor()
            # gui.show(frame)

    def get_obs(self) -> mcio.network.ObservationPacket:
        """Generate a fake observation as Minecraft"""
        self.frame_array[self.obs_sequence % self.frame_array.size] = 0xFF
        self.obs_sequence += 1
        # self.base_obs.frame = self.frame_array.tobytes()
        return self.base_obs

    def process_action(self, action: mcio.network.ActionPacket) -> None:
        """Process an action as Minecraft"""
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speed test mcio_remote")

    mcio.util.logging_add_arg(parser)

    parser.add_argument("--steps", "-s", type=int, help="Number of steps")

    args = parser.parse_args()
    mcio.util.logging_init(args=args)
    return args


def main() -> None:
    args = parse_args()
    speed_test = SpeedTest(args.steps)
    speed_test.run()
    # speed_test.run2()


if __name__ == "__main__":
    main()
