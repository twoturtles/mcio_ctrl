"""Game state observation tests (health, position, orientation)."""

import pytest

from .conftest import ControllerHolder, send_and_recv


@pytest.mark.integration
def test_health(ctrl: ControllerHolder) -> None:
    """In creative mode, health should be full (20.0)."""
    obs = send_and_recv(ctrl)
    assert obs.health == 20.0


@pytest.mark.integration
def test_player_position(ctrl: ControllerHolder) -> None:
    """On a flat world the Y coordinate should be around 64-70."""
    obs = send_and_recv(ctrl)
    x, y, z = obs.player_pos
    assert -1_000_000 < x < 1_000_000
    assert 50 < y < 80, f"Unexpected Y={y} for flat world"
    assert -1_000_000 < z < 1_000_000


@pytest.mark.integration
def test_player_orientation(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    assert -90.0 <= obs.player_pitch <= 90.0
    assert -180.0 <= obs.player_yaw <= 180.0
