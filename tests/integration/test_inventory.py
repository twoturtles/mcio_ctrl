"""Inventory manipulation tests via commands."""

import pytest

from mcio_ctrl import network

from .conftest import ControllerHolder, send_and_recv


@pytest.mark.integration
def test_give_item(ctrl: ControllerHolder) -> None:
    """Give the player a diamond and verify it appears in inventory."""
    # Clear first to start clean
    clear = network.ActionPacket(commands=["clear @s"])
    ctrl.send_action(clear)
    ctrl.recv_observation()
    send_and_recv(ctrl)  # extra tick

    # Give a diamond
    give = network.ActionPacket(commands=["give @s minecraft:diamond 1"])
    ctrl.send_action(give)
    ctrl.recv_observation()
    obs = send_and_recv(ctrl)  # extra tick for inventory update

    found = any(slot.id == "minecraft:diamond" for slot in obs.inventory_main)
    assert found, f"Diamond not found in inventory: {obs.inventory_main}"


@pytest.mark.integration
def test_clear_inventory(ctrl: ControllerHolder) -> None:
    """Clear the player's inventory and verify it's empty."""
    # Give something first so we know clearing works
    give = network.ActionPacket(commands=["give @s minecraft:diamond 1"])
    ctrl.send_action(give)
    ctrl.recv_observation()
    send_and_recv(ctrl)

    # Clear
    clear = network.ActionPacket(commands=["clear @s"])
    ctrl.send_action(clear)
    ctrl.recv_observation()
    obs = send_and_recv(ctrl)

    non_empty = [slot for slot in obs.inventory_main if slot.count > 0]
    assert len(non_empty) == 0, f"Inventory not empty after clear: {non_empty}"
