from pathlib import Path
import random
import sys
from typing import Final, Literal

from . import config
from . import util
from . import instance
from . import server

# STORAGE_LOCATION must equal StorageType
STORAGE_LOCATION: Final[str] = "storage"
StorageType = Literal["storage"]
LocationType = StorageType | config.InstanceName


class WorldManager:

    INSTANCE_WORLDS_SUBDIR: Final[str] = "saves"
    WORLD_STORAGE_SUBDIR: Final[str] = "world_storage"

    def __init__(
        self,
        mcio_dir: Path | str | None = None,
    ) -> None:
        mcio_dir = mcio_dir or config.DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.storage_dir = self.mcio_dir / self.WORLD_STORAGE_SUBDIR

    def create(
        self,
        world_name: config.WorldName,
        mc_version: config.MinecraftVersion = config.DEFAULT_MINECRAFT_VERSION,
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
        dst_dir = self.storage_dir / world_name
        if dst_dir.exists():
            print(f"World generation failed: world already exists: {dst_dir}")
            raise ValueError(f"World already exists: {dst_dir}")

        if seed is None:
            seed = random.randint(0, sys.maxsize)
        seed = str(seed)

        # Prepare for generation. Use server to create world
        svr = server.Server(mcio_dir=self.mcio_dir, mc_version=mc_version)
        # Install server if necessary
        if not svr.is_installed():
            print(f"Server version {mc_version} not installed. Installing...")
            svr.install_server()

        # Merge properties
        server_properties = server_properties or {}
        default_properties = {
            "gamemode": gamemode,
            "difficulty": difficulty,
            "level-seed": seed,
            "level-name": world_name,
        }
        server_properties = default_properties | server_properties
        svr.set_server_properties(server_properties, clear=reset_server_properties)

        # After stop the world dir should be ready
        print("Starting world generation...\n")
        svr.run()
        svr.stop()

        # Copy world to storage
        util.copy_dir(svr.get_world_dir(world_name), dst_dir)
        svr.delete_world_dir(world_name)

        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            cm.config.world_storage[world_name] = config.WorldConfig(
                name=world_name, minecraft_version=mc_version, seed=seed
            )

        print(f"\nDone: World saved to storage: {dst_dir}")

    def copy_cmd(self, src: str, dst: str) -> None:
        """Copy world for command line interface"""
        src_loc, src_world = src.split(":", 1)
        dst_loc, dst_world = dst.split(":", 1)
        self.copy(src_loc, src_world, dst_loc, dst_world)

    def copy(
        self,
        src_location: LocationType,  # "storage" or instance name
        src_world: config.WorldName,
        dst_location: LocationType,  # "storage" or instance name
        dst_world: config.WorldName | None = None,  # If None, uses src_world name
    ) -> None:
        """Copy a world between storage and instances.

        Args:
            src_location: Either "storage" or an instance name for the source
            src_world: Name of the world to copy
            dst_location: Either "storage" or an instance name for the destination
            dst_world: Name for the copied world. If None, uses the source world name
        """
        # Validate source location and get directory
        if src_location == STORAGE_LOCATION:
            src_dir = self.storage_dir
        else:
            if instance.instance_exists(self.mcio_dir, src_location):
                src_dir = instance.get_saves_dir(
                    mcio_dir=self.mcio_dir, instance_name=src_location
                )
            else:
                raise ValueError(f"Invalid src instance: {src_location}")

        # Validate source world exists
        if not (src_dir / src_world).exists():
            raise ValueError(f"Src world does not exist: {src_world}")

        # Validate destination location and get directory
        if dst_location == "storage":
            dst_dir = self.storage_dir
        else:
            if instance.instance_exists(self.mcio_dir, dst_location):
                dst_dir = instance.get_saves_dir(
                    mcio_dir=self.mcio_dir, instance_name=dst_location
                )
            else:
                raise ValueError(f"Invalid dst instance: {dst_location}")

        # Use source world name if destination name not specified
        dst_world = dst_world or src_world

        # Validate destination world doesn't exist
        if (dst_dir / dst_world).exists():
            raise ValueError(f"Dst world already exists: {dst_world}")

        util.copy_dir(src_dir / src_world, dst_dir / dst_world)

    def world_exists(
        self, location: LocationType, world_name: config.WorldName
    ) -> bool:
        if location == STORAGE_LOCATION:
            loc_dir = self.mcio_dir / WorldManager.WORLD_STORAGE_SUBDIR
        else:
            if instance.instance_exists(self.mcio_dir, location):
                loc_dir = instance.get_saves_dir(self.mcio_dir, location)
            else:
                return False
        return (loc_dir / world_name).exists()
