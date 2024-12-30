from pathlib import Path

import pytest

import minecraft_launcher_lib
from mcio_remote import config
from mcio_remote.scripts import mcio_cmd


INST_NAME = "test-instance"


@pytest.fixture
def test_config(tmp_path: Path) -> Path:
    """Write test config to tmp_path dir. Returns tmp mcio_dir."""
    with config.ConfigManager(tmp_path, save=True) as cm:
        cm.config.instances[INST_NAME] = config.InstanceConfig(
            id=INST_NAME,
            launch_version="test-launch-version",
            minecraft_version="test-mc-version",
        )
    return tmp_path


def test_instance_launch_list(
    test_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the arguments
    mcio_dir = test_config
    monkeypatch.setattr(
        "sys.argv",
        [
            "mcio",  # Program name
            "inst",  # Main command
            "launch",  # Subcommand
            INST_NAME,
            "--list",  # Show command list
            "--mcio-dir",
            str(mcio_dir),  # Use temp directory
        ],
    )

    command = ["foo", "--userType", "bar"]
    monkeypatch.setattr(
        minecraft_launcher_lib.command,
        "get_minecraft_command",
        lambda *args, **kwargs: command,
    )

    # Get the parsed arguments
    args, _ = mcio_cmd.base_parse_args()

    # Create and run the launch command
    cmd = mcio_cmd.InstanceLaunchCmd()
    cmd.run(args)

    # Not actually checking anything. Just want the code to run.
