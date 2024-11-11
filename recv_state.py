from dataclasses import dataclass
from typing import Set
import time
import io

import numpy as np
import cbor2
import zmq
from PIL import Image
import cv2

@dataclass
class StatePacket:
    seq: int = 0
    frame_png: bytes = b""
    message: str = ""

    @classmethod
    def unpack(cls, data: bytes) -> 'StatePacket':
        return cls(**cbor2.loads(data))


def recv_loop():
    zmq_context = zmq.Context()

    # Socket to receive state updates
    state_socket = zmq_context.socket(zmq.SUB)
    state_socket.connect(f"tcp://localhost:5557")
    state_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    scale = 2
    window_name = 'MCio Frame'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    start = time.time()
    pkt_count = 0
    width_last = height_last = None
    while True:
        pbytes = state_socket.recv()
        state = StatePacket.unpack(pbytes)

        end = time.time()
        pkt_count += 1
        if end - start >= 1:
            print(f'PPS = {pkt_count / (end - start):.1f} SEQ = {state.seq}')
            pkt_count = 0
            start = end

        nparr = np.frombuffer(state.frame_png, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        height, width = frame.shape[:2]
        if height != height_last or width != width_last:
            cv2.resizeWindow(window_name, width // scale, height // scale)
            width_last = width
            height_last = height

        cv2.imshow(window_name, frame)

        # Break loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    recv_loop()