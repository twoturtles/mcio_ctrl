"""Inventory manipulation tests via commands."""

import pytest

from mcio_ctrl import network

from .conftest import ControllerHolder


@pytest.mark.integration
def test_give_item(ctrl: ControllerHolder) -> None:
    """Give the player a diamond and verify it appears in inventory."""
    # Clear first to start clean
    clear = network.ActionPacket(commands=["clear @s"])
    ctrl.send_and_recv(clear, 20)
    # Give a diamond
    give = network.ActionPacket(commands=["give @s minecraft:diamond 1"])
    obs = ctrl.send_and_recv(give, 20)

    found = any(slot.id == "minecraft:diamond" for slot in obs.inventory_main)
    assert found, f"Diamond not found in inventory: {obs.inventory_main}"


@pytest.mark.integration
def test_clear_inventory(ctrl: ControllerHolder) -> None:
    """Clear the player's inventory and verify it's empty."""
    # Give something first so we know clearing works
    give = network.ActionPacket(commands=["give @s minecraft:diamond 1"])
    ctrl.send_and_recv(give, 20)
    # Clear
    clear = network.ActionPacket(commands=["clear @s"])
    obs = ctrl.send_and_recv(clear, 20)

    non_empty = [slot for slot in obs.inventory_main if slot.count > 0]
    assert len(non_empty) == 0, f"Inventory not empty after clear: {non_empty}"
