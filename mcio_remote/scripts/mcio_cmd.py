import argparse
import logging
import pprint
import textwrap
from pathlib import Path
from typing import Any, Final, Protocol

from mcio_remote import config, instance, mcio_gui, types, util, world

LOG = logging.getLogger(__name__)


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
        print(f"Showing information for MCio directory: {mcio_dir}\n")
        with config.ConfigManager(mcio_dir) as cm:
            print(cm.pformat())


class WorldCmd(Cmd):
    CMD = "world"

    def run(self, args: argparse.Namespace) -> None:
        wm = world.WorldManager(mcio_dir=args.mcio_dir)
        if args.world_command == "cp":
            wm.copy_cmd(args.src, args.dst)
        elif args.world_command == "create":
            wm.create(
                args.world_name, args.version, seed=args.seed, gamemode=args.gamemode
            )
        elif args.world_command == "rm":
            wm.delete_cmd(args.world_location)

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        """Add the world command subparser"""
        world_parser = parent_subparsers.add_parser("world", help="World management")
        world_subparsers = world_parser.add_subparsers(
            dest="world_command", metavar="world-command", required=True
        )

        create_parser = world_subparsers.add_parser(
            "create", help="Create world and save it to storage"
        )
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
        create_parser.add_argument(
            "--gamemode",
            "-g",
            type=str,
            choices=["survival", "creative", "hardcore", "spectator"],
            default="survival",
            help="Game mode (default: survival)",
        )

        cp_parser = world_subparsers.add_parser(
            "cp", help="Copy a world", formatter_class=argparse.RawTextHelpFormatter
        )
        _add_mcio_dir_arg(cp_parser)
        cp_parser.add_argument(
            "src",
            type=str,
            help="Source world (storage:<world-name> or <instance-name>:<world-name>)",
        )
        cp_parser.add_argument(
            "dst",
            type=str,
            help=(
                "Dest location (storage:<world-name> or <instance-name>:<world-name>)\n"
                "If world-name is omitted, uses the source world-name"
            ),
        )

        rm_parser = world_subparsers.add_parser("rm", help="Delete a world")
        rm_parser.add_argument(
            "world_location",
            metavar="world-location",
            type=str,
            help="storage:<world-name> or <instance-name>:<world-name>",
        )
        _add_mcio_dir_arg(rm_parser)


