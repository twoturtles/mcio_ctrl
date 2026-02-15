"""Test reconnecting to a running Minecraft instance."""

import pytest

from mcio_ctrl import network, types

from .conftest import (
    ACTION_PORT,
    CONNECTION_TIMEOUT,
    OBSERVATION_PORT,
    IntegrationController,
)


@pytest.mark.integration
def test_reconnect_without_restart(ctrl: IntegrationController) -> None:
    """Close the controller (without stopping MC), reconnect, and verify."""
    # Verify current connection works
    obs = ctrl.send_and_recv()
    assert obs.mode == types.MCioMode.SYNC

    # Close controller — but don't send stop, so MC keeps running
    ctrl.close()

    # Reconnect
    new_ctrl = IntegrationController(
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

    new_ctrl.close()
