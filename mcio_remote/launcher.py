"""Interface for managing and launching Minecraft instances"""

import argparse
import subprocess
import uuid
import pprint
from pathlib import Path
from typing import Any

from tqdm import tqdm

import minecraft_launcher_lib as mll


class Launcher:

    def __init__(
        self,
        mc_dir: Path | str | None = None,
        mc_username: str = "MCio",
        mc_version: str = "1.21.3",
        install: bool = True,
    ) -> None:
        mc_dir = mc_dir or "~/.mcio/minecraft"
        mc_dir = Path(mc_dir).expanduser()

        if install:
            progress = Progress()
            mll.install.install_minecraft_version(
                mc_version, mc_dir, callback=progress.get_callbacks()
            )

        mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, mc_username)
        options = mll.types.MinecraftOptions(
            username=mc_username, uuid=str(mc_uuid), token="MCioDev"
        )
        mc_cmd = mll.command.get_minecraft_command(mc_version, mc_dir, options)
        mc_cmd = self._update_option_argument(mc_cmd, "--userType", "legacy")
        pprint.pprint(mc_cmd)
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


class Progress:

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    launcher = Launcher()
