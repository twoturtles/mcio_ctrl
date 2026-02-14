"""Similar to the MineRL "Hello World" tutorial, using the mcio minerl
compatible environment. Just do random steps and display the results"""

import argparse

import numpy as np

import mcio_ctrl as mcio
from mcio_ctrl.envs import minerl_env


def tutorial(instance_name: str | None, world_name: str | None) -> None:
    if instance_name is not None:
        if world_name is None:
            raise ValueError("World name must be provided if instance name is provided")
        opts = mcio.types.RunOptions.for_launch(instance_name, world_name)
    else:
        opts = mcio.types.RunOptions.for_connect()

    # gym.make() works, but I prefer just creating the env instance directly.
    # env = gym.make("MCio/MinerlEnv-v0", render_mode="human", run_options=opts)
    # env = cast(minerl_env.MinerlEnv, env.unwrapped)  # Work around gym.make typing
    env = minerl_env.MinerlEnv(opts, render_mode="human")

    setup_commands = [
        "time set 0t",  # Just after sunrise
        "teleport @s ~ ~ ~ -90 0",  # face East
        # "summon minecraft:sheep ~2 ~2 ~2",
        # "summon minecraft:cow ~-2 ~2 ~-2",
    ]
    observation, info = env.reset(options={"commands": setup_commands})
    env.skip_steps(25)  # Give time for the commands to complete
    env.render()

    terminated = False
    while not terminated:
        action = env.action_space.sample()
        action["ESC"] = 0
        action["inventory"] = 0
        # Limit camera delta so it doesn't look so crazy
        action["camera"] = np.random.uniform(-1, 1, size=2).astype(np.float32)
        observation, reward, terminated, truncated, info = env.step(action)
        env.render()

    env.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo of using Minerl-compatible actions and observations.\n"
        "Connect to a running instance (default mode) or launch a specified instance and world.\n"
        "This will only work properly if Minecraft is in SYNC mode.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    mcio.util.logging_add_arg(parser)

    parser.add_argument(
        "--instance-name",
        "-i",
        type=str,
        help="Name of the Minecraft instance to launch",
    )
    parser.add_argument("--world", "-w", type=str, help="World name")

    args = parser.parse_args()
    mcio.util.logging_init(args=args)
    return args


if __name__ == "__main__":
    args = parse_args()

    tutorial(args.instance_name, args.world)
