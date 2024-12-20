"""Interface for managing and launching Minecraft instances"""

import subprocess
import uuid
from pathlib import Path
import os
import random
import sys
import shutil
from typing import Any, Final, Literal
import types

from tqdm import tqdm
import requests
import minecraft_launcher_lib as mll

from . import logger
from . import config

LOG = logger.LOG.get_logger(__name__)

DEFAULT_MCIO_DIR: Final[Path] = Path("~/.mcio/").expanduser()
INSTANCES_SUBDIR: Final[str] = "instances"

DEFAULT_MINECRAFT_VERSION: Final[str] = "1.21.3"
DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480

REQUIRED_MODS: Final[tuple[str, ...]] = ("fabric-api", "mcio")

McioMode = Literal["off", "async", "sync"]


class Launcher:
    """Launch Minecraft"""

    def __init__(
        self,
        instance_id: config.InstanceID,
        mcio_dir: Path | str | None = None,
        world_name: config.WorldName | None = None,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
        mcio_mode: McioMode = "async",
        mc_username: str = DEFAULT_MINECRAFT_USER,
    ) -> None:
        self.instance_id = instance_id
        mcio_dir = mcio_dir or DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mcio_mode = mcio_mode
        self.instance_dir = get_instance_dir(self.mcio_dir, self.instance_id)
        self.mc_username = mc_username
        self.mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)

        with config.ConfigManager(self.mcio_dir) as cm:
            instance_config = cm.config.instances.get(self.instance_id)
        if instance_config is None:
            raise ValueError(f"Missing instance_id in {cm.config_file}")
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

    def launch(self) -> None:
        env = self._get_env()
        cmd = self.get_command()
        # For some reason Minecraft logs end up in cwd, so set it to instance_dir
        subprocess.run(cmd, env=env, cwd=self.instance_dir)

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


