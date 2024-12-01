# setup
import logging


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

# module imports
from .network import *
from .controller import *
from .gym_lite import *
from .gui import *
from . import env

# constants
__version__ = "0.1.0"
