"""Player movement and command execution tests."""

import math

import glfw  # type: ignore
import pytest

from mcio_ctrl import network, types
from mcio_ctrl.envs import env_util

from .conftest import FLAT_Y, IntegrationController


@pytest.mark.integration
def test_forward_movement(ctrl: IntegrationController) -> None:
    """Press W for 20 ticks and verify the player moved."""
    obs_before = ctrl.send_and_recv()
    x0, y0, z0 = obs_before.player_pos

    # Press W
    press = network.ActionPacket(
        inputs=[
            types.InputEvent(types.InputType.KEY, glfw.KEY_W, types.GlfwAction.PRESS)
        ]
    )
    ctrl.send_and_recv(press)

    # Hold for 40 ticks
    ctrl.skip_steps(40)

    # Release W
    release = network.ActionPacket(
        inputs=[
            types.InputEvent(types.InputType.KEY, glfw.KEY_W, types.GlfwAction.RELEASE)
        ]
    )
    obs_after = ctrl.send_and_recv(release)
    x1, y1, z1 = obs_after.player_pos

    dist = math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2)
    assert dist > 0.5, f"Player barely moved: dist={dist}"


@pytest.mark.integration
def test_turning(ctrl: IntegrationController) -> None:
    # Setup - face straight South
    tp_action = network.ActionPacket(commands=["teleport @s ~ ~ ~ 0 0"])
    obs = ctrl.send_and_recv(tp_action, 20)
    # Check facing straight South
    assert obs.player_yaw == pytest.approx(0, abs=1.0)
    assert obs.player_pitch == pytest.approx(0, abs=1.0)

    # Turn and check that cursor movement causes expected change in pitch/yaw
    dpp = env_util.DegreesToPixels.DEGREES_PER_PIXEL
    obs = ctrl.send_and_recv(network.ActionPacket(cursor_pos=[(200, 400)]))
    # Check x movement matches expected yaw
    assert obs.player_yaw == pytest.approx(200 * dpp, abs=1.0)
    # Check y movement matches expected pitch
    assert obs.player_pitch == pytest.approx(400 * dpp, abs=1.0)


@pytest.mark.integration
def test_command_execution(ctrl: IntegrationController) -> None:
    """Teleport via /teleport, verify position, then teleport back."""
    obs_before = ctrl.send_and_recv()
    orig_pos = obs_before.player_pos

    # Teleport to a known position
    tp_action = network.ActionPacket(commands=[f"teleport @s 100 {FLAT_Y} 200"])
    obs = ctrl.send_and_recv(tp_action, 20)

    x, y, z = obs.player_pos
    assert x == pytest.approx(100, abs=1.0)
    assert y == pytest.approx(FLAT_Y, abs=1.0)
    assert z == pytest.approx(200, abs=1.0)

    # Teleport back
    tp_back = network.ActionPacket(
        commands=[f"teleport @s {orig_pos[0]:.1f} {orig_pos[1]:.1f} {orig_pos[2]:.1f}"]
    )
    ctrl.send_and_recv(tp_back, 20)
