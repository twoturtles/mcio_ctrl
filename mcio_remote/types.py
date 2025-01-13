"""Defines some common types for the module"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from . import config

# Project defines
DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480
DEFAULT_ACTION_PORT: Final[int] = 4001  # 4ction
DEFAULT_OBSERVATION_PORT: Final[int] = 8001  # 8bservation
DEFAULT_HOST = "localhost"  # For security, only localhost

McioMode = Literal["off", "async", "sync"]
DEFAULT_MCIO_MODE: Final[McioMode] = "async"


@dataclass(kw_only=True)
class RunOptions:
    """Options for running Minecraft

    Args:
        instance_name: Required if launching
        world_name: Launch directly into a world
        width: Frame width
        height: Frame height
        mcio_mode: sync/async
        action_port: port for action connection
        observation_port: port for observation connection
        mcio_dir: Top-level data directory
        java_path: Path to alternative java executable
        mc_username: Minecraft username
    """

    instance_name: config.InstanceName | None = None  # Required if launching
    world_name: config.WorldName | None = None

    width: int = DEFAULT_WINDOW_WIDTH
    height: int = DEFAULT_WINDOW_HEIGHT
    mcio_mode: McioMode = DEFAULT_MCIO_MODE

    action_port: int = DEFAULT_ACTION_PORT
    observation_port: int = DEFAULT_OBSERVATION_PORT

    mcio_dir: Path | str = config.DEFAULT_MCIO_DIR
    java_path: str | None = None  # To use a different java executable

    mc_username: str = DEFAULT_MINECRAFT_USER
    instance_dir: Path | None = field(init=False)  # Auto-generated
    mc_uuid: uuid.UUID = field(init=False)  # Auto-generated

    def __post_init__(self) -> None:
        from . import instance

        self.mc_uuid: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)
        self.mcio_dir = Path(self.mcio_dir).expanduser()
        im = instance.InstanceManager(self.mcio_dir)
        if self.instance_name is not None:
            self.instance_dir = im.get_instance_dir(self.instance_name)
        else:
            self.instance_dir = None
