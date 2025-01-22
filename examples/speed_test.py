"""Basic step speed test"""

import argparse
import time
from collections import defaultdict
from typing import Any

from mcio_remote import types
from mcio_remote.mcio_env.envs import mcio_env


def minerl_setup() -> Any:
    # gym version 0.23.1
    import gym  # type: ignore

    # import minerl  # minerl version 1.0.2
    # logging.basicConfig(level=logging.DEBUG)
    # Defaults to frame shape (360, 640, 3)
    env = gym.make("MineRLBasaltFindCave-v0")
    env.reset()
    return env


def mcio_setup() -> mcio_env.MCioEnv:
    # mcio inst launch DemoInstance -m sync -w Survival1 -W 640 -H 360
    # env = mcio_env.MCioEnv(render_mode=None, width=640, height=360)
    opts = types.RunOptions(
        instance_name="DemoInstance",
        world_name="DemoWorld",
        width=640,
        height=360,
        mcio_mode="sync",
        hide_window=True,
    )
    env = mcio_env.MCioEnv(opts, launch=True)
    env.reset()
    return env


def minerl_run(env: Any, num_steps: int) -> None:
    action: dict[str, Any] = defaultdict(
        int
    )  # This will return 0 for any unspecified key
    for step in range(num_steps):
        if step % 50 == 0:
            print(f"Step {step + 1}: {action}")
        env.step(action)


def mcio_run(env: mcio_env.MCioEnv, num_steps: int) -> None:
    action = env.get_noop_action()
    for step in range(num_steps):
        if step % 50 == 0:
            print(f"Step {step + 1}: {action}")
        env.step(action)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("mode", type=str, choices=["mcio", "minerl"], help="Test mode")
    parser.add_argument("--steps", "-s", type=int, default=1000, help="Number of steps")

    args = parser.parse_args()
    return args


def main() -> None:
    args = parse_args()

    env: mcio_env.MCioEnv | Any
    start = time.perf_counter()
    if args.mode == "minerl":
        env = minerl_setup()
    else:
        env = mcio_setup()
    setup_time = time.perf_counter() - start

    start = time.perf_counter()
    if args.mode == "minerl":
        minerl_run(env, args.steps)
    else:
        mcio_run(env, args.steps)
    run_time = time.perf_counter() - start
    print(
        f"steps={args.steps} setup={setup_time} run={run_time} steps_per_sec={args.steps/run_time:.2f}"
    )


if __name__ == "__main__":
    main()
