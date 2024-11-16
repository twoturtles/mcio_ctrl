import argparse
import textwrap

import glfw

import mcio_remote as mcio


def test(scale):
    # env = gym.make("LunarLander-v3", render_mode="human")
    env = mcio.Gym("Hello")
    # observation, info = env.reset()
    env.reset()

    action = mcio.ActionPacket(keys=[(glfw.KEY_W, glfw.PRESS)])
    observation = env.step(action)
    steps = 0
    while True:
        # observation, reward, terminated, truncated, info = env.step(action)
        cycle = (steps // 10) % 2
        if cycle == 0:
            action = mcio.ActionPacket(keys=[(glfw.KEY_SPACE, glfw.PRESS)])
        elif cycle == 1:
            action = mcio.ActionPacket(keys=[(glfw.KEY_SPACE, glfw.RELEASE)])
        observation = env.step(action)
        steps += 1

    # env.close()

def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
            Q to quit
                                    '''),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Window scale factor')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    app = test(args.scale)
    app.run()