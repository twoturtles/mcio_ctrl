"""Test gymnasium envs"""

import math

import numpy as np
import pytest

from mcio_ctrl.envs import minerl_env

from .conftest import FLAT_Y, FRAME_SHAPE, get_test_run_options


def _make_env() -> minerl_env.MinerlEnv:
    """Create a MinerlEnv connected to the test instance (no launch)."""
    return minerl_env.MinerlEnv(get_test_run_options(launch=False))


@pytest.mark.integration
def test_camera_delta(minecraft_session: None) -> None:
    """Verify camera delta changes pitch and yaw correctly."""
    env = _make_env()
    try:
        # Note: tp is absolute yaw, pitch vs. camera which is Δ-pitch, Δ-yaw
        setup_commands = [
            # /tp <target> <x> <y> <z> <yaw> <pitch>
            "teleport @s ~ ~ ~ -30 50",
        ]
        obs, info = env.reset(options={"commands": setup_commands})
        obs, reward, terminated, truncated, info = env.skip_steps(25)
        assert env.last_pitch == pytest.approx(50.0, abs=1.0)
        assert env.last_yaw == pytest.approx(-30.0, abs=1.0)

        action = env.get_noop_action()
        # Delta pitch, yaw
        action["camera"] = np.array((-10, 20), dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert env.last_pitch == pytest.approx(40.0, abs=1.0)
        assert env.last_yaw == pytest.approx(-10.0, abs=1.0)
    finally:
        env.close()


@pytest.mark.integration
def test_observation_space(minecraft_session: None) -> None:
    """Verify observations match the declared observation space."""
    env = _make_env()
    try:
        obs, info = env.reset()
        env.skip_steps(5)
        assert "pov" in obs
        assert obs["pov"].shape == FRAME_SHAPE
        assert obs["pov"].dtype == np.uint8
        assert obs in env.observation_space
    finally:
        env.close()


@pytest.mark.integration
def test_noop_action_in_space(minecraft_session: None) -> None:
    """Verify get_noop_action() produces a valid action."""
    env = _make_env()
    try:
        env.reset()
        env.skip_steps(5)
        noop = env.get_noop_action()
        assert noop in env.action_space
        # Stepping with noop should work without error
        obs, reward, terminated, truncated, info = env.step(noop)
        assert obs in env.observation_space
        assert not terminated
    finally:
        env.close()


@pytest.mark.integration
def test_forward_movement(minecraft_session: None) -> None:
    """Verify pressing forward moves the player."""
    env = _make_env()
    try:
        # Face South (Positive Z)
        env.reset(options={"commands": [f"teleport @s 0 {FLAT_Y} 0 0 0"]})
        env.skip_steps(25)

        # Record starting position
        env.step(env.get_noop_action())
        assert env._last_observation_pkt is not None
        x0, y0, z0 = env._last_observation_pkt.player_pos

        # Press forward for several ticks
        action = env.get_noop_action()
        action["forward"] = np.int64(1)
        for _ in range(20):
            env.step(action)

        # Release and check
        env.step(env.get_noop_action())
        x1, y1, z1 = env._last_observation_pkt.player_pos
        dist = math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2)
        assert dist > 1.0, f"Player barely moved: dist={dist}"
    finally:
        env.close()


@pytest.mark.integration
def test_terminated(minecraft_session: None) -> None:
    """Test various termination behaviors"""
    env = _make_env()
    try:
        env.reset()
        assert not env.terminated
        env.skip_steps(5)

        # Test ESC terminates
        action = env.get_noop_action()
        action["ESC"] = np.int64(1)
        obs, reward, terminated, truncated, info = env.step(action)
        assert terminated

        # Test can't step when terminated
        action = env.get_noop_action()
        with pytest.raises(AssertionError):
            obs, reward, terminated, truncated, info = env.step(action)

        # Test reset after terminated
        env.reset()
        action = env.get_noop_action()
        obs, reward, terminated, truncated, info = env.step(action)
        assert not terminated
    finally:
        env.close()


@pytest.mark.integration
def test_dying(minecraft_session: None) -> None:
    """Test dying behavior"""
    env = _make_env()
    try:
        env.reset()

        # Send kill command
        noop = env.get_noop_action()
        obs, reward, terminated, truncated, info = env.step(
            noop, options={"commands": ["kill @s"]}
        )
        # Step to let command take effect
        for _ in range(20):
            obs, reward, terminated, truncated, info = env.step(noop)
            if terminated:
                break
        assert terminated

        # Test that _reset_terminated_hack gets us back to living
        env.reset()
        assert not env.terminated

    finally:
        env.close()
