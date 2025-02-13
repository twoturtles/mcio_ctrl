"""Speed test the python side (mcio_remote)"""

import argparse
import sys
from typing import Any

# import numpy as np
from tqdm import tqdm

import mcio_remote as mcio


class SpeedTest:

    def __init__(
        self,
        steps: int | None = None,
        frame_height: int = 854,
        frame_width: int = 480,
        process_frames: bool = True,
        display_frames: bool = False,
    ) -> None:
        self.steps = steps or sys.maxsize
        self.frame_height = frame_height
        self.frame_width = frame_width
        # display requires process
        self.process_frames = process_frames or display_frames
        self.display_frames = display_frames

        if self.display_frames:
            self.gui = mcio.gui.ImageStreamGui(
                height=self.frame_height, width=self.frame_width
            )

    def run(self) -> None:
        # frame_shape = (0, 0, 3)  # 10754.7 fps
        # frame_shape = (480, 854, 3)  # 1370.8 fps
        # frame_shape = (1000, 2000, 3)  # 59.3 fps

        mm = mcio.mc_mock.MockMinecraft(
            generate_observation_class=GenerateObservation,
            process_action_class=ProcessAction,
        )
        self.ctrl = mcio.controller.ControllerSync()

        # Time the generate action / process observation loop
        for i in tqdm(range(self.steps)):
            self.ctrl.send_action(mcio.network.ActionPacket())

            obs_recv = self.ctrl.recv_observation()
            if self.process_frames:
                frame = obs_recv.get_frame_with_cursor()
            if self.display_frames:
                self.gui.show(frame)

        mm.close()
        self.ctrl.close()


class GenerateObservation(mcio.mc_mock.GenerateObservation):
    def initialize(self, options: dict[Any, Any] | None) -> None:
        self.counter = mcio.util.TrackPerSecond("GenerateObservationPPS")

        # # Prepare the fake observation as much as possible outside the loop
        # self.obs_sequence = 0
        # self.base_obs = mcio.network.ObservationPacket()
        # self.base_obs.frame_height = frame_height
        # self.base_obs.frame_width = frame_width
        # self.frame_array = np.zeros((frame_height * frame_width * 3,), dtype=np.uint8)
        # self.base_obs.frame = self.frame_array.tobytes()
        # self.base_obs.frame_type = mcio.network.FrameType.RAW

    def generate_observation(self) -> mcio.network.ObservationPacket:
        self.counter.count()
        # self.frame_array[self.obs_sequence % self.frame_array.size] = 0xFF
        # self.obs_sequence += 1
        # self.base_obs.frame = self.frame_array.tobytes()
        return mcio.network.ObservationPacket()


class ProcessAction(mcio.mc_mock.ProcessAction):
    def initialize(self, options: dict[Any, Any] | None) -> None:
        self.counter = mcio.util.TrackPerSecond("ProcessActionPPS")

    def process_action(self, action: mcio.network.ActionPacket) -> None:
        self.counter.count()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speed test mcio_remote")

    mcio.util.logging_add_arg(parser)

    parser.add_argument("--steps", "-s", type=int, help="Number of steps")
    parser.add_argument("--width", "-W", type=int, default=854, help="Frame width")
    parser.add_argument("--height", "-H", type=int, default=480, help="Frame height")
    parser.add_argument(
        "--multi", "-M", action="store_true", help="Use multiple threads"
    )
    parser.add_argument(
        "--no-frames", "-F", action="store_true", help="Disable frame processing"
    )
    parser.add_argument("--gui", "-G", action="store_true", help="Display frames")

    args = parser.parse_args()
    mcio.util.logging_init(args=args)
    return args


def main() -> None:
    args = parse_args()
    speed_test = SpeedTest(
        steps=args.steps,
        frame_height=args.height,
        frame_width=args.width,
        process_frames=not args.no_frames,
        display_frames=args.gui,
    )
    speed_test.run()


if __name__ == "__main__":
    main()
