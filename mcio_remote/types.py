"""Defines some common types for the module"""

import enum
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self, Type, TypeVar, cast

import glfw  # type: ignore

from . import config

# Project defines
DEFAULT_MINECRAFT_USER: Final[str] = "MCio"
DEFAULT_WINDOW_WIDTH: Final[int] = 854
DEFAULT_WINDOW_HEIGHT: Final[int] = 480
DEFAULT_ACTION_PORT: Final[int] = 4001  # 4ction
DEFAULT_OBSERVATION_PORT: Final[int] = 8001  # 8bservation
DEFAULT_HOST = "localhost"  # For security, only localhost
DEFAULT_HIDE_WINDOW = False


class StrEnumUpper(enum.StrEnum):
    """Like StrEnum, but the values are same as the enum rather than lowercase."""

    # XXX Wait, why do we need this? Could just use Enum["FOO"] / Enum.FOO.name

    @staticmethod
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[str]
    ) -> str:
        return name


class MCioMode(StrEnumUpper):
    """MCio Mode"""

    OFF = enum.auto()
    ASYNC = enum.auto()
    SYNC = enum.auto()


DEFAULT_MCIO_MODE: Final[MCioMode] = MCioMode.ASYNC


##
# Protocol types


class FrameType(StrEnumUpper):
    """Observation frame type. Currently just RAW."""

    RAW = enum.auto()


@dataclass
class InventorySlot:
    """Minecraft inventory slot - slot number, item id, and count"""

    slot: int
    id: str
    count: int


##
# Define types for key/button actions
# XXX Five types for storing 3 ints might be a bit much


class InputType(enum.IntEnum):
    KEY = 0
    MOUSE = 1


# GLFW key/button code, e.g. glfw.KEY_LEFT_SHIFT or glfw.MOUSE_BUTTON_LEFT
type GlfwCode = int


class GlfwAction(enum.IntEnum):
    RELEASE = glfw.RELEASE
    PRESS = glfw.PRESS
    # Note, not using glfw.REPEAT


@dataclass(frozen=True)  # Hashable
class InputID:
    type: InputType
    code: GlfwCode

    @classmethod
    def from_ints(cls, type_int: int, code: int) -> "InputID":
        return cls(type=InputType(type_int), code=code)


@dataclass(order=True)
class InputEvent:
    """Full input event sent to Minecraft"""

    type: InputType  # key / mouse
    code: GlfwCode  # glfw code
    action: GlfwAction  # press / release

    @classmethod
    def from_ints(cls, type_int: int, code: int, action_int: int) -> "InputEvent":
        """Alternate constructor that converts from int types to the enums."""
        return cls(type=InputType(type_int), code=code, action=GlfwAction(action_int))

    @classmethod
    def from_id(cls, input_id: InputID, action: GlfwAction) -> "InputEvent":
        return cls(type=input_id.type, code=input_id.code, action=action)


##
# Env config RunOptions


class _UnsetType:
    """Sentinel class to distinguish Env fields with no explicit arg value"""

    def __repr__(self) -> str:
        return "<UNSET>"


UNSET: Final = _UnsetType()

T = TypeVar("T")


