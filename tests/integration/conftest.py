"""Integration test fixtures for MCio.

Launches a real Minecraft instance with the MCio mod and connects over ZMQ.
On first run, auto-installs Minecraft + Fabric + mods (~minutes).
Subsequent runs reuse the existing installation.

Use env var MCIO_MOD_DIR or MCIO_MOD_JAR to copy in a development mod.

Basic:
uv run pytest -m integration

More Debug:
uv run pytest -m integration --log-cli-level=INFO
Include stdout/stderr:
uv run pytest -m integration --log-cli-level=INFO -s

Use dev mod:
MCIO_MOD_DIR=~/src/MCio/build/libs/ uv run pytest -m integration --log-cli-level=INFO

Use env var MCIO_HIDE_WINDOW=false to show the Minecraft window.
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
# ControllerHolder — mutable wrapper so reconnect tests can swap the inner ctrl
# ---------------------------------------------------------------------------


class ControllerHolder:
    """Mutable wrapper around ControllerSync.

    The reconnect test can replace ``self.ctrl`` without breaking fixtures
    that hold a reference to the holder.
    """

    def __init__(self, ctrl: controller.ControllerSync) -> None:
        self.ctrl = ctrl

    def send_action(self, action: network.ActionPacket) -> None:
        self.ctrl.send_action(action)

    def recv_observation(self) -> network.ObservationPacket:
        return self.ctrl.recv_observation()

    def send_stop(self) -> None:
        self.ctrl.send_stop()

    def close(self) -> None:
        self.ctrl.close()

    def send_and_recv(
        self, action: network.ActionPacket | None = None, skip_steps: int = 0
    ) -> network.ObservationPacket:
        """Send an action (default: empty) and return the observation. Optionally skip some steps."""
        if action is None:
            action = network.ActionPacket()
        self.send_action(action)
        obs = self.recv_observation()
        obs = self.skip_steps(skip_steps) if skip_steps > 0 else obs
        return obs

    def skip_steps(self, skip_steps: int) -> network.ObservationPacket:
        """Send empty actions and return the final observation. Use to skip over a
        number of steps/game ticks. This is necessary after commands which often take
        many ticks to complete."""
        skip_steps = max(int(skip_steps), 1)
        action = network.ActionPacket()
        for i in range(skip_steps):
            self.send_action(action)
            obs = self.recv_observation()
        return obs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Session-scoped fixture: one Minecraft launch for the entire test run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def minecraft_session() -> Generator[ControllerHolder, None, None]:
    """Launch Minecraft, connect, and yield a ControllerHolder.

    The instance is installed automatically on first run.
    """
    _ensure_installed()
    _ensure_world_exists()
    hide_window = os.environ.get("MCIO_HIDE_WINDOW", "true").lower() in (
        "true",
        "1",
    )

    run_options = types.RunOptions(
        instance_name=INSTANCE_NAME,
        world_name=WORLD_NAME,
        mcio_dir=INTTEST_DIR,
        height=FRAME_SHAPE[0],
        width=FRAME_SHAPE[1],
        mcio_mode=types.MCioMode.SYNC,
        hide_window=hide_window,
        action_port=ACTION_PORT,
        observation_port=OBSERVATION_PORT,
    )

    launcher = instance.Launcher(run_options)
    launcher.launch(wait=False)
    logger.info("Minecraft launched — waiting for connection ...")

    try:
        ctrl = controller.ControllerSync(
            action_port=ACTION_PORT,
            observation_port=OBSERVATION_PORT,
            wait_for_connection=True,
            connection_timeout=CONNECTION_TIMEOUT,
        )
        logger.info("Connected to Minecraft")

        # Clear any residual input and grab the initial observation
        action = network.ActionPacket(clear_input=True)
        ctrl.send_action(action)
        obs = ctrl.recv_observation()
        assert obs.mode == types.MCioMode.SYNC, f"Expected SYNC mode, got {obs.mode}"
        logger.info("Initial observation received — mode=%s", obs.mode)

        holder = ControllerHolder(ctrl)

        # Let the world settle
        holder.skip_steps(SETTLE_TICKS)

        yield holder

    finally:
        # Teardown: stop Minecraft cleanly
        try:
            ctrl.send_stop()
        except Exception:
            pass
        try:
            ctrl.close()
        except Exception:
            pass
        # Give MC a moment to exit, then force-kill
        time.sleep(2)
        launcher.close()
        logger.info("Minecraft shut down")


@pytest.fixture(scope="function")
def ctrl(minecraft_session: ControllerHolder) -> ControllerHolder:
    """Convenience alias — yields the session-scoped ControllerHolder."""
    return minecraft_session
