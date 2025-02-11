"""Speed test the python side (mcio_remote)"""

import argparse
import sys

import numpy as np
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

        # Prepare the fake observation as much as possible outside the loop
        self.obs_sequence = 0
        self.base_obs = mcio.network.ObservationPacket()
        self.base_obs.frame_height = frame_height
        self.base_obs.frame_width = frame_width
        self.frame_array = np.zeros((frame_height * frame_width * 3,), dtype=np.uint8)
        self.base_obs.frame = self.frame_array.tobytes()
        self.base_obs.frame_type = mcio.network.FrameType.RAW

        if self.display_frames:
            self.gui = mcio.gui.ImageStreamGui(
                height=self.frame_height, width=self.frame_width
            )

    def run_multi(self) -> None:
        # frame_shape = (0, 0, 3)  # 10754.7 fps
        # frame_shape = (480, 854, 3)  # 1370.8 fps
        # frame_shape = (1000, 2000, 3)  # 59.3 fps

        # For multi-threaded
        self.obs_counter = mcio.util.TrackPerSecond("ObsPerSecond")
        self.act_counter = mcio.util.TrackPerSecond("ActPerSecond")

        mm = mcio.network.MockMinecraft(
            use_threads=True,
            get_observation_cb=self.get_obs,
            process_action_cb=self.process_action,
        )
        self.ctrl = mcio.controller.ControllerSync()

        # Time the generate action / process observation loop
        for i in tqdm(range(self.steps)):
            self.ctrl.send_action(mcio.network.ActionPacket())

            mm.recv_action()
            mm.send_observation(self.base_obs)

            obs_recv = self.ctrl.recv_observation()
            if self.process_frames:
                frame = obs_recv.get_frame_with_cursor()
            if self.display_frames:
                self.gui.show(frame)

    def run_single(self) -> None:
        mm = mcio.network.MockMinecraft(use_threads=False)
        self.ctrl = mcio.controller.ControllerSync()

        for i in tqdm(range(self.steps)):
            self.ctrl.send_action(mcio.network.ActionPacket())

            mm.recv_action()
            mm.send_observation(self.base_obs)

            obs_recv = self.ctrl.recv_observation()
            if self.process_frames:
                frame = obs_recv.get_frame_with_cursor()
            if self.display_frames:
                self.gui.show(frame)

    def get_obs(self) -> mcio.network.ObservationPacket:
        """Generate a fake observation as Minecraft"""
        # self.frame_array[self.obs_sequence % self.frame_array.size] = 0xFF
        # self.obs_sequence += 1
        # self.base_obs.frame = self.frame_array.tobytes()
        self.obs_counter.count()
        return self.base_obs

    def process_action(self, action: mcio.network.ActionPacket) -> None:
        """Process an action as Minecraft"""
        self.act_counter.count()
        pass


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
    if args.multi:
        speed_test.run_multi()
    else:
        speed_test.run_single()


if __name__ == "__main__":
    main()
