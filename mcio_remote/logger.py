import logging


class Logger:
    COLORS = {
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "red-background": "\033[41m",
        "reset": "\033[0m",
    }

    def __init__(self, color: str | None = "cyan") -> None:
        # Get the root logger for mcio_remote
        self.root_logger = logging.getLogger("mcio_remote")
        if color is not None:
            color = self.COLORS[color]
            reset = self.COLORS["reset"]
        else:
            color = reset = ""
        if not self.root_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"{color}[%(asctime)s] [%(threadName)s/%(levelname)s] (%(name)s) %(message)s{reset}",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.root_logger.addHandler(handler)
            self.root_logger.setLevel(logging.INFO)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger for a specific module."""
        return logging.getLogger(name)

    def set_level(self, level: int) -> None:
        """Set the log level for all mcio_remote loggers."""
        self.root_logger.setLevel(level)


# mcio_remote root logger
LOG = Logger()
