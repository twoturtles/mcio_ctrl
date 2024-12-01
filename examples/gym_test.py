import argparse
import textwrap

import mcio_remote as mcio
from mcio_remote import LOG

import gymnasium as gym


def run():
    env = gym.make('mcio_env/MCioEnv-v0', render_mode='human')
    step = 0
    observation, info = env.reset()
    print(f'Step {step}: {observation}')
    step += 1
    done = False
    while not done:
        action = mcio.ActionPacket()
        observation, reward, terminated, truncated, info = env.step(action)
        # print(f'Step {step}: {observation}')
        step += 1
        done = terminated or truncated

    env.close()

def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
                                    '''),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--steps', '-s', type=int, default=1,
                        help='Number of steps, 0 for forever')
    parser.add_argument('--wait', '-w', action='store_true', help="Wait for enter between steps. Overrides -s")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    #mcio.LOG.setLevel(mcio.logging.WARNING)

    run()