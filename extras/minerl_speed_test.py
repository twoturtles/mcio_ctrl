"""
Minerl speed test for comparison and sanity check.
Use python 3.9
"""

import argparse
import logging
import time
from collections import defaultdict
from typing import Any, Optional

# gym version 0.23.1
import gym  # type: ignore

# minerl version 1.0.2
import minerl  # type: ignore # noqa: F401  # needed for gym registration
from tqdm import tqdm


def minerl_setup() -> Any:
    # logging.basicConfig(level=logging.DEBUG)
    # Defaults to frame shape (360, 640, 3)
    env = gym.make("MineRLBasaltFindCave-v0")
    env.reset()
    return env


def minerl_run(
    env: Any,
    num_steps: int,
    render: bool,
    render_n: Optional[int],
    steps_completed: list[int],
) -> None:
    action: dict[str, Any] = defaultdict(
        int
    )  # This will return 0 for any unspecified key
    action["camera"] = [0, 1]
    print(action)
    # Note: The minerl env seems to terminate after 3600 steps
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

    args = parser.parse_args()
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    start = time.perf_counter()
    env = minerl_setup()
    setup_time = time.perf_counter() - start

    start = time.perf_counter()
    steps_completed = [0]
    try:
        minerl_run(env, args.steps, args.render, args.render_n, steps_completed)
    except KeyboardInterrupt:
        print("Exiting...")
    run_time = time.perf_counter() - start
    env.close()

    steps = steps_completed[0]
    print(
        f"MINERL-SPEED-TEST steps={steps} setup={setup_time:.2f} "
        f"run={run_time:.2f} steps_per_sec={steps/run_time:.2f}"
    )


if __name__ == "__main__":
    main()
