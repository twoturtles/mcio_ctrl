import argparse
import pprint
import typing

from mcio_remote import launcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minecraft Instance Manager and Launcher"
    )

    # Subparsers for different modes
    subparsers = parser.add_subparsers(
        dest="command_mode", metavar="command-mode", required=True
    )

    def _add_mcio_dir_arg(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--mcio-dir",
            "-d",
            type=str,
            default=launcher.DEFAULT_MCIO_DIR,
            help=f"MCio data directory (default: {launcher.DEFAULT_MCIO_DIR})",
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
        default=launcher.DEFAULT_MINECRAFT_VERSION,
        help=f"Minecraft version to install (default: {launcher.DEFAULT_MINECRAFT_VERSION})",
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
        choices=typing.get_args(launcher.MCIO_MODE),
        default="async",
        help="MCio mode: (default: async)",
    )
    _add_mcio_dir_arg(launch_parser)
    launch_parser.add_argument("--world", "-w", type=str, help="World name")
    launch_parser.add_argument(
        "--width",
        "-W",
        type=int,
        default=launcher.DEFAULT_WINDOW_WIDTH,
        help=f"Window width (default: {launcher.DEFAULT_WINDOW_WIDTH})",
    )
    launch_parser.add_argument(
        "--height",
        "-H",
        type=int,
        default=launcher.DEFAULT_WINDOW_HEIGHT,
        help=f"Window height (default: {launcher.DEFAULT_WINDOW_HEIGHT})",
    )
    launch_parser.add_argument(
        "--username",
        "-u",
        type=str,
        default=launcher.DEFAULT_MINECRAFT_USER,
        help=f"Player name (default: {launcher.DEFAULT_MINECRAFT_USER})",
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
    # Show subparser
    show_parser = subparsers.add_parser(
        "show", help="Show information about what is installed"
    )
    _add_mcio_dir_arg(show_parser)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command_mode == "install":
        installer = launcher.Installer(args.instance_id, args.mcio_dir, args.version)
        installer.install()
    elif args.command_mode == "launch":
        launch = launcher.Launcher(
            args.instance_id,
            mcio_dir=args.mcio_dir,
            mc_username=args.username,
            world=args.world,
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
    elif args.command_mode == "show":
        launcher.show(mcio_dir=args.mcio_dir)
    else:
        print(f"Unknown mode: {args.command_mode}")


if __name__ == "__main__":
    main()
