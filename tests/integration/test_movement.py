"""Player movement and command execution tests."""

import math

import glfw
import pytest

from mcio_ctrl import network, types

from .conftest import ControllerHolder, send_and_recv


@pytest.mark.integration
def test_forward_movement(ctrl: ControllerHolder) -> None:
    """Press W for 20 ticks and verify the player moved."""
    obs_before = send_and_recv(ctrl)
    x0, y0, z0 = obs_before.player_pos

    # Press W
    press = network.ActionPacket(
        inputs=[types.InputEvent(types.InputType.KEY, glfw.KEY_W, types.GlfwAction.PRESS)]
    )
    ctrl.send_action(press)
    ctrl.recv_observation()

    # Hold for 20 ticks
    for _ in range(20):
        send_and_recv(ctrl)

    # Release W
    release = network.ActionPacket(
        inputs=[types.InputEvent(types.InputType.KEY, glfw.KEY_W, types.GlfwAction.RELEASE)]
    )
    ctrl.send_action(release)
    obs_after = ctrl.recv_observation()
    x1, y1, z1 = obs_after.player_pos

    dist = math.sqrt((x1 - x0) ** 2 + (z1 - z0) ** 2)
    assert dist > 0.5, f"Player barely moved: dist={dist}"


@pytest.mark.integration
def test_command_execution(ctrl: ControllerHolder) -> None:
    """Teleport via /teleport, verify position, then teleport back."""
    obs_before = send_and_recv(ctrl)
    orig_pos = obs_before.player_pos

    # Teleport to a known position
    tp_action = network.ActionPacket(commands=["teleport @s 100 70 100"])
    ctrl.send_action(tp_action)
    obs = ctrl.recv_observation()

    # Give a tick for the position to update
    obs = send_and_recv(ctrl)

    x, y, z = obs.player_pos
    assert abs(x - 100) < 1.0, f"X={x}, expected ~100"
    assert abs(y - 70) < 2.0, f"Y={y}, expected ~70"
    assert abs(z - 100) < 1.0, f"Z={z}, expected ~100"

    # Teleport back
    tp_back = network.ActionPacket(
        commands=[f"teleport @s {orig_pos[0]:.1f} {orig_pos[1]:.1f} {orig_pos[2]:.1f}"]
    )
    ctrl.send_action(tp_back)
    ctrl.recv_observation()
