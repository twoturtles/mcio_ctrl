# Prints received state to console. Doesn't rely on mcio_remote at all.

import pprint
import time

import cbor2
import zmq

def recv_loop():
    zmq_context = zmq.Context()

    # Socket to receive state updates
    state_socket = zmq_context.socket(zmq.SUB)
    state_socket.connect(f"tcp://localhost:5557")
    state_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    start = time.time()
    pkt_count = 0
    while True:
        pbytes = state_socket.recv()

        pkt = cbor2.loads(pbytes)
        # The frame is too big to print, so replace with its length.
        pkt['frame_png'] = len(pkt['frame_png'])
        pprint.pprint(pkt)

        # Print a PPS rate every second.
        end = time.time()
        pkt_count += 1
        if end - start >= 1:
            print(f'PPS = {pkt_count / (end - start):.1f}')
            pkt_count = 0
            start = end


if __name__ == "__main__":
    recv_loop()