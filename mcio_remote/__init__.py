import logging

from . import network as network
from . import controller as controller
from . import gym_lite as gym_litle
from . import gui as gui
from . import env as env


def _setup_logger():
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(threadName)s/%(levelname)s] (%(name)s) %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger


LOG = _setup_logger()

# constants
__version__ = "0.1.0"
