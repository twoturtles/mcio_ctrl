"""Integration test fixtures for MCio.

Launches a real Minecraft instance with the MCio mod and connects over ZMQ.
On first run, auto-installs Minecraft + Fabric + mods (~minutes).
Subsequent runs reuse the existing installation.

## Config

Use env var MCIO_MOD_DIR or MCIO_MOD_JAR to copy in a development mod.

Use env var MCIO_HIDE_WINDOW=false to show the Minecraft window.

Set MCIO_INT_EXTERNAL=true to skip launching Minecraft (use an already-running instance
on ports 4011/8011).

## Basic:
uv run pytest -m integration

## More Debug:
uv run pytest -m integration --log-cli-level=INFO
Include stdout/stderr:
uv run pytest -m integration --log-cli-level=INFO -s

## Use dev mod:
MCIO_MOD_DIR=~/src/MCio/build/libs/ uv run pytest -m integration --log-cli-level=INFO

## Use external instance:
Launch Minecraft:
MCIO_MODE=sync MCIO_ACTION_PORT=4011 MCIO_OBSERVATION_PORT=8011 uv run mcio inst launch inttest -w inttest_flat -d ~/src/mcio_ctrl/.inttest --width 320 --height 240
Connect pytest:
MCIO_INT_EXTERNAL=true uv run pytest -m integration --log-cli-level=INFO
"""

import glob
import logging
import os
import shutil
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from mcio_ctrl import controller, instance, network, types, world

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Isolated mcio_dir for integration tests (lives in the repo root, gitignored)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTTEST_DIR = _PROJECT_ROOT / ".inttest"

INSTANCE_NAME = "inttest"
WORLD_NAME = "inttest_flat"
TEST_SEED = 12345

ACTION_PORT = 4011
OBSERVATION_PORT = 8011

CONNECTION_TIMEOUT = 120.0  # seconds — first launch can be slow
SETTLE_TICKS = 30  # empty exchanges to let the world stabilize

FLAT_Y = -60  # flat worlds defaults to y = -60
FRAME_SHAPE = (240, 320, 3)  # (H, W, C)


# ---------------------------------------------------------------------------
# IntegrationController — ControllerSync with convenience methods for tests
# ---------------------------------------------------------------------------


class IntegrationController(controller.ControllerSync):
    """ControllerSync with extra convenience methods for integration tests."""

    def send_and_recv(
        self, action: network.ActionPacket | None = None, skip_steps: int = 0
    ) -> network.ObservationPacket:
        """Send an action (default: empty) and return the observation. Optionally skip some steps."""
        if action is None:
            action = network.ActionPacket()
        self.send_action(action)
        obs = self.recv_observation()
        if skip_steps > 0:
            obs = self.skip_steps(skip_steps)
        return obs

    def skip_steps(self, n_steps: int) -> network.ObservationPacket:
        """Send empty actions and return the final observation. Use to skip over a
        number of steps/game ticks. This is necessary after commands which often take
        many ticks to complete."""
        n_steps = max(int(n_steps), 1)
        action = network.ActionPacket()
        for _ in range(n_steps):
            self.send_action(action)
            obs = self.recv_observation()
        return obs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_external() -> bool:
    """Check if we should use an externally-launched Minecraft instance."""
    return os.environ.get("MCIO_INT_EXTERNAL", "").lower() in ("1", "true")


def _ensure_installed() -> None:
    """Install Minecraft + Fabric + mods if the instance doesn't exist yet."""
    im = instance.InstanceManager(mcio_dir=INTTEST_DIR)
    if im.instance_exists(INSTANCE_NAME):
        logger.info("Instance '%s' already exists — skipping install", INSTANCE_NAME)
    else:
        logger.info("Installing Minecraft instance '%s' ...", INSTANCE_NAME)
        installer = instance.Installer(INSTANCE_NAME, mcio_dir=INTTEST_DIR)
        installer.install()
        logger.info("Install complete")

    # Optionally replace the MCio mod jar with a local build
    mod_jar_path = _resolve_mod_jar()
    if mod_jar_path:
        mods_dir = im.get_instance_dir(INSTANCE_NAME) / "mods"
        # Remove any existing mcio jar(s)
        for old in glob.glob(str(mods_dir / "mcio-*.jar")):
            logger.info("Removing old mod jar: %s", old)
            os.remove(old)

        dst = mods_dir / mod_jar_path.name
        logger.info("Copying mod jar %s -> %s", mod_jar_path, dst)
        shutil.copy2(mod_jar_path, dst)


