"""Similar to the MineRL "Hello World" tutorial
XXX Requires that Minecraft is started first (will fix)
"""

import argparse
import textwrap
import pprint

from mcio_remote.mcio_env.envs import mcio_env


def tutorial(steps: int) -> None:
    # gym.make doesn't seem to play well with type checking
    # env = gym.make("mcio_env/MCioEnv-v0", render_mode="human")
    env = mcio_env.MCioEnv(render_mode="human")

    step = 0
    setup_commands = [
        "time set day",
        "teleport @s 0  0 180 0",
        "summon minecraft:sheep ~2 ~2 ~2",
        "summon minecraft:cow ~-2 ~2 ~-2",
    ]
    observation, info = env.reset(
        options={"commands": setup_commands}
    )
    print_step(step, None, observation)
    step += 1
    done = False
    while not done and step < steps:
        # Cycle jumping on and off
        cycle = (steps // 50) % 2
        action = env.action_space.sample()
        if cycle == 0:
            action["keys"]["SPACE"] = mcio_env.PRESS
        elif cycle == 1:
            action["keys"]["SPACE"] = mcio_env.NO_PRESS

        # # # Go forward and press attack button
        action["keys"]["W"] = mcio_env.PRESS
        action["mouse_buttons"]["LEFT"] = mcio_env.PRESS
        observation, reward, terminated, truncated, info = env.step(action)
        print_step(step, action, observation)
        step += 1
        done = terminated or truncated

    env.close()


def print_step(
    step: int,
    action: mcio_env.MCioAction | None = None,
    observation: mcio_env.MCioObservation | None = None,
) -> None:
    print(f"Step {step}:")
    if action is not None:
        print(f"Action:\n{pprint.pformat(action)}")
    if observation is not None:
        print(f"Obs:\n{obs_to_string(observation)}")
    print("-" * 10)


def obs_to_string(obs: mcio_env.MCioObservation) -> str:
    """Return a pretty version of the observation as a string.
    Prints the shape of the frame rather than the frame itself"""
    frame = obs["frame"]
    obs["frame"] = frame.shape
    formatted = pprint.pformat(obs)
    obs["frame"] = frame
    return formatted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Demonstrate actions and observations
                                    """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--steps", "-s", type=int, default=100, help="Number of steps, 0 for forever"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # mcio.LOG.setLevel(mcio.logging.WARNING)

    tutorial(args.steps)
