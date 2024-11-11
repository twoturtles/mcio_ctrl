import threading
import time
import io
import queue
from dataclasses import dataclass, asdict, field
from typing import Set

import glfw
import OpenGL.GL as gl
import cbor2
import zmq

import numpy as np
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
        # Flag to signal threads to stop.
        self.running = threading.Event()
        self.running.set()

        self.cmd_queue = queue.Queue()
        self.state_queue = queue.Queue()

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
        self.state_thread = threading.Thread(target=self.state_thread_fn, name="StateThread")
        self.state_thread.daemon = True
        self.state_thread.start()

        self.cmd_thread = threading.Thread(target=self.cmd_thread_fn, name="CommandThread")
        self.cmd_thread.daemon = True
        self.cmd_thread.start()

    def cmd_thread_fn(self):
        print("CommandThread start")
        while self.running.is_set():
            cmd = self.cmd_queue.get()
            if cmd is None:
                break   # Command None to signal exit
            self.cmd_socket.send(cmd.pack())
            self.cmd_queue.task_done()
        print("Command-Thread shut down")

    def state_thread_fn(self):
        print("StateThread start")
        while self.running.is_set():
            try:
                pbytes = self.state_socket.recv()
            except zmq.error.ContextTerminated:
                break   # Exiting
            state = StatePacket.unpack(pbytes)
            self.state_queue.put(state)
        print("StateThread shut down")

    def shutdown(self):
        self.running.clear()
        self.cmd_socket.close()
        self.state_socket.close()
        self.zmq_context.term()

        self.state_thread.join()
        # Send empty command to unblock CommandThread
        self.cmd_queue.put(None)
        self.cmd_thread.join()

class MCioGUI:
    def __init__(self, width=800, height=600):
        # Initialize GLFW
        if not glfw.init():
            raise Exception("GLFW initialization failed")
            
        # Create window
        self.window = glfw.create_window(width, height, "MCio GUI", None, None)
        if not self.window:
            glfw.terminate()
            raise Exception("Window creation failed")
            
        # Set up OpenGL context
        glfw.make_context_current(self.window)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        
        # Set callbacks
        glfw.set_key_callback(self.window, self.key_callback)
        glfw.set_cursor_pos_callback(self.window, self.cursor_position_callback)
        glfw.set_mouse_button_callback(self.window, self.mouse_button_callback)
        glfw.set_window_size_callback(self.window, self.resize_callback)

        self.controller = ControllerThreads()
        
    def key_callback(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        #print(f'Key={key} action={action}')
        
        # Quit handling
        if key == glfw.KEY_Q and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)
            return

        if action == glfw.PRESS:
            cmd = CmdPacket(keys_pressed={key})
            self.controller.cmd_queue.put(cmd)
        elif action == glfw.RELEASE:
            cmd = CmdPacket(keys_released={key})
            self.controller.cmd_queue.put(cmd)
        # Skip action REPEAT.

    # XXX When the cursor gets to the edge of the screen you turn any farther because the
    # cursor position doesn't change. Minecraft handles this, but doesn't show the cursor.
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
        print(f'RESIZE {width} {height}')
        gl.glViewport(0, 0, width, height)
        # Force a redraw
        glfw.post_empty_event()
        
    def render(self, state: StatePacket):
        """Render graphics"""
        SCALE = 2
        
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        
        if state.frame_png:
            # Convert PNG bytes to image
            img = Image.open(io.BytesIO(state.frame_png))
            img_width, img_height = img.size
            
            # Scale the target dimensions
            target_width = img_width // SCALE
            target_height = img_height // SCALE
            
            # On first frame or if size changed, resize window
            current_width, current_height = glfw.get_window_size(self.window)
            if current_width != target_width or current_height != target_height:
                print(f'RESIZE2 {target_width} {target_height}')
                glfw.set_window_size(self.window, target_width, target_height)
                gl.glViewport(0, 0, target_width, target_height)
                # Tell GLFW to poll events immediately
                glfw.poll_events()
            
            # Convert image to numpy array and flip vertically to pass to OpenGL
            img_data = np.array(img)
            img_data = np.flipud(img_data)
            
            # Scale the image data to fit the desired size
            img_data = cv2.resize(img_data, (target_width, target_height))
            
            # Create and bind texture
            texture = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            
            # Set texture parameters for scaling down/up
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            
            # Upload the scaled image to texture
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGB, 
                target_width, target_height, 0,
                gl.GL_RGB, gl.GL_UNSIGNED_BYTE, 
                img_data
            )
            
            # Enable texture mapping
            gl.glEnable(gl.GL_TEXTURE_2D)
            
            # Draw a quad (rectangle made of two triangles) that fills the screen
            # The quad goes from -1 to 1 in both x and y (OpenGL normalized coordinates)
            gl.glBegin(gl.GL_QUADS)
            # For each vertex, set texture coordinate (0-1) and vertex position (-1 to 1)
            gl.glTexCoord2f(0, 0); gl.glVertex2f(-1, -1)
            gl.glTexCoord2f(1, 0); gl.glVertex2f(1, -1)
            gl.glTexCoord2f(1, 1); gl.glVertex2f(1, 1)
            gl.glTexCoord2f(0, 1); gl.glVertex2f(-1, 1)
            gl.glEnd()
            
            # Clean up
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glDeleteTextures([texture])
        
        glfw.swap_buffers(self.window)
        
    def run(self):
        """Main application loop"""
        while not glfw.window_should_close(self.window):
            # Poll for events
            glfw.poll_events()
            try:
                state = self.controller.state_queue.get(block=False)
                self.controller.state_queue.task_done()
            except queue.Empty:
                pass
            else:
                self.render(state)
            
        # Cleanup
        print("Exiting...")
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources"""
        self.controller.shutdown()
        print('HERE1')
        glfw.terminate()
        print("HERE2")

if __name__ == "__main__":
    app = MCioGUI()
    app.run()