class RunOptions:
    """
    ## Options for running Minecraft

    All values have reasonable defaults. For common cases, use the provided
    classmethods (`for_launch`, `for_connect`) to simplify setup.

    Fields marked with "env" in the default can also be set via environment variable.
    Launcher will pass non-default values to MCio/Minecraft.
    The priority is: explicit `__init__` parameter > env > default.

    ### Args:
        #### Launching
        - `mcio_dir` (default: ~/.mcio/): Top-level data directory.
        - `instance_name` (default: None): Name of the instance to launch. Leave
            None to connect to an existing instance.
        - `world_name` (default: None): World to launch directly into.
            Recommended if launching an instance; otherwise, Minecraft will open to
            the main menu.

        #### Common
        - `mcio_mode` (default: env or async): Mode of communication (sync/async).
        - `width` (default: 854): Frame width.
        - `height` (default: 480): Frame height.
        - `hide_window` (default: env or False): Whether to hide the Minecraft window.
        - `gpu_lib` (default: None): Set __GLX_VENDOR_LIBRARY_NAME env var.
            Use to enable a gpu in headless mode on Linux. Possible values: nvida, amd, mesa

        #### Communication
        - `action_port` (default: env or 4001): Port used for the action connection.
        - `observation_port` (default: env or 8001): Port used for the observation connection.

        #### Advanced / Misc
        - `env_extra` (default: {}): Extra env vars to pass to Minecraft. Intended for dev / testing.
        - `mc_username` (default: MCio): Local Minecraft username.
        - `cleanup_on_signal` (default: True): Kill the launched Minecraft on SIGINT or SIGTERM (and exit).
        - `java_path` (default: None): Path to alternative java executable (for debugging / dev)

    ### Auto-generated fields
        - `instance_dir`: Path to the selected instance directory, or None if not launching.
        - `mc_uuid`: UUID derived from the Minecraft username.
    """

    def __init__(
        self,
        *,
        # Launching
        mcio_dir: Path | str = config.DEFAULT_MCIO_DIR,
        instance_name: config.InstanceName | None = None,
        world_name: config.WorldName | None = None,
        # Common
        mcio_mode: MCioMode | _UnsetType = UNSET,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
        hide_window: bool | _UnsetType = UNSET,
        gpu_lib: str | None = None,
        # Communication
        action_port: int | _UnsetType = UNSET,
        observation_port: int | _UnsetType = UNSET,
        # Advanced / Misc
        env_extra: dict[str, str] | None = None,
        mc_username: str = DEFAULT_MINECRAFT_USER,
        cleanup_on_signal: bool = True,
        mcio_log_cfg: Path | str | None = None,
        java_path: str | None = None,
    ) -> None:

        # Environment variables passed to MCio/Minecraft.
        # Only explicitly provided arguments are added to env_vars.
        # If an option's origin is already the environment, then we don't need
        # to set it again.
        # Options left as UNSET are not passed and will use the MCio default.
        self.env_vars: dict[str, str] = {}

        # Launching
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.instance_name = instance_name
        self.world_name = world_name

        # Common
        self.mcio_mode: MCioMode = self._resolve(
            MCioMode, mcio_mode, "MCIO_MODE", DEFAULT_MCIO_MODE
        )
        self.width = width
        self.height = height
        # XXX hide_window doesn't need a member var? Like mcio_log_cfg.
        self.hide_window: bool = self._resolve(
            bool, hide_window, "MCIO_HIDE_WINDOW", DEFAULT_HIDE_WINDOW
        )
        if gpu_lib is not None:
            self.env_vars["__GLX_VENDOR_LIBRARY_NAME"] = gpu_lib

        # Communication
        self.action_port: int = self._resolve(
            int, action_port, "MCIO_ACTION_PORT", DEFAULT_ACTION_PORT
        )
        self.observation_port: int = self._resolve(
            int, observation_port, "MCIO_OBSERVATION_PORT", DEFAULT_OBSERVATION_PORT
        )

        # Advanced / Misc
        self.mc_username = mc_username
        self.cleanup_on_signal = cleanup_on_signal
        self.java_path = java_path

        # MCIO_LOG_CFG gives a way to adjust the Minecraft logging. It's passed
        # to Minecraft via a java arg.
        _mlc = mcio_log_cfg or os.getenv("MCIO_LOG_CFG")
        if _mlc is not None:
            _mlc = str(Path(_mlc).resolve())
        self.mcio_log_cfg: str | None = _mlc

        # Auto-generated
        self.instance_dir: Path | None = self._instance_dir()
        self.mc_uuid = uuid.uuid5(uuid.NAMESPACE_URL, self.mc_username)

        # Copy env_extra. These will override any set by arguments or env vars.
        self.env_vars.update(env_extra or {})

    def _instance_dir(self) -> Path | None:
        if self.instance_name is None:
            return None

        from . import instance

        im = instance.InstanceManager(self.mcio_dir)
        return im.get_instance_dir(self.instance_name)

    def _resolve(
        self,
        typ: Type[T],
        arg_val: T | _UnsetType,
        env_key: str,
        default: T,
    ) -> T:
        """
        Pull field values from env variables and resolve based on priority.
        Also sets self.env_vars
        """
        if not isinstance(arg_val, _UnsetType):
            # Explicit arg_val. Save as env var to pass to MCio/Minecraft if
            # launching
            self.env_vars[env_key] = str(arg_val)
            return arg_val

        # Check for env val
        env_val = os.getenv(env_key)
        if env_val is None:
            return default
        try:
            if typ is bool:
                return cast(T, env_val.lower() in ("true", "1"))
            elif typ is int:
                return cast(T, int(env_val))
            elif typ is float:
                return cast(T, float(env_val))
            elif typ is str:
                return cast(T, env_val)
            elif issubclass(typ, enum.Enum):
                return cast(T, typ[env_val.upper()])
            else:
                raise ValueError(f"Unsupported conversion: type={typ.__name__}")
        except Exception as e:
            raise ValueError(
                f"Could not convert env var {env_key}={env_val!r} to {typ.__name__}: {e}"
            ) from e

    ##
    # Some simplified constructors for common cases

    @classmethod
    def for_launch(
        cls,
        instance_name: config.InstanceName,
        world_name: config.WorldName,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
    ) -> Self:
        """Simplified constructor for launching a Minecraft instance for an environment.
        This just creates the properly configured RunOptions. Launch using an env (or instance.Launcher).
        """

        return cls(
            instance_name=instance_name,
            world_name=world_name,
            width=width,
            height=height,
            mcio_mode=MCioMode.SYNC,
            hide_window=True,
        )

    @classmethod
    def for_connect(
        cls,
        width: int = DEFAULT_WINDOW_WIDTH,
        height: int = DEFAULT_WINDOW_HEIGHT,
    ) -> Self:
        """Simplified constructor for connecting to an already running Minecraft instance
        This just creates the properly configured RunOptions. Connect using an env
        """

        return cls(
            width=width,
            height=height,
            mcio_mode=MCioMode.SYNC,
            hide_window=True,
        )
