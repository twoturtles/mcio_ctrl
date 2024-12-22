import argparse
import pprint
import typing
from typing import Any, Protocol, Final
from pathlib import Path
import textwrap

from mcio_remote import instance
from mcio_remote import config
from mcio_remote import world
from mcio_remote import mcio_gui


def _add_mcio_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mcio-dir",
        "-d",
        type=str,
        default=config.DEFAULT_MCIO_DIR,
        help=f"MCio data directory (default: {config.DEFAULT_MCIO_DIR})",
    )


class Cmd(Protocol):
    CMD: str

    def cmd(self) -> str:
        return self.CMD

    def run(self, args: argparse.Namespace) -> None: ...
    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None: ...


class ShowCmd(Cmd):
    CMD = "show"

    # Unfortunately, argparse is not set up for type hints
    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        show_parser = parent_subparsers.add_parser(
            self.CMD, help="Show information about what is installed"
        )
        _add_mcio_dir_arg(show_parser)

    def run(self, args: argparse.Namespace) -> None:
        self.show(args.mcio_dir)

    def show(self, mcio_dir: Path | str) -> None:
        mcio_dir = Path(mcio_dir).expanduser()
        print(f"Showing information for MCio directory: {mcio_dir}")
        with config.ConfigManager(mcio_dir) as cm:
            print("\nInstances:")
            for inst_name, inst_cfg in cm.config.instances.items():
                print(f"  {inst_name}: mc_version={inst_cfg.minecraft_version}")
                saves_dir = instance.get_saves_dir(mcio_dir, inst_name)
                if saves_dir.exists():
                    print("    Worlds:")
                    for world_path in saves_dir.iterdir():
                        print(f"      {inst_name}:{world_path.name}")

            print("\nWorld Storage:")
            for world_name, world_cfg in cm.config.world_storage.items():
                print(
                    f"  {world.STORAGE_LOCATION}:{world_name}: mc_version={world_cfg.minecraft_version} seed={world_cfg.seed}"
                )

            print()


class WorldCmd(Cmd):
    CMD = "world"

    def run(self, args: argparse.Namespace) -> None:
        wm = world.WorldManager(mcio_dir=args.mcio_dir)
        if args.world_command == "cp":
            wm.copy_cmd(args.src, args.dst)
        elif args.world_command == "create":
            wm.create(args.world_name, args.version, seed=args.seed)

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        """Add the world command subparser"""
        world_parser = parent_subparsers.add_parser("world", help="World management")
        world_subparsers = world_parser.add_subparsers(
            dest="world_command", metavar="world-command", required=True
        )

        create_parser = world_subparsers.add_parser("create", help="Create a new world")
        create_parser.add_argument(
            "world_name",
            metavar="world-name",
            type=str,
            help="Name of the world",
        )
        _add_mcio_dir_arg(create_parser)
        create_parser.add_argument(
            "--version",
            "-v",
            type=str,
            default=config.DEFAULT_MINECRAFT_VERSION,
            help=f"World's Minecraft version (default: {config.DEFAULT_MINECRAFT_VERSION})",
        )
        create_parser.add_argument(
            "--seed",
            "-s",
            type=str,
            help="Set the world's seed (default is a random seed)",
        )

        cp_parser = world_subparsers.add_parser("cp", help="Copy a world")
        _add_mcio_dir_arg(cp_parser)
        cp_parser.add_argument(
            "src",
            type=str,
            help="Source world (storage:<world-name> or <instance-name>:<world-name>)",
        )
        cp_parser.add_argument(
            "dst",
            type=str,
            help="Dest world (storage:<world-name> or <instance-name>:<world-name>)",
        )


