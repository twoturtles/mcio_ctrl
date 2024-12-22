"""Interface for managing and launching Minecraft instances"""

import subprocess
import uuid
from pathlib import Path
import os
from typing import Any, Final, Literal

import requests
import minecraft_launcher_lib as mll

from . import logger
from . import config
from . import util

LOG = logger.LOG.get_logger(__name__)

INSTANCES_SUBDIR: Final[str] = "instances"

DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480

REQUIRED_MODS: Final[tuple[str, ...]] = ("fabric-api", "mcio")

McioMode = Literal["off", "async", "sync"]


class Installer:
    """Install Minecraft along with Fabric and MCio"""

    def __init__(
        self,
        instance_name: "config.InstanceName",
        mcio_dir: Path | str | None = None,
        mc_version: str = config.DEFAULT_MINECRAFT_VERSION,
    ) -> None:
        self.instance_name = instance_name
        mcio_dir = mcio_dir or config.DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mc_version = mc_version
        self.instance_dir = get_instance_dir(self.mcio_dir, self.instance_name)

        with config.ConfigManager(self.mcio_dir) as cfg_mgr:
            if cfg_mgr.config.instances.get(self.instance_name) is not None:
                print(
                    f"Warning: Instance {self.instance_name} already exists in {cfg_mgr.config_file}"
                )

    def install(self) -> None:
        print(f"Installing Minecraft {self.mc_version} in {self.instance_dir}...")
        progress = util.InstallProgress()
        mll.install.install_minecraft_version(
            self.mc_version, self.instance_dir, callback=progress.get_callbacks()
        )
        progress.close()

        print("\nInstalling Fabric...")
        # Use the Minecraft jvm to install Fabric.
        jvm_info = mll.runtime.get_version_runtime_information(
            self.mc_version, self.instance_dir
        )
        assert jvm_info is not None
        # jvm_info = {'name': 'java-runtime-delta', 'javaMajorVersion': 21}
        java_cmd = mll.runtime.get_executable_path(jvm_info["name"], self.instance_dir)
        progress = util.InstallProgress()
        # XXX This doesn't check that the loader is compatible with the minecraft version
        fabric_ver = mll.fabric.get_latest_loader_version()
        mll.fabric.install_fabric(
            self.mc_version,
            self.instance_dir,
            loader_version=fabric_ver,
            callback=progress.get_callbacks(),
            java=java_cmd,
        )
        progress.close()
        # This is the format mll uses to generate the version string.
        # XXX Would prefer to get this automatically.
        fabric_minecraft_version = f"fabric-loader-{fabric_ver}-{self.mc_version}"

        # Install mods
        print()
        for mod in REQUIRED_MODS:
            self._install_mod(mod, self.instance_dir, self.mc_version)

        # XXX https://codeberg.org/JakobDev/minecraft-launcher-lib/issues/143
        err_path = self.instance_dir / "libraries/org/ow2/asm/asm/9.3/asm-9.3.jar"
        err_path.unlink()

        # Disable narrator
        with util.OptionsTxt(self.instance_dir / "options.txt", save=True) as opts:
            opts["narrator"] = "0"

        with config.ConfigManager(self.mcio_dir, save=True) as cfg_mgr:
            cfg_mgr.config.instances[self.instance_name] = config.InstanceConfig(
                id=self.instance_name,
                launch_version=fabric_minecraft_version,
                minecraft_version=self.mc_version,
            )
        print("Success!")

    def _install_mod(
        self,
        mod_id: str,
        instance_dir: Path,
        mc_ver: str,
        version_type: str = "release",
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

        mods_dir = instance_dir / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        print(f"Installing {filename}")
        with open(mods_dir / filename, "wb") as f:
            f.write(response.content)


class Launcher:
    """Launch Minecraft"""

    def __init__(
        self,
        instance_name: config.InstanceName,
        mcio_dir: Path | str | None = None,
        world_name: config.WorldName | None = None,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
        mcio_mode: McioMode = "async",
        mc_username: str = DEFAULT_MINECRAFT_USER,
    ) -> None:
        self.instance_name = instance_name
        mcio_dir = mcio_dir or config.DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mcio_mode = mcio_mode
        self.instance_dir = get_instance_dir(self.mcio_dir, self.instance_name)
        self.mc_username = mc_username
        self.mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)

        with config.ConfigManager(self.mcio_dir) as cm:
            instance_config = cm.config.instances.get(self.instance_name)
        if instance_config is None:
            raise ValueError(f"Missing instance_name in {cm.config_file}")
        self.launch_version = instance_config.launch_version

        # Store options
        options = mll.types.MinecraftOptions(
            username=mc_username,
            uuid=str(self.mc_uuid),
            token="MCioDev",
            customResolution=True,
            resolutionWidth=str(width),
            resolutionHeight=str(height),
        )
        if world_name is not None:
            options["quickPlaySingleplayer"] = world_name
        self.mll_options = options

        self._process: subprocess.Popen[str] | None = None

    def launch(self, wait: bool = True) -> None:
        env = self._get_env()
        cmd = self.get_command()
        # For some reason Minecraft logs end up in cwd, so set it to instance_dir
        self._process = subprocess.Popen(cmd, env=env, cwd=self.instance_dir, text=True)
        if wait:
            self._process.wait()
            self._process = None

    def close(self) -> None:
        # XXX Cleaner way to stop?
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except TimeoutError:
                self._process.kill()
        self._process = None

    def poll(self) -> int | None:
        """Return the process return code, or None if still running"""
        assert self._process is not None
        return self._process.poll()

    def wait(self) -> None:
        if self._process is not None:
            self._process.wait()
            self._process = None

    def get_command(self) -> list[str]:
        mc_cmd = mll.command.get_minecraft_command(
            self.launch_version, self.instance_dir, self.mll_options
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


##
# Utility functions


def get_instances_dir(mcio_dir: Path) -> Path:
    return mcio_dir / INSTANCES_SUBDIR


def get_instance_dir(mcio_dir: Path, instance_name: "config.InstanceName") -> Path:
    return get_instances_dir(mcio_dir) / instance_name


def get_saves_dir(mcio_dir: Path | str, instance_name: config.InstanceName) -> Path:
    SAVES_SUBDIR = "saves"
    mcio_dir = Path(mcio_dir).expanduser()
    instance_dir = get_instance_dir(mcio_dir, instance_name)
    return instance_dir / SAVES_SUBDIR


def instance_exists(mcio_dir: Path | str, instance_name: config.InstanceName) -> bool:
    mcio_dir = Path(mcio_dir).expanduser()
    instance_dir = get_instance_dir(mcio_dir, instance_name)
    return instance_dir.exists()


# XXX Replace with World usage
def get_world_list(
    mcio_dir: Path | str, instance_name: config.InstanceName
) -> list[str]:
    mcio_dir = Path(mcio_dir).expanduser()
    world_dir = get_saves_dir(mcio_dir, instance_name)
    world_names = [x.name for x in world_dir.iterdir() if x.is_dir()]
    return world_names
