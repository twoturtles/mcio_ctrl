"""Basic step speed test"""

import argparse
import logging
import time
from collections import defaultdict
from typing import Any


def minerl_setup() -> Any:
    # gym version 0.23.1
    import gym  # type: ignore

    # import minerl  # minerl version 1.0.2
    # logging.basicConfig(level=logging.DEBUG)
    # Defaults to frame shape (360, 640, 3)
    env = gym.make("MineRLBasaltFindCave-v0")
    env.reset()
    return env


def mcio_setup() -> Any:
    import mcio_remote as mcio
    from mcio_remote.mcio_env.envs import mcio_env

    # mcio inst launch DemoInstance -m sync -w Survival1 -W 640 -H 360
    # env = mcio_env.MCioEnv(render_mode=None, width=640, height=360)
    opts = mcio.types.RunOptions(
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


def mcio_run(env: Any, num_steps: int) -> None:
    from mcio_remote.mcio_env.envs import mcio_env

    assert isinstance(env, mcio_env.MCioEnv)
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
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

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

    env.close()
    print(
        f"SPEED-TEST mode={args.mode} steps={args.steps} setup={setup_time:.2f} "
        f"run={run_time:.2f} steps_per_sec={args.steps/run_time:.2f}"
    )


if __name__ == "__main__":
    main()
