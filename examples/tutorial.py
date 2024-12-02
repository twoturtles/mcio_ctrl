import argparse
import textwrap
import pprint

import gymnasium as gym

import mcio_remote as mcio  # noqa: F401


def tutorial(steps):
    env = gym.make("mcio_env/MCioEnv-v0", render_mode="human")
    step = 0
    observation, info = env.reset(
        options={"commands": ["time set day", "teleport @s 0 -60 0 180 0"]}
    )
    print(f"Step {step}: {obs_to_string(observation)}")
    step += 1
    done = False
    while not done and step < steps:
        # Cycle jumping on and off
        # cycle = (steps // 50) % 2
        action = env.action_space.sample()
        # if cycle == 0:
        #     action['keys'] = [(glfw.KEY_SPACE, glfw.PRESS)]
        # elif cycle == 1:
        #     action['keys'] = [(glfw.KEY_SPACE, glfw.RELEASE)]

        # # Go forward and press attack button
        # action['keys'].append((glfw.KEY_W, glfw.PRESS))
        # action['mouse_buttons'] = [(glfw.MOUSE_BUTTON_1, glfw.PRESS)]
        observation, reward, terminated, truncated, info = env.step(action)
        print(f"Step {step}: {action}\n{obs_to_string(observation)}\n")
        step += 1
        done = terminated or truncated

    env.close()

def obs_to_string(obs: dict):
    """Return a pretty version of the observation as a string.
    Prints the shape of the frame rather than the frame itself"""
    frame = obs['frame']
    obs['frame'] = frame.shape
    formatted = pprint.pformat(obs)
    obs["frame"] = frame
    return formatted

def parse_args():
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