class GuiCmd(Cmd):
    CMD = "gui"

    def run(self, args: argparse.Namespace) -> None:
        gui = mcio_gui.MCioGUI(scale=args.scale, fps=args.fps)
        gui.run()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        """Add the gui command subparser"""
        gui_parser = parent_subparsers.add_parser(
            "gui",
            help="Launch demo GUI",
            description=textwrap.dedent(
                """
                Provides a human GUI to MCio.
                Q to quit.
                """
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        gui_parser.add_argument(
            "--scale",
            type=float,
            default=1.0,
            help="Window scale factor",
        )
        gui_parser.add_argument("--fps", type=int, default=60, help="Set fps limit")


class LaunchCmd(Cmd):
    CMD = "launch"

    def run(self, args: argparse.Namespace) -> None:
        launch = instance.Launcher(
            args.instance_name,
            mcio_dir=args.mcio_dir,
            mc_username=args.username,
            world_name=args.world,
            width=args.width,
            height=args.height,
            mcio_mode=args.mcio_mode,
        )
        if args.list:
            cmd = launch.get_show_command()
            pprint.pprint(cmd)
        elif args.str:
            cmd = launch.get_show_command()
            print(" ".join(cmd))
        else:
            launch.launch()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        launch_parser = parent_subparsers.add_parser("launch", help="Launch Minecraft")
        launch_parser.add_argument(
            "instance_name",
            metavar="instance-name",
            type=str,
            help="ID/Name of the Minecraft instance",
        )
        launch_parser.add_argument(
            "--mcio_mode",
            "-m",
            metavar="mcio-mode",
            type=str,
            choices=typing.get_args(instance.McioMode),
            default="async",
            help="MCio mode: (default: async)",
        )
        _add_mcio_dir_arg(launch_parser)
        launch_parser.add_argument("--world", "-w", type=str, help="World name")
        launch_parser.add_argument(
            "--width",
            "-W",
            type=int,
            default=instance.DEFAULT_WINDOW_WIDTH,
            help=f"Window width (default: {instance.DEFAULT_WINDOW_WIDTH})",
        )
        launch_parser.add_argument(
            "--height",
            "-H",
            type=int,
            default=instance.DEFAULT_WINDOW_HEIGHT,
            help=f"Window height (default: {instance.DEFAULT_WINDOW_HEIGHT})",
        )
        launch_parser.add_argument(
            "--username",
            "-u",
            type=str,
            default=instance.DEFAULT_MINECRAFT_USER,
            help=f"Player name (default: {instance.DEFAULT_MINECRAFT_USER})",
        )

        launch_group = launch_parser.add_mutually_exclusive_group()
        launch_group.add_argument(
            "--list",
            action="store_true",
            default=False,
            help="Don't run the command; print it as a list",
        )
        launch_group.add_argument(
            "--str",
            action="store_true",
            default=False,
            help="Don't run the command; print it as a string",
        )


class InstallCmd(Cmd):
    CMD = "install"

    def run(self, args: argparse.Namespace) -> None:
        installer = instance.Installer(args.instance_name, args.mcio_dir, args.version)
        installer.install()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        install_parser = parent_subparsers.add_parser(
            "install", help="Install Minecraft"
        )
        install_parser.add_argument(
            "instance_name",
            metavar="instance-name",
            type=str,
            help="ID/Name of the Minecraft instance",
        )
        _add_mcio_dir_arg(install_parser)
        install_parser.add_argument(
            "--version",
            "-v",
            type=str,
            default=config.DEFAULT_MINECRAFT_VERSION,
            help=f"Minecraft version to install (default: {config.DEFAULT_MINECRAFT_VERSION})",
        )


class DemoCmd(Cmd):
    CMD = "demo"
    inst_name: Final[str] = "DemoInstance"
    world_name: Final[str] = "DemoWorld"
    seed: Final[str] = "Hello, World!"

    def run(self, args: argparse.Namespace) -> None:
        """See 1-6 in add() for an explaination"""

        # 1 and 2
        if not instance.instance_exists(args.mcio_dir, self.inst_name):
            print("Installing Minecraft...")
            installer = instance.Installer(self.inst_name, mcio_dir=args.mcio_dir)
            installer.install()

        # 3
        wm = world.WorldManager(mcio_dir=args.mcio_dir)
        if not wm.world_exists(world.STORAGE_LOCATION, self.world_name):
            print("\nCreating world...")
            with config.ConfigManager(args.mcio_dir, save=True) as cm:
                cm.config.world_storage
            wm.create(self.world_name, seed=self.seed)

        # 4
        if not wm.world_exists(self.inst_name, self.world_name):
            wm.copy(world.STORAGE_LOCATION, self.world_name, self.inst_name)

        try:
            # 5
            print("\nLaunching Minecraft...")
            launch = instance.Launcher(
                self.inst_name, mcio_dir=args.mcio_dir, world_name=self.world_name
            )
            launch.launch(wait=False)

            # 6
            print("\nStarting MCio GUI...")
            gui = mcio_gui.MCioGUI()
            gui.run(launcher=launch)  # This blocks
        except KeyboardInterrupt:
            pass
        finally:
            print("\nExiting...")
            launch.close()
            gui.close()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        demo_parser = parent_subparsers.add_parser(
            "demo",
            help="Run the demo",
            description=textwrap.dedent(
                f"""
                1. Installs Minecraft instance called {self.inst_name} in <mcio-dir>
                2. Installs Fabric, fabric-api, and MCio in {self.inst_name}
                3. Creates a world called {self.world_name} in world storage
                4. Copies {self.world_name} into {self.inst_name}
                5. Launches Minecraft with {self.inst_name} and {self.world_name}
                6. Starts the MCio demo GUI

                Two windows will open - one for Minecraft and one for the MCio GUI.

                Note: This is meant to be run on your local machine, not a headless server.
                """
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        _add_mcio_dir_arg(demo_parser)


def parse_args() -> tuple[argparse.Namespace, list[Any]]:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )

    # Subparsers for different modes
    subparsers = parser.add_subparsers(dest="command", metavar="command", required=True)

    cmd_objects: list[Any] = [
        InstallCmd(),
        LaunchCmd(),
        WorldCmd(),
        GuiCmd(),
        ShowCmd(),
        DemoCmd(),
    ]

    for cmd in cmd_objects:
        cmd.add(subparsers)

    return parser.parse_args(), cmd_objects


def main() -> None:
    args, cmd_objects = parse_args()
    for cmd in cmd_objects:
        if args.command == cmd.cmd():
            cmd.run(args)
            return
    print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
