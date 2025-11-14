import random
import sys
from pathlib import Path
from typing import Final, Literal

from nbt import nbt  # type: ignore

from . import config, instance, server, util

# STORAGE_LOCATION must equal StorageType
STORAGE_LOCATION: Final[str] = "storage"
StorageType = Literal["storage"]
LocationType = StorageType | config.InstanceName


class WorldManager:

    # XXX It might be better to make storage just a special instance
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

        # Enable commands in the world. This is disabled by default in survival worlds.
        self._nbt_config(dst_dir)

        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            cm.config.world_storage[world_name] = config.WorldConfig(
                name=world_name, minecraft_version=mc_version, seed=seed
            )

        print(f"\nDone: World saved to storage: {dst_dir}")

    def _nbt_config(self, world_dir: Path) -> None:
        """Set values in level.dat nbt file
        Enables allowCommands, doImmediateRespawn
        Disables sendCommandFeedback
        """
        level_dat = world_dir / "level.dat"
        nbt_root = nbt.NBTFile(level_dat)
        # allowCommands is a Byte used as a bool
        nbt_root["Data"]["allowCommands"].value = 1
        # doImmediateRespawn is a String used as a bool
        nbt_root["Data"]["GameRules"]["doImmediateRespawn"].value = "true"
        # sendCommandFeedback is a String used as a bool. Disable by default so
        # commands don't pollute the screen with messages.
        nbt_root["Data"]["GameRules"]["sendCommandFeedback"].value = "false"
        nbt_root.write_file()

    def delete_cmd(self, loc_world: str) -> None:
        loc, world = loc_world.split(":", 1)
        self.delete(loc, world)

    def delete(self, location: LocationType, world_name: config.WorldName) -> None:
        im = instance.InstanceManager(self.mcio_dir)
        if location == STORAGE_LOCATION:
            loc_dir = self.storage_dir
        else:
            if im.instance_exists(location):
                loc_dir = im.get_saves_dir(instance_name=location)
            else:
                raise ValueError(f"Invalid instance: {location}")
        world_dir = loc_dir / world_name

        # Just rmrf without checking it exists
        util.rmrf(world_dir)
        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            if location == STORAGE_LOCATION:
                cm.config.world_storage.pop(world_name, None)
            else:
                cm.config.instances[location].worlds.pop(world_name, None)

    def copy_cmd(self, src: str, dst: str, force: bool = False) -> None:
        """Copy world for command line interface"""
        src_loc, src_world = src.split(":", 1)
        dst_loc, dst_world = dst.split(":", 1)
        self.copy(src_loc, src_world, dst_loc, dst_world, force=force)

    def copy(
        self,
        src_location: LocationType,  # STORAGE_LOCATION or instance name
        src_world: config.WorldName,
        dst_location: LocationType,  # STORAGE_LOCATION or instance name
        dst_world: config.WorldName | None = None,  # If None, uses src_world name
        force: bool = False,
    ) -> None:
        """Copy a world between storage and instances.

        Args:
            src_location: Either STORAGE_LOCATION or an instance name for the source
            src_world: Name of the world to copy
            dst_location: Either STORAGE_LOCATION or an instance name for the destination
            dst_world: Name for the copied world. If None, uses the source world name
            force: Overwrite dst if it exists
        """
        im = instance.InstanceManager(self.mcio_dir)

        # Validate source location and get directory
        if src_location == STORAGE_LOCATION:
            src_dir = self.storage_dir
        else:
            if im.instance_exists(src_location):
                src_dir = im.get_saves_dir(instance_name=src_location)
            else:
                raise ValueError(f"Invalid src instance: {src_location}")

        # Validate source world exists
        if not (src_dir / src_world).exists():
            raise ValueError(f"Src world does not exist: {src_world}")

        # Validate destination location and get directory
        if dst_location == STORAGE_LOCATION:
            dst_dir = self.storage_dir
        else:
            if im.instance_exists(dst_location):
                dst_dir = im.get_saves_dir(instance_name=dst_location)
            else:
                raise ValueError(f"Invalid dst instance: {dst_location}")

        # Use source world name if destination name not specified
        dst_world = dst_world or src_world

        # Validate destination world doesn't exist
        if (dst_dir / dst_world).exists():
            if force:
                util.rmrf(dst_dir / dst_world)
            else:
                raise ValueError(f"Dst world already exists: {dst_world}")

        util.copy_dir(src_dir / src_world, dst_dir / dst_world)
        self._copy_update_config(src_location, src_world, dst_location, dst_world)

    def _copy_update_config(
        self,
        src_location: LocationType,
        src_world: config.WorldName,
        dst_location: LocationType,
        dst_world: config.WorldName,
    ) -> None:
        # Everything is validated at this point
        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            if src_location == STORAGE_LOCATION:
                src_config = cm.config.world_storage[src_world]
            else:
                src_config = cm.config.instances[src_location].worlds[src_world]

            dst_config = config.WorldConfig(
                name=dst_world,
                minecraft_version=src_config.minecraft_version,
                seed=src_config.seed,
            )
            if dst_location == STORAGE_LOCATION:
                cm.config.world_storage[dst_world] = dst_config
            else:
                cm.config.instances[dst_location].worlds[dst_world] = dst_config

    def world_exists(
        self, location: LocationType, world_name: config.WorldName
    ) -> bool:
        im = instance.InstanceManager(self.mcio_dir)
        if location == STORAGE_LOCATION:
            loc_dir = self.mcio_dir / WorldManager.WORLD_STORAGE_SUBDIR
        else:
            if im.instance_exists(location):
                loc_dir = im.get_saves_dir(location)
            else:
                return False
        return (loc_dir / world_name).exists()
