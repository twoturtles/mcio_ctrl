"""Speed test the python side (mcio_remote)."""

import argparse

from tqdm import tqdm

import mcio_remote as mcio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speed test mcio_remote")

    mcio.util.logging_add_arg(parser)

    parser.add_argument("--steps", "-s", type=int, default=1000, help="Number of steps")

    args = parser.parse_args()
    mcio.util.logging_init(args=args)
    return args


def main() -> None:
    args = parse_args()

    mm = mcio.network.MockMinecraft()
    ctrl = mcio.controller.ControllerSync()
    obs = mcio.network.ObservationPacket()

    for _ in tqdm(range(args.steps)):
        ctrl.send_action(mcio.network.ActionPacket())
        mm.recv_action()

        mm.send_observation(obs)
        obs = ctrl.recv_observation()


if __name__ == "__main__":
    main()
