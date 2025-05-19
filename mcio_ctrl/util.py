import argparse
import logging
import queue
import shutil
import time
import types
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

import cv2
import minecraft_launcher_lib as mll
import numpy as np
import requests
from numpy.typing import NDArray
from tqdm import tqdm

from . import types as mcio_types

LOG = logging.getLogger(__name__)

##
# Logging


def logging_add_arg(
    parser: argparse.ArgumentParser, default: int | str = "INFO"
) -> None:
    """Add a default logging argument to argparse"""
    parser.add_argument(
        "--log-level",
        "-L",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=default,
        help="Set the logging level (default: INFO)",
    )


_FMT = "[%(asctime)s] [%(threadName)s/%(levelname)s] (%(name)s) %(message)s"
_DATEFMT = "%H:%M:%S"


def logging_init(
    *,
    args: argparse.Namespace | None = None,
    level: int | str | None = None,
    use_colors: bool = True,
) -> None:
    """Default log init. If args are passed (see logging_add_arg), level is pulled
    from that. Otherwise uses a passed in level. Finally defaults to INFO"""
    if args is not None:
        level = getattr(logging, args.log_level.upper(), logging.INFO)
    elif level is None:
        level = logging.INFO

    if use_colors:
        handler = logging.StreamHandler()
        handler.setFormatter(LogColorFormatter())
        logging.basicConfig(level=level, handlers=[handler])
    else:
        logging.basicConfig(level=level, format=_FMT, datefmt=_DATEFMT)


class LogColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }

    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        fmt = f"{color}{_FMT}{self.RESET}"
        formatter = logging.Formatter(fmt, datefmt=_DATEFMT)
        return formatter.format(record)


##
# Cursor drawing. Normally the OS adds the cursor, so frames from Minecraft do
# not show the cursor. These are to add the cursor.
class CursorDrawer(Protocol):
    def draw_cursor(
        self, frame: NDArray[np.uint8], cursor_pos: tuple[float, float]
    ) -> None:
        """Draw the cursor onto the frame. Assumes the frame is writable."""
        ...


class MinerlCursor(CursorDrawer):
    MINERL_CURSOR_FILE = "minerl_cursor_16x16.npy"

    def __init__(self) -> None:
        """The default cursor used by MineRL"""
        cursor_file = mcio_types.RESOURCES_DIR / self.MINERL_CURSOR_FILE
        with cursor_file.open("rb") as f:
            cursor_data = np.load(f)
        self.cursor_alpha = cursor_data[:16, :16, 3:] / 255.0
        self.cursor_image = cursor_data[:16, :16, :3] * self.cursor_alpha

    def draw_cursor(
        self,
        frame: NDArray[np.uint8],
        cursor_pos: tuple[float, float],
    ) -> None:
        """Draw a cursor on a raw frame"""
        x, y = int(cursor_pos[0]), int(cursor_pos[1])
        h, w = frame.shape[:2]

        if x < 0 or x >= w or y < 0 or y >= h:
            return  # Cursor out of frame

        ch = min(h - y, self.cursor_image.shape[0])
        cw = min(w - x, self.cursor_image.shape[1])

        background = frame[y : y + ch, x : x + cw]
        cropped_alpha = self.cursor_alpha[:ch, :cw]
        cropped_image = self.cursor_image[:ch, :cw]

        frame[y : y + ch, x : x + cw] = (
            background * (1 - cropped_alpha) + cropped_image
        ).astype(frame.dtype)


class CrosshairCursor(CursorDrawer):
    def __init__(
        self, color: tuple[int, int, int] = (255, 0, 0), arm_length: int = 5
    ) -> None:
        self.color = color
        self.arm_length = arm_length

    def draw_cursor(
        self,
        frame: NDArray[np.uint8],
        cursor_pos: tuple[float, float],
    ) -> None:
        """Draw a crosshair cursor on a raw frame"""
        x, y = int(cursor_pos[0]), int(cursor_pos[1])
        h, w = frame.shape[:2]

        if x < 0 or x >= w or y < 0 or y >= h:
            return  # Cursor out of frame

        # Bounds checks
        x_min = max(0, x - self.arm_length)
        x_max = min(w, x + self.arm_length + 1)
        y_min = max(0, y - self.arm_length)
        y_max = min(h, y + self.arm_length + 1)

        frame[y, x_min:x_max] = self.color  # Horizontal line
        frame[y_min:y_max, x] = self.color  # Vertical line


