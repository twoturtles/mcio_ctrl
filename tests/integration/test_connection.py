"""Basic connection and protocol tests."""

import pytest

from mcio_ctrl import network, types

from .conftest import IntegrationController


@pytest.mark.integration
def test_protocol_version(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    assert obs.version == network.MCIO_PROTOCOL_VERSION


@pytest.mark.integration
def test_sync_mode(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    assert obs.mode == types.MCioMode.SYNC


@pytest.mark.integration
def test_sequence_increments(ctrl: IntegrationController) -> None:
    obs1 = ctrl.send_and_recv()
    obs2 = ctrl.send_and_recv()
    assert obs2.sequence > obs1.sequence
