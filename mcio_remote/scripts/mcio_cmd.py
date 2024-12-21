import argparse
import pprint
import typing
from typing import Any
from pathlib import Path

from mcio_remote import instance
from mcio_remote import config
from mcio_remote import world


def _add_mcio_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mcio-dir",
        "-d",
        type=str,
        default=config.DEFAULT_MCIO_DIR,
        help=f"MCio data directory (default: {config.DEFAULT_MCIO_DIR})",
    )


def show(mcio_dir: Path | str) -> None:
    mcio_dir = Path(mcio_dir).expanduser()
    print(f"Showing information for MCio directory: {mcio_dir}")
    with config.ConfigManager(mcio_dir) as cm:
        print("\nInstances:")
        for inst_id, inst_cfg in cm.config.instances.items():
            print(f"  {inst_id}: mc_version={inst_cfg.minecraft_version}")
            saves_dir = instance.get_saves_dir(mcio_dir, inst_id)
            print("    Worlds:")
            for world_path in saves_dir.iterdir():
                print(f"      {world_path.name}")

        print("\nWorld Storage:")
        for world_name, world_cfg in cm.config.world_storage.items():
            print(
                f"  {world_name}: mc_version={world_cfg.minecraft_version} seed={world_cfg.seed}"
            )

        print()


# Unfortunately, argparse is not set up for type hints
def add_world_command(parent_subparsers: "argparse._SubParsersAction[Any]") -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )

    # Subparsers for different modes
    subparsers = parser.add_subparsers(dest="command", metavar="command", required=True)

    ##
    # Install subparser
    install_parser = subparsers.add_parser("install", help="Install Minecraft")
    install_parser.add_argument(
        "instance_id",
        metavar="instance-id",
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

    ##
    # Launch subparser
    launch_parser = subparsers.add_parser("launch", help="Launch Minecraft")
    launch_parser.add_argument(
        "instance_id",
        metavar="instance-id",
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

    ##
    # World subparser
    add_world_command(subparsers)

    ##
    # Show subparser
    show_parser = subparsers.add_parser(
        "show", help="Show information about what is installed"
    )
    _add_mcio_dir_arg(show_parser)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "install":
        installer = instance.Installer(args.instance_id, args.mcio_dir, args.version)
        installer.install()
    elif args.command == "launch":
        launch = instance.Launcher(
            args.instance_id,
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
    elif args.command == "world":
        if args.world_command == "cp":
            wrld = world.World(mcio_dir=args.mcio_dir)
            wrld.copy(args.src, args.dst)
        elif args.world_command == "create":
            wrld = world.World(mcio_dir=args.mcio_dir)
            wrld.create(args.world_name, args.version, seed=args.seed)
    elif args.command == "show":
        show(args.mcio_dir)
    else:
        print(f"Unknown mode: {args.command_mode}")


if __name__ == "__main__":
    main()
