"""Interface for managing and launching Minecraft instances"""

import subprocess
from dataclasses import dataclass, asdict, field
import uuid
from pathlib import Path
import os
from typing import Any, Final, Literal, Optional, TypeAlias

from tqdm import tqdm
import requests
from ruamel.yaml import YAML
import minecraft_launcher_lib as mll
import dacite

from . import logger

LOG = logger.LOG.get_logger(__name__)

DEFAULT_MCIO_DIR: Final[Path] = Path("~/.mcio/").expanduser()
INSTANCES_SUBDIR: Final[str] = "instances"
CONFIG_FILENAME: str = "mcio.yaml"

DEFAULT_MINECRAFT_VERSION: Final[str] = "1.21.3"
DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480

MCIO_MODE = Literal["off", "async", "sync"]

REQUIRED_MODS: list[str] = ["fabric-api", "mcio"]

# TODO
# multiple instances
# create world: name, seed, mode, difficulty, ...


class Launcher:
    """Launch Minecraft"""

    def __init__(
        self,
        instance_id: str,
        mcio_dir: Path | str | None = None,
        world: str | None = None,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
        mcio_mode: MCIO_MODE = "async",
        mc_username: str = DEFAULT_MINECRAFT_USER,
    ) -> None:
        self.instance_id = instance_id
        mcio_dir = mcio_dir or DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mcio_mode = mcio_mode
        self.mc_dir = get_minecraft_dir(self.mcio_dir, self.instance_id)
        self.mc_username = mc_username
        self.mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)

        cm = ConfigManager(self.mcio_dir)
        instance_config = cm.config.instances.get(self.instance_id)
        if instance_config is None:
            raise ValueError(f"Missing instance_id in {cm.config_file}")
        self.mc_version = instance_config.version

        # Store options
        options = mll.types.MinecraftOptions(
            username=mc_username,
            uuid=str(self.mc_uuid),
            token="MCioDev",
            customResolution=True,
            resolutionWidth=str(width),
            resolutionHeight=str(height),
        )
        if world:
            options["quickPlaySingleplayer"] = world
        self.mll_options = options

    def launch(self) -> None:
        env = self._get_env()
        cmd = self.get_command()
        # For some reason Minecraft logs end up in cwd, so set it to mc_dir
        subprocess.run(cmd, env=env, cwd=self.mc_dir)

    def get_command(self) -> list[str]:
        mc_cmd = mll.command.get_minecraft_command(
            self.mc_version, self.mc_dir, self.mll_options
        )
        mc_cmd = self._update_option_argument(mc_cmd, "--userType", "legacy")
        return mc_cmd

    def get_show_command(self) -> list[str]:
        """For testing, return the command that will be run"""
        cmd = [f"MCIO_MODE={self.mcio_mode}"]
        cmd += self.get_command()
        return cmd

    def _get_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["MCIO_MODE"] = self.mcio_mode
        return env

    def _update_option_argument(
        self, command_list: list[str], option: str, new_argument: str
    ) -> list[str]:
        try:
            new_list = command_list.copy()
            option_index = new_list.index(option)
            new_list[option_index + 1] = new_argument
            return new_list
        except ValueError:
            print(f"Option {option} not found in command list")
            raise
        except IndexError:
            print(f"Unexpected end of list after option {option}")
            raise


class Installer:
    """Install Minecraft along with Fabric and MCio"""

    def __init__(
        self,
        instance_id: str,
        mcio_dir: Path | str | None = None,
        mc_version: str = DEFAULT_MINECRAFT_VERSION,
    ) -> None:
        self.instance_id = instance_id
        mcio_dir = mcio_dir or DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mc_version = mc_version
        self.mc_dir = get_minecraft_dir(self.mcio_dir, self.instance_id)

        self.cfg_mgr = ConfigManager(self.mcio_dir)
        if self.cfg_mgr.config.instances.get(self.instance_id) is not None:
            print(f"Warning: Instance {self.instance_id} already exists in {self.cfg_mgr.config_file}")

    def install(self) -> None:
        print(f"Installing Minecraft in {self.mc_dir}...")
        progress = _InstallProgress()
        mll.install.install_minecraft_version(
            self.mc_version, self.mc_dir, callback=progress.get_callbacks()
        )
        progress.close()

        print("\nInstalling Fabric...")
        progress = _InstallProgress()
        # XXX This doesn't check that the loader is compatible with the minecraft version
        fabric_ver = mll.fabric.get_latest_loader_version()
        mll.fabric.install_fabric(
            self.mc_version, self.mc_dir, loader_version=fabric_ver, callback=progress.get_callbacks()
        )
        progress.close()
        # This is the format mll uses to generate the version string.
        # Would prefer to get this automatically.
        fabric_minecraft_version = f"fabric-loader-{fabric_ver}-{self.mc_version}"

        # Install mods
        print()
        for mod in REQUIRED_MODS:
            self._install_mod(mod, self.mc_dir, self.mc_version)

        # XXX https://codeberg.org/JakobDev/minecraft-launcher-lib/issues/143
        err_path = self.mc_dir / "libraries/org/ow2/asm/asm/9.3/asm-9.3.jar"
        err_path.unlink()

        # Disable narrator
        opts = OptionsTxt(self.mc_dir / "options.txt")
        opts["narrator"] = "0"
        opts.save()

        self.cfg_mgr.config.instances[self.instance_id] = Instance(fabric_minecraft_version)
        self.cfg_mgr.save()
        print("Success!")

    def _install_mod(
        self, mod_id: str, mc_dir: Path, mc_ver: str, version_type: str = "release"
    ) -> None:
        mod_info_url = f'https://api.modrinth.com/v2/project/{mod_id}/version?game_versions=["{mc_ver}"]'
        response = requests.get(mod_info_url)
        response.raise_for_status()
        info_list: list[Any] = response.json()

        found: dict[str, Any] | None = None
        for vers_info in info_list:
            if vers_info["version_type"] == version_type:
                found = vers_info
                break

        if not found:
            raise ValueError(
                f"No {version_type} version found for {mod_id} supporting Minecraft {mc_ver}"
            )
        # Is the jar always the first in the "files" list?
        jar_info = found["files"][0]
        response = requests.get(jar_info["url"])
        response.raise_for_status()
        filename = jar_info["filename"]

        mods_dir = mc_dir / "mods"
        mods_dir.mkdir(exist_ok=True)
        print(f"Installing {filename}")
        with open(mods_dir / filename, "wb") as f:
            f.write(response.content)


