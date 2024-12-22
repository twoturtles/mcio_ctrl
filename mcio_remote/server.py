import subprocess
from pathlib import Path
from typing import Final

import requests
import minecraft_launcher_lib as mll

from . import config
from . import util


class Server:
    """Install / interface with Minecraft server."""

    SERVERS_SUBDIR: Final[str] = "servers"

    def __init__(
        self,
        mcio_dir: Path = config.DEFAULT_MCIO_DIR,
        mc_version: config.MinecraftVersion = config.DEFAULT_MINECRAFT_VERSION,
    ) -> None:
        self.mcio_dir = mcio_dir
        self.mc_version = mc_version

        self.servers_dir = self.mcio_dir / self.SERVERS_SUBDIR
        self.servers_dir.mkdir(parents=True, exist_ok=True)

        self.server_version_dir = self.servers_dir / self.mc_version

        self._process: subprocess.Popen[str] | None = None

    def install_server(self) -> None:
        if self.is_installed():
            print(f"Server version {self.mc_version} already installed")
            return
        self.server_version_dir.mkdir(parents=True, exist_ok=True)

        print("Installing server...")
        info = util.mojang_get_version_details(self.mc_version)
        server_url = info["downloads"]["server"]["url"]
        server_jvm_version = info["javaVersion"]["component"]

        response = requests.get(server_url)
        response.raise_for_status()

        with open(self.server_version_dir / "server.jar", "wb") as f:
            f.write(response.content)
        self._write_eula()

        print("Install server java runtime")
        progress = util.InstallProgress()
        mll.runtime.install_jvm_runtime(
            server_jvm_version,
            self.server_version_dir,
            callback=progress.get_callbacks(),
        )

        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            cm.config.servers[self.mc_version] = config.ServerConfig(
                self.mc_version, server_jvm_version
            )

    def is_installed(self) -> bool:
        # Consider the dir existing as already installed
        return self.server_version_dir.exists()

    def set_server_properties(
        self, properties: dict[str, str], clear: bool = False
    ) -> None:
        if clear:
            self.clear_server_properties()
        with self._open_properties(save=True) as props:
            for key, value in properties.items():
                props[key] = value

    def clear_server_properties(self) -> None:
        with self._open_properties(save=True) as props:
            props.clear()

    def set_server_property(self, key: str, value: str) -> None:
        self.set_server_properties({key: value})

    def run(self) -> None:
        """This will generate the world. Make sure server.properties are set first."""
        assert self._process is None
        cmd = self.get_start_command()
        self._process = subprocess.Popen(
            cmd,
            cwd=self.server_version_dir,
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
        with config.ConfigManager(self.mcio_dir) as cm:
            server_config = cm.config.servers[self.mc_version]

        java_cmd = mll.runtime.get_executable_path(
            server_config.jvm_version, self.server_version_dir.resolve()
        )
        if java_cmd is None:
            raise ValueError("Error getting java command")
        cmd = [java_cmd]
        # Args from https://www.minecraft.net/en-us/download/server
        server_args = "-Xmx1024M -Xms1024M -jar server.jar nogui".split()
        return cmd + server_args

    def get_world_dir(self, world_name: config.WorldName) -> Path:
        return self.server_version_dir / world_name

    def delete_world_dir(self, world_name: config.WorldName) -> None:
        util.rmrf(self.get_world_dir(world_name))

    def _write_eula(self) -> None:
        with open(self.server_version_dir / "eula.txt", "w") as f:
            f.write("eula=true\n")

    def _open_properties(self, save: bool = False) -> util.OptionsTxt:
        return util.OptionsTxt(
            self.server_version_dir / "server.properties", separator="=", save=save
        )
