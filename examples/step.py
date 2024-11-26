import argparse
import sys
import textwrap

import mcio_remote as mcio
from mcio_remote import LOG

# XXX Doesn't work if agent is started first

def steps(n_steps: int, wait: bool = False):
    env = mcio.GymLite("Hello", render_mode="human", mcio_mode='sync')
    observation = env.reset(send_reset=False)
    print(f'Step 1 (reset): {observation}')
    if n_steps == 0 or wait:
        n_steps = sys.maxsize # Go forever
    for i in range(1, n_steps):
        if wait:
            input("Step> ")
        action = mcio.ActionPacket()
        observation = env.step(action)
        print(f'Step {i+1}: {observation}')

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
    steps(args.steps, args.wait)