class _InstallProgress:
    """Progress bar for Minecraft installer"""

    def __init__(self, desc_width: int = 40) -> None:
        self.pbar: tqdm[Any] | None = None
        self.desc_width = desc_width
        self.current = 0

    def get_callbacks(self) -> mll.types.CallbackDict:
        return mll.types.CallbackDict(
            setStatus=self._set_status,
            setProgress=self._set_progress,
            setMax=self._set_max,
        )

    def close(self) -> None:
        if self.pbar:
            self.pbar.close()

    def _set_max(self, total: int) -> None:
        """The installer calls set_max multiple times. Create a new bar each time."""
        if self.pbar:
            self.pbar.close()
        self.pbar = tqdm(total=total)
        self.current = 0

    def _set_status(self, status: str) -> None:
        if self.pbar:
            status = status[: self.desc_width].ljust(self.desc_width)
            self.pbar.set_description(status)

    def _set_progress(self, current: int) -> None:
        if self.pbar:
            self.pbar.update(current - self.current)
            self.current = current


class OptionsTxt:
    """Load/Save options.txt. Keeps everything as strings."""

    def __init__(self, options_path: Path | str) -> None:
        self.path = Path(options_path).expanduser()
        self.options = self._load(self.path)

    def save(self) -> None:
        """Save options back to file"""
        with self.path.open("w") as f:
            for key, value in self.options.items():
                f.write(f"{key}:{value}\n")

    def __getitem__(self, key: str) -> str:
        return self.options[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.options[key] = value

    def _load(self, options_path: Path) -> dict[str, str]:
        """Load options from file"""
        if not self.path.exists():
            return {}

        with self.path.open("r") as f:
            txt = f.read()
        lines = txt.strip().split()
        options = {}
        for line in lines:
            line = line.strip()
            if len(line) == 0 or line.startswith("#"):
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            options[key] = value
        return options


def get_instances_dir(mcio_dir: Path) -> Path:
    return mcio_dir / INSTANCES_SUBDIR
def get_minecraft_dir(mcio_dir: Path, instance_id: str) -> Path:
    return get_instances_dir(mcio_dir) / instance_id


##
# Configuration

InstanceID: TypeAlias = str


@dataclass
class Instance:
    version: str = ""


@dataclass
class Config:
    instances: dict[InstanceID, Instance] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> Optional["Config"]:
        try:
            rv = dacite.from_dict(data_class=cls, data=config_dict)
        except Exception as e:
            # This means the dict doesn't match ConfigFile
            LOG.error(f"Failed to parse config file: {e}")
            return None
        return rv

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigManager:
    def __init__(self, mcio_dir: Path | str) -> None:
        mcio_dir = Path(mcio_dir).expanduser()
        self.config_file = mcio_dir / CONFIG_FILENAME
        self.yaml = YAML(typ="rt")
        self.config: Config = Config()
        self.load()

    def load(self) -> None:
        if self.config_file.exists():
            with open(self.config_file) as f:
                # load() returns None if the file has no data.
                cfg_dict = self.yaml.load(f) or {}
                self.config = Config.from_dict(cfg_dict) or Config()
        else:
            self.config = Config()

    def save(self) -> None:
        with open(self.config_file, "w") as f:
            self.yaml.dump(self.config.to_dict(), f)


def show(mcio_dir: Path | str) -> None:
    mcio_dir = Path(mcio_dir).expanduser()
    cm = ConfigManager(mcio_dir=mcio_dir)
    for inst_id, inst_info in cm.config.instances.items():
        for info in mll.utils.get_installed_versions(get_instances_dir(mcio_dir) / inst_id):
            print(info)
