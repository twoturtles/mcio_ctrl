"""Defines some common types for the module"""

from dataclasses import dataclass, field
import uuid
from pathlib import Path
from typing import Final, Literal

from . import config
from . import instance

DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480

McioMode = Literal["off", "async", "sync"]
DEFAULT_MCIO_MODE: Final[McioMode] = "async"


@dataclass(kw_only=True)
class EnvConfig:
    """Core configuration needed by MCioEnv (and LauncherOptions)"""

    width: int = DEFAULT_WINDOW_WIDTH
    height: int = DEFAULT_WINDOW_HEIGHT
    mcio_mode: McioMode = DEFAULT_MCIO_MODE


@dataclass(kw_only=True)
class LauncherOptions:
    """Options for launching Minecraft"""

    instance_name: config.InstanceName
    env_config: EnvConfig = field(default_factory=EnvConfig)
    # If world_name is None, Minecraft will launch to the main menu
    world_name: config.WorldName | None = None
    mc_username: str = DEFAULT_MINECRAFT_USER
    mc_uuid: uuid.UUID = field(init=False)  # Calculated automatically
    mcio_dir: Path | str = config.DEFAULT_MCIO_DIR
    instance_dir: Path = field(init=False)  # Calculated automatically
    java_path: str | None = None

    def __post_init__(self) -> None:
        self.mc_uuid: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)
        self.mcio_dir = Path(self.mcio_dir).expanduser()
        im = instance.InstanceManager(self.mcio_dir)
        self.instance_dir = im.get_instance_dir(self.instance_name)
