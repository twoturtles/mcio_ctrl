import argparse
import textwrap

import glfw

import mcio_remote as mcio
from mcio_remote import LOG

env = mcio.GymLiteSync("Hello", render_mode=None)
env.reset()
