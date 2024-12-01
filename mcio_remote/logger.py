import logging

class Logger:
    def __init__(self):
        # Get the root logger for mcio_remote
        self.root_logger = logging.getLogger("mcio_remote")
        if not self.root_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(asctime)s] [%(threadName)s/%(levelname)s] (%(name)s) %(message)s",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.root_logger.addHandler(handler)
            self.root_logger.setLevel(logging.INFO)

    def get_logger(self, name):
        """Get a logger for a specific module."""
        return logging.getLogger(name)

    def set_level(self, level):
        """Set the log level for all mcio_remote loggers."""
        self.root_logger.setLevel(level)


# mcio_remote root logger
LOG = Logger()
