"""Persistent config - mcio.yaml"""

import logging
import types
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Final, Optional, TypeAlias

import dacite
from ruamel.yaml import YAML

LOG = logging.getLogger(__name__)

##
# Global defines

DEFAULT_MCIO_DIR: Final[Path] = Path("~/.mcio/").expanduser()
DEFAULT_MINECRAFT_VERSION: Final[str] = "1.21.3"


##
# Configuration

# XXX Consider saving necessary config in each entity's directory

CONFIG_FILENAME: Final[str] = "mcio.yaml"
CONFIG_VERSION: Final[int] = 1
InstanceName: TypeAlias = str
WorldName: TypeAlias = str
MinecraftVersion: TypeAlias = str


@dataclass
class WorldConfig:
    name: WorldName = ""
    minecraft_version: MinecraftVersion = ""  # Save the version that created this world
    seed: str = ""


@dataclass
class InstanceConfig:
    name: InstanceName = ""
    launch_version: MinecraftVersion = ""
    minecraft_version: MinecraftVersion = ""
    worlds: dict[WorldName, WorldConfig] = field(default_factory=dict)


@dataclass
class ServerConfig:
    minecraft_version: MinecraftVersion = ""
    jvm_version: str = ""


@dataclass
class Config:
    config_version: int = CONFIG_VERSION  # XXX Eventually check this
    instances: dict[InstanceName, InstanceConfig] = field(default_factory=dict)
    world_storage: dict[WorldName, WorldConfig] = field(default_factory=dict)
    servers: dict[MinecraftVersion, ServerConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> Optional["Config"]:
        try:
            rv = dacite.from_dict(data_class=cls, data=config_dict)
        except Exception as e:
            # This means the dict doesn't match Config
            LOG.error(f"Failed to parse config file: {e}")
            return None
        return rv

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigManager:
    def __init__(self, mcio_dir: Path | str, save: bool = False) -> None:
        """Set save to true to save automatically on exiting"""
        self.save_on_exit = save
        mcio_dir = Path(mcio_dir).expanduser()
        self.config_file = mcio_dir / CONFIG_FILENAME
        self.yaml = YAML(typ="rt")
        self.config: Config = Config()

    def load(self) -> None:
        if self.config_file.exists():
            with open(self.config_file) as f:
                # load() returns None if the file has no data.
                cfg_dict = self.yaml.load(f) or {}
                self.config = Config.from_dict(cfg_dict) or Config()
        else:
            self.config = Config()

    def pformat(self) -> str:
        """Pretty print the config"""
        string_stream = StringIO()
        self.yaml.dump(self.config.to_dict(), string_stream)
        return string_stream.getvalue()

    def save(self) -> None:
        with open(self.config_file, "w") as f:
            self.yaml.dump(self.config.to_dict(), f)

    def __enter__(self) -> "ConfigManager":
        self.load()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> bool | None:
        if exc_type is None:
            # Clean exit
            if self.save_on_exit:
                self.save()
        return None
