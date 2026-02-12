"""Basic connection and protocol tests."""

import pytest

from mcio_ctrl import network, types

from .conftest import ControllerHolder, send_and_recv


@pytest.mark.integration
def test_protocol_version(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    assert obs.version == network.MCIO_PROTOCOL_VERSION


@pytest.mark.integration
def test_sync_mode(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    assert obs.mode == types.MCioMode.SYNC


@pytest.mark.integration
def test_sequence_increments(ctrl: ControllerHolder) -> None:
    obs1 = send_and_recv(ctrl)
    obs2 = send_and_recv(ctrl)
    assert obs2.sequence > obs1.sequence