class Installer:
    """Install Minecraft along with Fabric and MCio"""

    def __init__(
        self,
        instance_id: "config.InstanceID",
        mcio_dir: Path | str | None = None,
        mc_version: str = DEFAULT_MINECRAFT_VERSION,
    ) -> None:
        self.instance_id = instance_id
        mcio_dir = mcio_dir or DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.mc_version = mc_version
        self.instance_dir = get_instance_dir(self.mcio_dir, self.instance_id)

        with config.ConfigManager(self.mcio_dir) as cfg_mgr:
            if cfg_mgr.config.instances.get(self.instance_id) is not None:
                print(
                    f"Warning: Instance {self.instance_id} already exists in {cfg_mgr.config_file}"
                )

    def install(self) -> None:
        print(f"Installing Minecraft in {self.instance_dir}...")
        progress = _InstallProgress()
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
        jvm_path = mll.runtime.get_executable_path(jvm_info["name"], self.instance_dir)
        progress = _InstallProgress()
        # XXX This doesn't check that the loader is compatible with the minecraft version
        fabric_ver = mll.fabric.get_latest_loader_version()
        mll.fabric.install_fabric(
            self.mc_version,
            self.instance_dir,
            loader_version=fabric_ver,
            callback=progress.get_callbacks(),
            java=jvm_path,
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

        # Download the server to use for world generation
        print()
        server = Server(mcio_dir=self.mcio_dir, mc_version=self.mc_version)
        server.install_server()

        # Disable narrator
        with OptionsTxt(self.instance_dir / "options.txt", save=True) as opts:
            opts["narrator"] = "0"

        with config.ConfigManager(self.mcio_dir, save=True) as cfg_mgr:
            cfg_mgr.config.instances[self.instance_id] = config.InstanceConfig(
                id=self.instance_id,
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
    """Load/Save options.txt. Keeps everything as strings.
    To work with server.properties instead, set separator to "="
    """

    def __init__(
        self,
        options_path: Path | str,
        separator: Literal[":", "="] = ":",
        save: bool = False,
    ) -> None:
        """Set save to true to save automatically on exiting"""
        self.save_on_exit = save
        self.path = Path(options_path).expanduser()
        self.sep = separator
        self.options: dict[str, str] | None = None

    def load(self) -> None:
        """Load options from file."""
        if not self.path.exists():
            # XXX Should we let the user know instead of creating an empty options?
            self.options = {}
            return

        with self.path.open("r") as f:
            txt = f.read()
        lines = txt.strip().split("\n")
        self.options = {}
        for line in lines:
            line = line.strip()
            if len(line) == 0 or line.startswith("#"):
                continue
            key, value = line.split(self.sep, 1)
            key = key.strip()
            value = value.strip()
            self.options[key] = value

    def save(self) -> None:
        """Save options back to file"""
        assert self.options is not None
        with self.path.open("w") as f:
            for key, value in self.options.items():
                f.write(f"{key}{self.sep}{value}\n")

    def clear(self) -> None:
        """Clear the file"""
        self.options = {}

    def __getitem__(self, key: str) -> str:
        assert self.options is not None
        return self.options[key]

    def __setitem__(self, key: str, value: str) -> None:
        assert self.options is not None
        self.options[key] = value

    def __enter__(self) -> "OptionsTxt":
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


class Server:
    """Install / interface with Minecraft server."""

    SERVERS_SUBDIR: Final[str] = "servers"

    def __init__(
        self,
        mcio_dir: Path,
        mc_version: str = DEFAULT_MINECRAFT_VERSION,
    ) -> None:
        self.mcio_dir = mcio_dir
        self.mc_version = mc_version

        self.servers_dir = self.mcio_dir / self.SERVERS_SUBDIR
        self.servers_dir.mkdir(parents=True, exist_ok=True)

        self.server_version_dir = self.servers_dir / self.mc_version
        self.server_version_dir.mkdir(parents=True, exist_ok=True)

        self._process: subprocess.Popen[str] | None = None

    def install_server(self) -> None:
        print("Installing server...")
        info = get_version_details(self.mc_version)
        server_url = info["downloads"]["server"]["url"]

        response = requests.get(server_url)
        response.raise_for_status()

        with open(self.server_version_dir / "server.jar", "wb") as f:
            f.write(response.content)
        self._write_eula()

        print("Install server java runtime")
        progress = _InstallProgress()
        mll.runtime.install_jvm_runtime(
            info["javaVersion"]["component"],
            self.server_version_dir,
            callback=progress.get_callbacks(),
        )

    def set_server_properties(
        self, properties: dict[str, str], clear: bool = False
    ) -> None:
        if clear:
            self.clear_server_properties()
        with self._load_properties(save=True) as props:
            for key, value in properties.items():
                props[key] = value

    def clear_server_properties(self) -> None:
        with self._load_properties(save=True) as props:
            props.clear()

    def set_server_property(self, key: str, value: str) -> None:
        self.set_server_properties({key: value})

    def run(self) -> None:
        """This will generate the world. Make sure server.properties are set first."""
        assert self._process is None
        cmd = self.get_start_command()
        self._process = subprocess.Popen(
            cmd,
            cwd=self.servers_dir,
            stdin=subprocess.PIPE,
            # stdout=subprocess.PIPE,
            # stderr=subprocess.PIPE,
            text=True,
        )

    def send_command(self, command: str) -> None:
        """Send a command to a running server."""
        assert self._process is not None
        assert self._process.stdin is not None  # For mypy
        if not command.endswith("\n"):
            command += "\n"
        self._process.stdin.write(command)
        self._process.stdin.flush()

    def stop(self) -> None:
        """Tell server to exit."""
        assert self._process is not None
        self.send_command("stop")
        self._process.wait()
        self._process = None

    def get_start_command(self) -> list[str]:
        """Get the shell command to start the server."""
        # XXX What should java version be?
        java_cmd = mll.runtime.get_executable_path(
            "java-runtime-delta", self.server_version_dir
        )
        if java_cmd is None:
            raise ValueError("Error getting java command")
        cmd = [java_cmd]
        # Args from https://www.minecraft.net/en-us/download/server
        server_args = "-Xmx1024M -Xms1024M -jar server.jar nogui".split()
        return cmd + server_args

    def _write_eula(self) -> None:
        with open(self.servers_dir / "eula.txt", "w") as f:
            f.write("eula=true\n")

    def _load_properties(self, save: bool = False) -> OptionsTxt:
        return OptionsTxt(
            self.servers_dir / "server.properties", separator="=", save=save
        )


# XXX Move server installation to World. Keep per mc version
class World:

    SERVER_WORLD_SUBDIR: Final[str] = "world"
    INSTANCE_WORLDS_SUBDIR: Final[str] = "saves"
    WORLD_STORAGE: Final[str] = "world_storage"

    def __init__(
        self,
        mcio_dir: Path | str | None = None,
    ) -> None:
        mcio_dir = mcio_dir or DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.storage_dir = self.mcio_dir / self.WORLD_STORAGE

    def generate(
        self,
        world_name: config.WorldName,
        instance_id: "config.InstanceID",  # XXX Used for generation
        gamemode: Literal[
            "survival", "creative", "adventure", "spectator"
        ] = "survival",
        difficulty: Literal["peaceful", "easy", "normal", "hard"] = "normal",
        seed: int | str | None = None,
        reset_server_properties: bool = False,
        server_properties: dict[str, str] | None = None,
    ) -> None:
        """
        Use this interface for generating worlds (vs. using the Server directly)
        https://minecraft.fandom.com/wiki/Server.properties

        This assumes the server has already been installed, which should
        be true. Installer does this automatically.

        You can set gamemode, difficulty, and level-seed via function arguments
        or server_properties. Values in server_properties will override function arguments.
        """
        if seed is None:
            seed = random.randint(0, sys.maxsize)
        seed = str(seed)

        instance_dir = get_instance_dir(self.mcio_dir, instance_id)
        server = Server(instance_dir)

        # Clear the world dir before generation
        world_dir = server.servers_dir / self.SERVER_WORLD_SUBDIR
        _rmrf(world_dir)

        # Use server to create world
        server_properties = server_properties or {}
        default_properties = {
            "gamemode": gamemode,
            "difficulty": difficulty,
            "level-seed": seed,
        }
        server_properties = default_properties | server_properties
        server.set_server_properties(server_properties, clear=reset_server_properties)
        # After stop the world dir should be ready
        print("Starting world generation...\n")
        server.run()
        server.stop()

        # Copy world to storage
        _copy_dir(world_dir, self.storage_dir / world_name)

        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            mc_ver = cm.config.instances[instance_id].minecraft_version
            cm.config.world_storage[world_name] = config.WorldConfig(
                name=world_name, minecraft_version=mc_ver
            )

        print("\nDone")

    def copy_from_storage(
        self,
        src_name: config.WorldName,
        dst_instance_id: config.InstanceID,
        dst_name: config.WorldName | None = None,
        overwrite: bool = False,
    ) -> None:
        dst_name = dst_name or src_name
        dst_instance_dir = get_instance_dir(self.mcio_dir, dst_instance_id)
        _copy_dir(
            self.storage_dir / src_name,
            dst_instance_dir / dst_name,
            overwrite=overwrite,
        )

    def copy_to_storage(
        self,
        src_instance_id: config.InstanceID,
        src_name: config.WorldName,
        dst_name: config.WorldName | None = None,
        overwrite: bool = False,
    ) -> None:
        dst_name = dst_name or src_name
        src_instance_dir = get_instance_dir(self.mcio_dir, src_instance_id)
        _copy_dir(
            src_instance_dir / src_name,
            self.storage_dir / dst_name,
            overwrite=overwrite,
        )


##
# Utility functions


def get_instances_dir(mcio_dir: Path) -> Path:
    return mcio_dir / INSTANCES_SUBDIR


def get_instance_dir(mcio_dir: Path, instance_id: "config.InstanceID") -> Path:
    return get_instances_dir(mcio_dir) / instance_id


def get_saves_dir(instance_dir: Path) -> Path:
    SAVES_SUBDIR = "saves"
    return instance_dir / SAVES_SUBDIR


# XXX Replace with World usage
def get_world_list(mcio_dir: Path | str, instance_id: config.InstanceID) -> list[str]:
    mcio_dir = Path(mcio_dir).expanduser()
    instance_dir = get_instance_dir(mcio_dir, instance_id)
    world_dir = get_saves_dir(instance_dir)
    world_names = [x.name for x in world_dir.iterdir() if x.is_dir()]
    return world_names


def show(mcio_dir: Path | str) -> None:
    mcio_dir = Path(mcio_dir).expanduser()
    print(f"Available Instances in {mcio_dir}:")
    with config.ConfigManager(mcio_dir=mcio_dir) as cm:
        for inst_id, inst_info in cm.config.instances.items():
            print(f"  Instance ID: {inst_id})")
            world_list = get_world_list(mcio_dir, inst_id)
            print(f"    Worlds: {", ".join(world_list)}")


def get_version_manifest() -> dict[Any, Any]:
    versions_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    response = requests.get(versions_url)
    response.raise_for_status()
    manifest: dict[Any, Any] = response.json()
    return manifest


def get_version_info(mc_version: str) -> dict[str, Any]:
    """Example:
    {
      "id": "1.21.4",
      "type": "release",
      "url": "https://piston-meta.mojang.com/v1/packages/a3bcba436caa849622fd7e1e5b89489ed6c9ac63/1.21.4.json",
      "time": "2024-12-03T10:24:48+00:00",
      "releaseTime": "2024-12-03T10:12:57+00:00",
      "sha1": "a3bcba436caa849622fd7e1e5b89489ed6c9ac63",
      "complianceLevel": 1
    },
    """
    manifest = get_version_manifest()
    ver_list = manifest["versions"]
    ver_info: dict[str, Any]
    for ver_info in ver_list:
        if ver_info["id"] == mc_version:
            return ver_info
    raise ValueError(f"Version not found: {mc_version}")


def get_version_details(mc_version: str) -> dict[str, Any]:
    ver_info = get_version_info(mc_version)
    ver_details_url = ver_info["url"]

    response = requests.get(ver_details_url)
    response.raise_for_status()
    ver_details: dict[str, Any] = response.json()
    return ver_details


def _rmrf(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_dir(src: Path, dst: Path, overwrite: bool = False) -> None:
    if not src.exists():
        raise ValueError(f"Source is missing: {src}")
    if not src.is_dir():
        raise ValueError(f"Source is not a directory: {src}")
    if dst.exists():
        if overwrite:
            _rmrf(dst)
        else:
            raise ValueError(f"Destination exists: {dst}")
    shutil.copytree(src, dst)
