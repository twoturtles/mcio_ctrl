import argparse
import sys
import textwrap

import mcio_remote as mcio
from mcio_remote import LOG

def steps(n_steps: int, wait: bool = False):
    env = mcio.GymNewSync("Hello", render_mode="human")
    observation = env.reset(send_reset=False)
    LOG.info(f'Reset: {observation}')
    if n_steps == 0 or wait:
        n_steps = sys.maxsize # Go forever
    for i in range(n_steps):
        if wait:
            input("Step> ")
        action = mcio.ActionPacket()
        observation = env.step(action)
        LOG.info(f'Step {i}: {observation}')

    env.close()

def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
                                    '''),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--steps', '-s', type=int, default=1,
                        help='Number of steps, 0 for forever')
    parser.add_argument('--wait', '-w', action='store_true', help="Wait for enter between steps")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    steps(args.steps, args.wait)