from pathlib import Path
import random
import sys
from typing import Final, Literal

from . import config
from . import util
from . import instance
from . import server


class World:

    INSTANCE_WORLDS_SUBDIR: Final[str] = "saves"
    WORLD_STORAGE: Final[str] = "world_storage"

    def __init__(
        self,
        mcio_dir: Path | str | None = None,
    ) -> None:
        mcio_dir = mcio_dir or config.DEFAULT_MCIO_DIR
        self.mcio_dir = Path(mcio_dir).expanduser()
        self.storage_dir = self.mcio_dir / self.WORLD_STORAGE

    def create(
        self,
        world_name: config.WorldName,
        mc_version: config.MinecraftVersion,
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
        svr.delete_world_dir()

        # Merge properties
        server_properties = server_properties or {}
        default_properties = {
            "gamemode": gamemode,
            "difficulty": difficulty,
            "level-seed": seed,
        }
        server_properties = default_properties | server_properties
        svr.set_server_properties(server_properties, clear=reset_server_properties)

        # After stop the world dir should be ready
        print("Starting world generation...\n")
        svr.run()
        svr.stop()

        # Copy world to storage
        util.copy_dir(svr.server_world_dir, dst_dir)

        with config.ConfigManager(self.mcio_dir, save=True) as cm:
            cm.config.world_storage[world_name] = config.WorldConfig(
                name=world_name, minecraft_version=mc_version, seed=seed
            )

        print(f"\nDone: World saved to storage: {dst_dir}")

    def _src_split(self, loc_world: str) -> tuple[Path, str]:
        loc, world = loc_world.split(":", 1)

        # Validate loc
        if loc == "storage":
            loc_dir = self.storage_dir
        else:
            if instance.instance_exists(self.mcio_dir, loc):
                inst_dir = instance.get_instance_dir(self.mcio_dir, loc)
                loc_dir = instance.get_saves_dir(inst_dir)
            else:
                raise ValueError(f"Invalid instance: {loc}")

        # Validate world
        if not (loc_dir / world).exists():
            raise ValueError(f"World does not exist: {loc_world}")

        return loc_dir, world

    def _dst_split(self, loc_world: str, src_world: str) -> tuple[Path, str]:
        loc, world = loc_world.split(":", 1)

        # Validate loc
        if loc == "storage":
            loc_dir = self.storage_dir
        else:
            if instance.instance_exists(self.mcio_dir, loc):
                inst_dir = instance.get_instance_dir(self.mcio_dir, loc)
                loc_dir = instance.get_saves_dir(inst_dir)
            else:
                raise ValueError(f"Invalid instance: {loc}")

        # Validate world
        if world == "":
            world = src_world
        if (loc_dir / world).exists():
            raise ValueError(f"World already exists: {loc_world}")

        return loc_dir, world

    def copy(self, src: str, dst: str) -> None:
        src_dir, src_world = self._src_split(src)
        dst_dir, dst_world = self._dst_split(dst, src_world)
        print(src_dir, src_world, dst_dir, dst_world)

    def copy_from_storage_to_instance(
        self,
        src_name: config.WorldName,
        dst_instance_id: config.InstanceID,
        dst_name: config.WorldName | None = None,
        overwrite: bool = False,
    ) -> None:
        dst_name = dst_name or src_name
        dst_instance_dir = instance.get_instance_dir(self.mcio_dir, dst_instance_id)
        util.copy_dir(
            self.storage_dir / src_name,
            dst_instance_dir / dst_name,
            overwrite=overwrite,
        )

    def copy_from_instance_to_storage(
        self,
        src_instance_id: config.InstanceID,
        src_name: config.WorldName,
        dst_name: config.WorldName | None = None,
        overwrite: bool = False,
    ) -> None:
        dst_name = dst_name or src_name
        src_instance_dir = instance.get_instance_dir(self.mcio_dir, src_instance_id)
        util.copy_dir(
            src_instance_dir / src_name,
            self.storage_dir / dst_name,
            overwrite=overwrite,
        )
