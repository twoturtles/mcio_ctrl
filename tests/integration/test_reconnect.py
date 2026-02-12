"""Test reconnecting to a running Minecraft instance."""

import time

import pytest

from mcio_ctrl import controller, network, types

from .conftest import (
    ACTION_PORT,
    CONNECTION_TIMEOUT,
    OBSERVATION_PORT,
    ControllerHolder,
    send_and_recv,
)


@pytest.mark.integration
def test_reconnect_without_restart(ctrl: ControllerHolder) -> None:
    """Close the controller (without stopping MC), reconnect, and verify."""
    # Verify current connection works
    obs = send_and_recv(ctrl)
    assert obs.mode == types.MCioMode.SYNC

    # Close controller — but don't send stop, so MC keeps running
    ctrl.ctrl.close()

    time.sleep(1)

    # Reconnect
    new_ctrl = controller.ControllerSync(
        action_port=ACTION_PORT,
        observation_port=OBSERVATION_PORT,
        wait_for_connection=True,
        connection_timeout=CONNECTION_TIMEOUT,
    )

    # Verify new connection
    new_ctrl.send_action(network.ActionPacket(clear_input=True))
    obs = new_ctrl.recv_observation()
    assert obs.mode == types.MCioMode.SYNC
    assert obs.version == network.MCIO_PROTOCOL_VERSION

    # Replace the holder's inner controller so subsequent tests use the new one
    ctrl.ctrl = new_ctrl