class GuiCmd(Cmd):
    CMD = "gui"

    def run(self, args: argparse.Namespace) -> None:
        gui = mcio_gui.MCioGUI(
            scale=args.scale,
            fps=args.fps,
            action_port=args.action_port,
            observation_port=args.observation_port,
        )
        gui.run()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        """Add the gui command subparser"""
        gui_parser = parent_subparsers.add_parser(
            "gui",
            help="Launch human interface to Minecraft MCio",
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
        gui_parser.add_argument(
            "--action-port",
            type=int,
            default=types.DEFAULT_ACTION_PORT,
            help=f"Port for the action connection. Default {types.DEFAULT_ACTION_PORT}",
        )
        gui_parser.add_argument(
            "--observation-port",
            type=int,
            default=types.DEFAULT_OBSERVATION_PORT,
            help=f"Port for the observation connection. Default {types.DEFAULT_OBSERVATION_PORT}",
        )


class InstanceLaunchCmd(Cmd):
    CMD = "launch"

    def run(self, args: argparse.Namespace) -> None:
        opts = types.RunOptions(
            instance_name=args.instance_name,
            width=args.width,
            height=args.height,
            mcio_mode=args.mcio_mode,
            hide_window=args.hide_window,
            action_port=args.action_port,
            observation_port=args.observation_port,
            mcio_dir=args.mcio_dir,
            mc_username=args.username,
            world_name=args.world,
            java_path=args.java,
        )
        launch = instance.Launcher(opts)
        if args.list:
            cmd = launch.get_show_command()
            pprint.pprint(cmd)
        elif args.str:
            cmd = launch.get_show_command()
            print(" ".join(cmd))
        else:
            launch.launch(wait=True)

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        launch_parser = parent_subparsers.add_parser("launch", help="Launch instance")
        launch_parser.add_argument(
            "instance_name",
            metavar="instance-name",
            type=str,
            help="Name of the Minecraft instance",
        )
        launch_parser.add_argument(
            "--mcio-mode",
            "-m",
            type=str,
            choices=[str(x) for x in types.MCioMode],
            default=types.DEFAULT_MCIO_MODE,
            help=f"MCio mode: (default: {types.DEFAULT_MCIO_MODE})",
        )
        _add_mcio_dir_arg(launch_parser)
        launch_parser.add_argument("--world", "-w", type=str, help="World name")
        launch_parser.add_argument(
            "--width",
            "-W",
            type=int,
            default=types.DEFAULT_WINDOW_WIDTH,
            help=f"Window width (default: {types.DEFAULT_WINDOW_WIDTH})",
        )
        launch_parser.add_argument(
            "--height",
            "-H",
            type=int,
            default=types.DEFAULT_WINDOW_HEIGHT,
            help=f"Window height (default: {types.DEFAULT_WINDOW_HEIGHT})",
        )

        launch_parser.add_argument(
            "--hide-window",
            action="store_true",
            default=types.DEFAULT_HIDE_WINDOW,
            help=f"Hide Minecraft window (default: {types.DEFAULT_HIDE_WINDOW})",
        )

        launch_parser.add_argument(
            "--username",
            "-u",
            type=str,
            default=types.DEFAULT_MINECRAFT_USER,
            help=f"Player name (default: {types.DEFAULT_MINECRAFT_USER})",
        )
        launch_parser.add_argument(
            "--java",
            "-j",
            type=str,
            help="Path to java executable (defaults to Mojang's java installed with the instance)",
        )
        launch_parser.add_argument(
            "--action-port",
            type=int,
            default=types.DEFAULT_ACTION_PORT,
            help=f"Port for the action connection. Default {types.DEFAULT_ACTION_PORT}",
        )
        launch_parser.add_argument(
            "--observation-port",
            type=int,
            default=types.DEFAULT_OBSERVATION_PORT,
            help=f"Port for the observation connection. Default {types.DEFAULT_OBSERVATION_PORT}",
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


class InstanceInstallCmd(Cmd):
    CMD = "install"

    def run(self, args: argparse.Namespace) -> None:
        installer = instance.Installer(
            args.instance_name,
            args.mcio_dir,
            mc_version=args.version,
            java_path=args.java,
        )
        installer.install()

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        install_parser = parent_subparsers.add_parser(
            "install", help="Install instance"
        )
        install_parser.add_argument(
            "instance_name",
            metavar="instance-name",
            type=str,
            help="Name of the Minecraft instance",
        )
        _add_mcio_dir_arg(install_parser)
        install_parser.add_argument(
            "--version",
            "-v",
            type=str,
            default=config.DEFAULT_MINECRAFT_VERSION,
            help=f"Minecraft version to install (default: {config.DEFAULT_MINECRAFT_VERSION})",
        )
        install_parser.add_argument(
            "--java",
            "-j",
            type=str,
            help="Path to java executable (defaults to Mojang's java installed with the instance)",
        )


class InstanceCpCmd(Cmd):
    CMD = "cp"

    def run(self, args: argparse.Namespace) -> None:
        im = instance.InstanceManager(args.mcio_dir)
        im.copy(args.src, args.dst)

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        cp_parser = parent_subparsers.add_parser(
            "cp", help="Copy an instance", formatter_class=argparse.RawTextHelpFormatter
        )
        _add_mcio_dir_arg(cp_parser)
        cp_parser.add_argument(
            "src",
            type=str,
            help="Src instance name",
        )
        cp_parser.add_argument(
            "dst",
            type=str,
            help="Dst instance name",
        )


class InstanceRmCmd(Cmd):
    CMD = "rm"

    def run(self, args: argparse.Namespace) -> None:
        im = instance.InstanceManager(args.mcio_dir)
        im.delete(args.instance_name)

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        rm_parser = parent_subparsers.add_parser("rm", help="Delete an instance")
        rm_parser.add_argument(
            "instance_name",
            metavar="instance-name",
            type=str,
            help="Instance name",
        )
        _add_mcio_dir_arg(rm_parser)


class InstanceCmd(Cmd):
    CMD = "inst"

    def run(self, args: argparse.Namespace) -> None:
        for cmd in self.cmd_objects:
            if args.instance_command == cmd.cmd():
                cmd.run(args)
                return

    def add(self, parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
        instance_parser = parent_subparsers.add_parser(
            self.CMD, help="Minecraft instance management"
        )
        subparsers = instance_parser.add_subparsers(
            dest="instance_command", metavar="instance-command", required=True
        )

        self.cmd_objects: list[Any] = [
            InstanceInstallCmd(),
            InstanceLaunchCmd(),
            InstanceCpCmd(),
            InstanceRmCmd(),
        ]

        for cmd in self.cmd_objects:
            cmd.add(subparsers)


class DemoCmd(Cmd):
    CMD = "demo"
    inst_name: Final[str] = "DemoInstance"
    world_name: Final[str] = "DemoWorld"
    seed: Final[str] = "Hello, World!"

    def run(self, args: argparse.Namespace) -> None:
        """See 1-6 in add() for an explaination"""
        im = instance.InstanceManager(args.mcio_dir)

        # 1 and 2
        if not im.instance_exists(self.inst_name):
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

        launch: instance.Launcher | None = None
        gui: mcio_gui.MCioGUI | None = None
        try:
            # 5
            print("\nLaunching Minecraft...")
            opts = types.RunOptions(
                instance_name=self.inst_name,
                mcio_dir=args.mcio_dir,
                world_name=self.world_name,
            )
            launch = instance.Launcher(opts)
            launch.launch(wait=False)

            # 6
            print("\nStarting MCio GUI...")
            gui = mcio_gui.MCioGUI()
            gui.run(launcher=launch)  # This blocks
        except KeyboardInterrupt:
            pass
        finally:
            print("\nExiting...")
            if launch:
                launch.close()
            if gui:
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


def base_parse_args() -> tuple[argparse.Namespace, list[Any]]:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )
    util.logging_add_arg(parser)

    # Subparsers for different modes
    subparsers = parser.add_subparsers(dest="command", metavar="command", required=True)

    cmd_objects: list[Any] = [
        InstanceCmd(),
        WorldCmd(),
        ShowCmd(),
        GuiCmd(),
        DemoCmd(),
    ]

    for cmd in cmd_objects:
        cmd.add(subparsers)

    args = parser.parse_args()
    util.logging_init(args=args)
    return args, cmd_objects


def base_run(args: argparse.Namespace, cmd_objects: list[Any]) -> None:
    for cmd in cmd_objects:
        if args.command == cmd.cmd():
            cmd.run(args)
            return
    print(f"Unknown command: {args.command}")


def main() -> None:
    args, cmd_objects = base_parse_args()
    base_run(args, cmd_objects)


if __name__ == "__main__":
    main()