# Pre-load the default
DEFAULT_CURSOR_DRAWER = MinerlCursor()

##
# LatestItemQueue

T = TypeVar("T")


class LatestItemQueue(queue.Queue[T]):
    """
    Threadsafe Queue that only saves the most recent item.
    Puts replace any item on the queue.
    """

    def __init__(self) -> None:
        super().__init__(maxsize=1)

    def put(self, item: T) -> bool:  # type: ignore[override]
        """Return True if the previous packet had to be dropped"""
        dropped = False
        try:
            # Discard the current item if the queue isn't empty
            self.get_nowait()
            dropped = True
        except queue.Empty:
            pass

        super().put(item)
        return dropped

    def get(self, block: bool = True, timeout: float | None = None) -> T:
        """
        The same as Queue.get, except this automatically calls task_done()
        I'm not sure task_done() really matters for how we're using Queue.
        Can raise queue.Empty if non-blocking or timeout
        """
        item = super().get(block=block, timeout=timeout)
        super().task_done()
        return item


class TrackPerSecond:
    def __init__(self, name: str, log_time: float | None = 10.0):
        self.name = name
        self.start = time.time()
        self.end = self.start
        self.item_count = 0

        self.log_start = self.start
        self.log_time = log_time
        self.log_count = 0

    def count(self) -> None:
        """Increment the counter and log every log_time"""
        self.end = time.time()
        self.item_count += 1
        self.log_count += 1
        if self.log_time is not None and self.end - self.log_start >= self.log_time:
            per_sec = self.log_count / (self.end - self.log_start)
            LOG.info(f"{self.name}: {per_sec:.1f}")
            self.log_count = 0
            self.log_start = self.end

    def avg_rate(self) -> float:
        """Return the average rate"""
        return self.item_count / (self.end - self.start)


##


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


class InstallProgress:
    """Progress bar for minecraft_launcher_lib installer"""

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


##
# Mojang web API utils
def mojang_get_version_manifest() -> dict[Any, Any]:
    """Example:
    {
      "latest": {
        "release": "1.21.4",
        "snapshot": "1.21.4"
      },
      "versions": [
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
    versions_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    response = requests.get(versions_url)
    response.raise_for_status()
    manifest: dict[Any, Any] = response.json()
    return manifest


def mojang_get_version_info(mc_version: str) -> dict[str, Any]:
    manifest = mojang_get_version_manifest()
    ver_list = manifest["versions"]
    ver_info: dict[str, Any]
    for ver_info in ver_list:
        if ver_info["id"] == mc_version:
            return ver_info
    raise ValueError(f"Version not found: {mc_version}")


def mojang_get_version_details(mc_version: str) -> dict[str, Any]:
    ver_info = mojang_get_version_info(mc_version)
    ver_details_url = ver_info["url"]

    response = requests.get(ver_details_url)
    response.raise_for_status()
    ver_details: dict[str, Any] = response.json()
    return ver_details


##
# Misc utils


def rmrf(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_dir(src: Path, dst: Path, overwrite: bool = False) -> None:
    if not src.exists():
        raise ValueError(f"Source is missing: {src}")
    if not src.is_dir():
        raise ValueError(f"Source is not a directory: {src}")
    if dst.exists():
        if overwrite:
            rmrf(dst)
        else:
            raise ValueError(f"Destination exists: {dst}")
    shutil.copytree(src, dst)


class VideoWriter:
    def __init__(self) -> None:
        self.frames: list[NDArray[np.uint8]] = []

    def add(self, frame: NDArray[np.uint8]) -> None:
        self.frames.append(frame)

    def write(self, filename: str, fps: float = 20.0, codec: str = "avc1") -> None:
        height, width, _ = self.frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*codec)  # type: ignore[attr-defined]
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        for frame in self.frames:
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(bgr)
        out.release()
