import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://localhost:5555")

# Give time for subscribers to connect
time.sleep(1)

for request in range(10):
    print(f"Sending request {request} ...")
    socket.send(b"Hello")
    time.sleep(0.1)  # Add small delay between messages