def _resolve_mod_jar() -> Path | None:
    """Resolve MCIO_MOD_JAR or MCIO_MOD_DIR to a jar path, or None."""
    mod_jar = os.environ.get("MCIO_MOD_JAR")
    mod_dir = os.environ.get("MCIO_MOD_DIR")

    if mod_jar and mod_dir:
        raise ValueError("Set MCIO_MOD_JAR or MCIO_MOD_DIR, not both")

    if mod_jar:
        path = Path(mod_jar).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"MCIO_MOD_JAR not found: {path}")
        return path

    if mod_dir:
        dir_path = Path(mod_dir).expanduser().resolve()
        if not dir_path.is_dir():
            raise NotADirectoryError(f"MCIO_MOD_DIR not found: {dir_path}")
        # Find mcio jars, excluding -sources
        candidates = [
            p for p in dir_path.glob("mcio-*.jar") if "-sources" not in p.name
        ]
        if not candidates:
            raise FileNotFoundError(f"No mcio-*.jar found in MCIO_MOD_DIR: {dir_path}")
        # Pick the most recently modified
        best = max(candidates, key=lambda p: p.stat().st_mtime)
        logger.info("Resolved MCIO_MOD_DIR to %s", best)
        return best

    return None


def _ensure_world_exists() -> None:
    """Create the flat test world in storage + copy to instance if needed."""
    wm = world.WorldManager(mcio_dir=INTTEST_DIR)

    # Create in storage if missing
    if not wm.world_exists("storage", WORLD_NAME):
        logger.info("Creating world '%s' in storage ...", WORLD_NAME)
        wm.create(
            WORLD_NAME,
            gamemode="creative",
            seed=TEST_SEED,
            server_properties={"level-type": "minecraft:flat"},
        )
        logger.info("World created")

    # Copy to instance if missing
    if not wm.world_exists(INSTANCE_NAME, WORLD_NAME):
        logger.info(
            "Copying world '%s' to instance '%s' ...", WORLD_NAME, INSTANCE_NAME
        )
        wm.copy(
            src_location="storage",
            src_world=WORLD_NAME,
            dst_location=INSTANCE_NAME,
            dst_world=WORLD_NAME,
        )
        logger.info("World copied")


def get_test_run_options(launch: bool = True) -> types.RunOptions:
    """Get RunOptions configured for testing"""
    hide_window = os.environ.get("MCIO_HIDE_WINDOW", "true").lower() in (
        "true",
        "1",
    )
    run_options = types.RunOptions(
        instance_name=INSTANCE_NAME if launch else None,
        world_name=WORLD_NAME,
        mcio_dir=INTTEST_DIR,
        height=FRAME_SHAPE[0],
        width=FRAME_SHAPE[1],
        mcio_mode=types.MCioMode.SYNC,
        hide_window=hide_window,
        action_port=ACTION_PORT,
        observation_port=OBSERVATION_PORT,
    )
    return run_options


# ---------------------------------------------------------------------------
# Session-scoped fixture: one Minecraft launch for the entire test run
# ---------------------------------------------------------------------------


# pytest yield fixture
@pytest.fixture(scope="session")
def minecraft_session() -> Generator[None, None, None]:
    """Launch Minecraft for the test session.

    If MCIO_INT_EXTERNAL=true, skips launch/shutdown (assumes an instance is already
    running on ports 4011/8011).
    """
    if _is_external():
        logger.info("MCIO_INT_EXTERNAL set — using externally-launched instance")
        yield
        return

    _ensure_installed()
    _ensure_world_exists()

    run_options = get_test_run_options()
    launcher = instance.Launcher(run_options)
    launcher.launch(wait=False)
    logger.info("Minecraft launched")

    yield

    # Teardown: connect briefly to send stop, then close launcher
    try:
        stop_ctrl = controller.ControllerSync(
            action_port=ACTION_PORT,
            observation_port=OBSERVATION_PORT,
            wait_for_connection=True,
            connection_timeout=10.0,
        )
        stop_ctrl.send_stop()
        stop_ctrl.close()
    except Exception:
        pass
    time.sleep(2)
    launcher.close()
    logger.info("Minecraft shut down")


# ---------------------------------------------------------------------------
# Function-scoped fixture: fresh controller per test
# ---------------------------------------------------------------------------


# pytest yield fixture
@pytest.fixture(scope="function")
def ctrl(minecraft_session: None) -> Generator[IntegrationController, None, None]:
    """Connect a fresh IntegrationController for each test, with clear_input."""
    c = IntegrationController(
        action_port=ACTION_PORT,
        observation_port=OBSERVATION_PORT,
        wait_for_connection=True,
        connection_timeout=CONNECTION_TIMEOUT,
    )
    logger.info("Controller connected")

    # Clear residual input
    # c.send_and_recv(network.ActionPacket(clear_input=True))

    yield c

    c.close()
    logger.info("Controller closed")
