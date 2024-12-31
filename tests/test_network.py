from unittest.mock import MagicMock

import pytest
import zmq

from mcio_remote import network


@pytest.fixture
def mock_zmq(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Mock out enough of zmq to get past _Connection()"""
    # Set up Context mock
    mock_context = MagicMock()
    mock_socket = MagicMock()
    mock_socket.get_monitor_socket.return_value = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket
    monkeypatch.setattr("zmq.Context", mock_context)

    # Mock the monitor message function
    mock_monitor_message = MagicMock(return_value={"event": zmq.EVENT_CONNECTED})
    monkeypatch.setattr("zmq.utils.monitor.recv_monitor_message", mock_monitor_message)

    # Set up Poller mock
    mock_poller = MagicMock()
    mock_poller.return_value.poll.return_value = {
        mock_socket.get_monitor_socket.return_value: zmq.POLLIN
    }
    monkeypatch.setattr("zmq.Poller", mock_poller)

    # Return objects that tests might need to access
    return {
        "context": mock_context,
        "socket": mock_socket,
        "monitor_message": mock_monitor_message,
        "poller": mock_poller,
    }


def test_send(mock_zmq: dict[str, MagicMock]) -> None:
    conn = network._Connection()
    action = network.ActionPacket()
    conn.send_action(action)
    # Just checks that the packet makes it through to send.
    assert action.pack() == mock_zmq["socket"].send.call_args_list[0][0][0]


def test_recv_observation(mock_zmq: dict[str, MagicMock]) -> None:
    # Set up garbage packet. Decode will fail and we'll receive None
    mock_zmq["socket"].recv.return_value = b"garbage packet"
    conn = network._Connection()
    observation = conn.recv_observation()
    assert observation is None
