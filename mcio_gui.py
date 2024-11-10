import threading
from queue import Queue
from dataclasses import dataclass, asdict, field
from typing import Set

import glfw
import OpenGL.GL as gl
import cbor2
import zmq

@dataclass
class CmdPacket:
    seq: int = 0           # sequence number
    keys_pressed: Set[int] = field(default_factory=set)
    keys_released: Set[int] = field(default_factory=set)
    mouse_buttons_pressed: Set[int] = field(default_factory=set)
    mouse_buttons_released: Set[int] = field(default_factory=set)
    mouse_pos_update: bool = False
    mouse_pos_x: int = 0
    mouse_pos_y: int = 0
    key_reset: bool = False
    message: str = ""

    def pack(self) -> bytes:
        return cbor2.dumps(asdict(self))
    
    @classmethod
    def unpack(cls, data: bytes) -> 'CmdPacket':
        return cls(**cbor2.loads(data))

# Threads to handle zmq i/o.
class ControllerThreads:
    def __init__(self, host='localhost'):
        self.running = threading.Event()
        self.running.set()

        self.cmd_queue = Queue()
        self.state_queue = Queue()

        # Initialize ZMQ context
        self.zmq_context = zmq.Context()

        # Socket to send commands
        self.cmd_socket = self.zmq_context.socket(zmq.PUB)
        self.cmd_socket.bind(f"tcp://{host}:5556")
        
        # Socket to receive state updates
        self.state_socket = self.zmq_context.socket(zmq.SUB)
        self.state_socket.connect(f"tcp://{host}:5557")
        self.state_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        # Start ZMQ threads
        self.cmd_thread = threading.Thread(target=self.cmd_thread_fn)
        self.cmd_thread.daemon = True
        self.cmd_thread.start()

    def cmd_thread_fn(self):
        while self.running.is_set():
            cmd = self.cmd_queue.get()
            self.cmd_socket.send(cmd.pack())
            self.cmd_queue.task_done()

    def state_thread_fn(self):
        ...

    def shutdown(self):
        self.running.clear()
        self.cmd_thread.join()
        self.cmd_socket.close()
        self.zmq_context.term()
        
class MCioGUI:
    def __init__(self, width=800, height=600):
        # Initialize GLFW
        if not glfw.init():
            raise Exception("GLFW initialization failed")
            
        # Create window
        self.window = glfw.create_window(width, height, "GLFW-ZMQ Integration", None, None)
        if not self.window:
            glfw.terminate()
            raise Exception("Window creation failed")
            
        # Set up OpenGL context
        glfw.make_context_current(self.window)
        
        # Set callbacks
        glfw.set_key_callback(self.window, self.key_callback)
        glfw.set_cursor_pos_callback(self.window, self.cursor_position_callback)
        glfw.set_mouse_button_callback(self.window, self.mouse_button_callback)
        glfw.set_window_size_callback(self.window, self.resize_callback)

        self.controller = ControllerThreads()
        
    def key_callback(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        #print(f'Key={key} action={action}')
        if action == glfw.PRESS:
            cmd = CmdPacket(keys_pressed={key})
            self.controller.cmd_queue.put(cmd)
        elif action == glfw.RELEASE:
            cmd = CmdPacket(keys_released={key})
            self.controller.cmd_queue.put(cmd)
        # Skip action REPEAT.

    def cursor_position_callback(self, window, xpos, ypos):
        """Handle mouse movement"""
        #print(f'Mouse {xpos} {ypos}')
        cmd = CmdPacket(mouse_pos_update=True, mouse_pos_x=xpos, mouse_pos_y=ypos)
        self.controller.cmd_queue.put(cmd)
        
    def mouse_button_callback(self, window, button, action, mods):
        """Handle mouse button events"""
        if action == glfw.PRESS:
            cmd = CmdPacket(mouse_buttons_pressed={button})
            self.controller.cmd_queue.put(cmd)
        elif action == glfw.RELEASE:
            cmd = CmdPacket(mouse_buttons_released={button})
            self.controller.cmd_queue.put(cmd)

    def resize_callback(self, window, width, height):
        """Handle window resize"""
        gl.glViewport(0, 0, width, height)
        
    def render(self):
        """Render graphics"""
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        
        glfw.swap_buffers(self.window)
        
    def run(self):
        """Main application loop"""
        while not glfw.window_should_close(self.window):
            # Poll for events
            glfw.poll_events()
            
            # Render frame
            self.render()
            
        # Cleanup
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources"""
        self.controller.shutdown()
        glfw.terminate()

if __name__ == "__main__":
    app = MCioGUI()
    app.run()