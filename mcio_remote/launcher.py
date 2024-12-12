"""Interface for managing and launching Minecraft instances"""

import argparse
import subprocess
import uuid
from pathlib import Path
from typing import Any, Final

from tqdm import tqdm

import minecraft_launcher_lib as mll

DEFAULT_MINECRAFT_DIR: Final[str] = "~/.mcio/minecraft"
DEFAULT_MINECRAFT_VERSION: Final[str] = "1.21.3"
DEFAULT_MINECRAFT_USER: Final[str] = "MCio"


class Launcher:

    def __init__(
        self,
        mc_dir: Path | str | None = None,
        mc_username: str = DEFAULT_MINECRAFT_USER,
        mc_version: str = DEFAULT_MINECRAFT_VERSION,
        do_install: bool = True,
    ) -> None:
        mc_dir = mc_dir or DEFAULT_MINECRAFT_DIR
        mc_dir = Path(mc_dir).expanduser()

        if do_install:
            install(mc_version, mc_dir)

        mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, mc_username)
        options = mll.types.MinecraftOptions(
            username=mc_username, uuid=str(mc_uuid), token="MCioDev"
        )
        mc_cmd = mll.command.get_minecraft_command(mc_version, mc_dir, options)
        mc_cmd = self._update_option_argument(mc_cmd, "--userType", "legacy")
        subprocess.run(mc_cmd)

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


def install(
    mc_version: str = DEFAULT_MINECRAFT_VERSION, mc_dir: Path | str | None = None
) -> None:
    mc_dir = mc_dir or DEFAULT_MINECRAFT_DIR
    mc_dir = Path(mc_dir).expanduser()

    progress = _InstallProgress()
    mll.install.install_minecraft_version(
        mc_version, mc_dir, callback=progress.get_callbacks()
    )
    progress.close()

    # Disable narrator
    opts = OptionsTxt(mc_dir / "options.txt")
    opts["narrator"] = "0"
    opts.save()


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )

    # Command mode
    parser.add_argument(
        "mode",
        choices=["install", "launch"],
        help="Mode of operation: install Minecraft or launch the game",
    )

    # Optional arguments
    parser.add_argument(
        "--minecraft-dir",
        "-d",
        type=str,
        help=f"Minecraft directory (default: {DEFAULT_MINECRAFT_DIR})",
    )
    parser.add_argument(
        "--version",
        "-v",
        type=str,
        default=DEFAULT_MINECRAFT_VERSION,
        help=f"Minecraft version to install/launch (default: {DEFAULT_MINECRAFT_VERSION})",
    )
    parser.add_argument(
        "--username",
        "-u",
        type=str,
        default=DEFAULT_MINECRAFT_USER,
        help=f"Player name (default: {DEFAULT_MINECRAFT_USER})",
    )
    parser.add_argument(
        "--install",
        "-i",
        action="store_true",
        default=False,
        help="Install Minecraft before launching (only applies to launch mode)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.mode == "install":
        install(mc_version=args.version, mc_dir=args.minecraft_dir)
    else:  # launch
        launcher = Launcher(
            mc_dir=args.minecraft_dir,
            mc_username=args.username,
            mc_version=args.version,
            do_install=args.install,  # Use the install flag
        )
