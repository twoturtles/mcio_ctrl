from unittest.mock import MagicMock, patch

from mcio_remote import network


@patch("zmq.Context", autospec=True)
def test_send(mock_context: MagicMock) -> None:
    # Set up our mock sockets
    conn = network._Connection()

    action = network.ActionPacket()
    conn.send_action(action)
    # send(action): CallList [0][0][0] -> Call -> Args -> 1st Arg
    call_args_list = mock_context.return_value.socket.return_value.send.call_args_list
    # Just checks that the packet makes it through to send.
    assert action.pack() == call_args_list[0][0][0]
