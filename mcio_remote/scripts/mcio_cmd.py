import argparse
import pprint
import typing

from mcio_remote import instance
from mcio_remote import config
from mcio_remote import world


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )

    # Subparsers for different modes
    subparsers = parser.add_subparsers(dest="command", metavar="command", required=True)

    def _add_mcio_dir_arg(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--mcio-dir",
            "-d",
            type=str,
            default=config.DEFAULT_MCIO_DIR,
            help=f"MCio data directory (default: {config.DEFAULT_MCIO_DIR})",
        )

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
    world_parser = subparsers.add_parser("world", help="World management")
    world_parser.add_argument(
        "world_name",
        metavar="world-name",
        type=str,
        help="Name of the world",
    )
    _add_mcio_dir_arg(world_parser)
    world_parser.add_argument(
        "--version",
        "-v",
        type=str,
        default=config.DEFAULT_MINECRAFT_VERSION,
        help=f"World's Minecraft version (default: {config.DEFAULT_MINECRAFT_VERSION})",
    )
    world_parser.add_argument(
        "--seed",
        "-s",
        type=str,
        help="Set the world's seed (default is a random seed)",
    )

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
        wrld = world.World(mcio_dir=args.mcio_dir)
        wrld.generate(args.world_name, args.version, seed=args.seed)
    elif args.command == "show":
        instance.show(mcio_dir=args.mcio_dir)
    else:
        print(f"Unknown mode: {args.command_mode}")


if __name__ == "__main__":
    main()
