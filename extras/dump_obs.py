"""
For testing. Prints received observation to console. Doesn't rely on mcio_ctrl at all.
"""

import pprint
import time

import cbor2
import zmq

OBSERVATION_PORT = 8001


def recv_loop() -> None:
    zmq_context = zmq.Context()

    # Socket to receive observation updates
    observation_socket = zmq_context.socket(zmq.PULL)
    observation_socket.connect(f"tcp://localhost:{OBSERVATION_PORT}")

    start = time.time()
    pkt_count = 0
    while True:
        pbytes = observation_socket.recv()

        pkt = cbor2.loads(pbytes)
        # The frame is too big to print, so replace with its length.
        if "frame" in pkt:
            pkt["frame"] = len(pkt["frame"])
        pprint.pprint(pkt)

        # Print a PPS rate every second.
        end = time.time()
        pkt_count += 1
        if end - start >= 1:
            print(f"PPS = {pkt_count / (end - start):.1f}")
            pkt_count = 0
            start = end


if __name__ == "__main__":
    recv_loop()
