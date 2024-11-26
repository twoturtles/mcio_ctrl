import argparse
import textwrap

import glfw

import mcio_remote as mcio
from mcio_remote import LOG

def tutorial():
    # env = gym.make("LunarLander-v3", render_mode="human")
    env = mcio.GymLite("Hello", render_mode="human")
    # observation, info = env.reset()
    observation = env.reset()
    LOG.debug(observation)

    # Go forward and press attack button
    action = mcio.ActionPacket(keys=[(glfw.KEY_W, glfw.PRESS)],
                               mouse_buttons=[(glfw.MOUSE_BUTTON_1, glfw.PRESS)])
    observation = env.step(action)
    LOG.debug(observation)

    steps = 0
    while True:
        # Cycle jumping on and off
        cycle = (steps // 50) % 2
        if cycle == 0:
            action = mcio.ActionPacket(keys=[(glfw.KEY_SPACE, glfw.PRESS)])
        elif cycle == 1:
            action = mcio.ActionPacket(keys=[(glfw.KEY_SPACE, glfw.RELEASE)])
        # observation, reward, terminated, truncated, info = env.step(action)
        observation = env.step(action)
        LOG.debug(observation)
        steps += 1

    env.close()

def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
            Demonstrate actions and observations
                                    '''),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    tutorial()