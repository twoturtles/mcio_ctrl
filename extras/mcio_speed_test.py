"""
Basic step speed test. Drives MCio in sync mode as fast as possible.

mcio inst launch DemoInstance -m sync -w DemoWorld -W 640 -H 360
SPEED-TEST mode=mcio steps=5000 setup=0.19 run=16.92 steps_per_sec=295.50
"""

import argparse
import logging
import time
from collections import defaultdict
from typing import Any

from tqdm import tqdm

import mcio_ctrl as mcio
from mcio_ctrl.envs import minerl_env


def mcio_setup(render: bool, connect: bool) -> Any:
    if connect:
        # To launch an instance:
        #  mcio inst launch DemoInstance -m sync -w DemoWorld -W 640 -H 360
        opts = mcio.types.RunOptions.for_connect(width=640, height=360)
    else:
        opts = mcio.types.RunOptions.for_launch(
            "DemoInstance", "DemoWorld", width=640, height=360
        )

    render_mode = "human" if render else None
    env = minerl_env.MinerlEnv(opts, render_mode=render_mode)
    setup_commands = [
        "time set day",
        "teleport @s ~ ~ ~ -90 0",  # face East, straight ahead
        "gamemode creative",  # Don't die. The death screen steps faster than the game.
    ]
    env.reset(options={"commands": setup_commands})
    env.skip_steps(25)  # Give the commands time to take effect
    return env


def mcio_run(
    env: Any,
    num_steps: int,
    render: bool,
    render_n: int | None,
    steps_completed: list[int],
) -> None:
    from mcio_ctrl.envs import minerl_env

    assert isinstance(env, minerl_env.MinerlEnv)

    action: dict[str, Any] = defaultdict(
        int
    )  # This will return 0 for any unspecified key
    action["camera"] = [0, 1]
    print(action)
    for i in tqdm(range(num_steps)):
        env.step(action)
        if render:
            env.render()
        elif render_n is not None and i % render_n == 0:
            env.render()
        steps_completed[0] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--steps", "-s", type=int, default=1000, help="Number of steps")
    parser.add_argument(
        "--render", "-r", action="store_true", help="render (show output frames)"
    )
    parser.add_argument("--render-n", "-R", type=int, help="show every n frames")
    parser.add_argument(
        "--connect",
        "-c",
        action="store_true",
        help="Connect to a separately launched Minecraft",
    )

    args = parser.parse_args()
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    do_render = args.render or args.render_n is not None

    start = time.perf_counter()
    env = mcio_setup(do_render, args.connect)
    setup_time = time.perf_counter() - start

    start = time.perf_counter()
    steps_completed = [0]
    try:
        mcio_run(env, args.steps, args.render, args.render_n, steps_completed)
    except KeyboardInterrupt:
        print("Exiting...")
    run_time = time.perf_counter() - start
    env.close()

    steps = steps_completed[0]
    print(
        f"MCIO-SPEED-TEST steps={steps} setup={setup_time:.2f} "
        f"run={run_time:.2f} steps_per_sec={steps/run_time:.2f}"
    )


if __name__ == "__main__":
    main()
