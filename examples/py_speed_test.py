"""
Speed test the python side (mcio_remote)

Results on my laptop:
frame=0x0x3 (0 bytes), process_frames=True, display_frames=False, rate=60137.2 fps
frame=480x854x3 (1229760 bytes), process_frames=True, display_frames=False, rate=2217.4 fps
frame=2000x1000x3 (6000000 bytes), process_frames=True, display_frames=False, rate=112.5 fps
"""

import argparse
import logging
from itertools import count
from typing import Any

import numpy as np
from tqdm import tqdm

import mcio_remote as mcio

LOG = logging.getLogger(__name__)


class SpeedTest:

    def __init__(
        self,
        steps: int | None = None,
        frame_height: int = 854,
        frame_width: int = 480,
        process_frames: bool = True,
        display_frames: bool = False,
    ) -> None:
        self.steps = steps
        self.frame_height = frame_height
        self.frame_width = frame_width

        if display_frames and (self.frame_height == 0 or self.frame_width == 0):
            raise ValueError("Cannot display frames with height or width of 0")
        # display requires process
        self.process_frames = process_frames or display_frames
        self.display_frames = display_frames

        if self.display_frames:
            self.gui = mcio.gui.ImageStreamGui(
                height=self.frame_height, width=self.frame_width
            )

    def run(self) -> None:
        obs_options = {
            "frame_height": self.frame_height,
            "frame_width": self.frame_width,
        }
        self.mm = mcio.mc_mock.MockMinecraft(
            generate_observation_class=GenerateObservation,
            observation_options=obs_options,
            process_action_class=ProcessAction,
        )
        self.ctrl = mcio.controller.ControllerSync()

        # Time the generate action / process observation loop
        self.counter = mcio.util.TrackPerSecond("SpeedTestPPS")
        for i in tqdm(count() if self.steps is None else range(self.steps)):
            self.ctrl.send_action(mcio.network.ActionPacket())

            obs_recv = self.ctrl.recv_observation()
            if self.process_frames:
                frame = obs_recv.get_frame_with_cursor()
            if self.display_frames:
                self.gui.show(frame)
            self.counter.count()

    def close(self) -> None:
        size = self.frame_height * self.frame_width * 3
        print(
            f"frame={self.frame_height}x{self.frame_width}x3 ({size} bytes), "
            f"process_frames={self.process_frames}, display_frames={self.display_frames}, "
            f"rate={self.counter.avg_rate():.1f} fps"
        )

        self.mm.close()
        self.ctrl.close()


class GenerateObservation(mcio.mc_mock.GenerateObservation):
    def initialize(self, options: dict[Any, Any] | None) -> None:
        assert options is not None
        self.counter = mcio.util.TrackPerSecond("GenerateObservationPPS")

        height = options["frame_height"]
        width = options["frame_width"]

        # # Prepare the fake observation as much as possible outside the loop
        self.obs_sequence = 0
        self.base_obs = mcio.network.ObservationPacket()
        self.base_obs.frame_height = height
        self.base_obs.frame_width = width
        frame_size = height * width * 3
        self.frame_array = np.zeros((frame_size,), dtype=np.uint8)
        self.base_obs.frame = self.frame_array.tobytes()
        self.base_obs.frame_type = mcio.network.FrameType.RAW

    def generate_observation(self) -> mcio.network.ObservationPacket:
        self.counter.count()
        # self.frame_array[self.obs_sequence % self.frame_array.size] = 0xFF
        # self.obs_sequence += 1
        # self.base_obs.frame = self.frame_array.tobytes()
        return self.base_obs


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
    try:
        speed_test.run()
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        speed_test.close()


if __name__ == "__main__":
    main()
