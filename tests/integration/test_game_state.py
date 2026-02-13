"""Game state observation tests (health, position, orientation)."""

import pytest

from .conftest import FLAT_Y, IntegrationController


@pytest.mark.integration
def test_health(ctrl: IntegrationController) -> None:
    """In creative mode, health should be full (20.0)."""
    obs = ctrl.send_and_recv()
    assert obs.health == 20.0


@pytest.mark.integration
def test_player_position(ctrl: IntegrationController) -> None:
    """On a flat world the Y coordinate should be around 64-70."""
    obs = ctrl.send_and_recv()
    x, y, z = obs.player_pos
    assert -1_000_000 < x < 1_000_000
    # flat defaults to y = -60
    assert (FLAT_Y - 10) < y < (FLAT_Y + 10), f"Unexpected Y={y} for flat world"
    assert -1_000_000 < z < 1_000_000


@pytest.mark.integration
def test_player_orientation(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    assert -90.0 <= obs.player_pitch <= 90.0
    assert -180.0 <= obs.player_yaw <= 180.0
