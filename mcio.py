import time
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Set

import zmq
import cbor2
import glfw     # For key definitions



@dataclass
class CmdPacket:
    seq: int = 0           # sequence number
    keys_pressed: Set[int] = field(default_factory=set)
    key_reset: bool = False
    message: str = ""
    #image_data: bytes
    #numbers: List[int]
    #metadata: Dict[str, str]

    def pack(self) -> bytes:
        return cbor2.dumps(asdict(self))
    
    @classmethod
    def unpack(cls, data: bytes) -> 'CmdPacket':
        return cls(**cbor2.loads(data))


class MinecraftController:
    def __init__(self, host: str = "localhost"):
        # Set up ZMQ context
        self.context = zmq.Context()
        
        # Socket to send commands
        self.cmd_socket = self.context.socket(zmq.PUB)
        self.cmd_socket.bind(f"tcp://{host}:5556")
        
        # Socket to receive state updates
        self.state_socket = self.context.socket(zmq.SUB)
        self.state_socket.connect(f"tcp://{host}:5557")
        self.state_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def send(self, command: CmdPacket) -> None:
        self.cmd_socket.send(command.pack())

    def close(self) -> None:
        """Clean up ZMQ resources."""
        self.cmd_socket.close()
        self.state_socket.close()
        self.context.term()

# Example usage
if __name__ == "__main__":
    # Create controller
    controller = MinecraftController()
    # Give time for subscribers to connect
    time.sleep(1)

    print('Here')
    try:
        pkt = CmdPacket(seq=22, key_reset=True, keys_pressed=({glfw.KEY_W, glfw.KEY_SPACE}), message='HELLOOOO')
        controller.send(pkt)
        time.sleep(1)
        pkt = CmdPacket(seq=22, keys_pressed=({glfw.KEY_W}))
        controller.send(pkt)
        time.sleep(1)
        
    finally:
        controller.close()