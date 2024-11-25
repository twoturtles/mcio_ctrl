#
# Example allowing human control through MCio
#

import threading
import queue
import argparse
import textwrap

import glfw
import OpenGL.GL as gl

import numpy as np

import mcio_remote as mcio
from mcio_remote import LOG

# Threads to handle zmq i/o.
class ControllerThreads:
    def __init__(self, host='localhost'):
        # Flag to signal threads to stop.
        self.running = threading.Event()
        self.running.set()

        self.action_queue = queue.Queue()
        self.observation_queue = queue.Queue()

        self.mcio_conn = mcio.Connection()

        # Start threads
        self.observation_thread = threading.Thread(target=self.observation_thread_fn, name="ObservationThread")
        self.observation_thread.daemon = True
        self.observation_thread.start()

        self.action_thread = threading.Thread(target=self.action_thread_fn, name="ActionThread")
        self.action_thread.daemon = True
        self.action_thread.start()

    def action_thread_fn(self):
        ''' Loops. Pulls packets from the action_queue and sends to minecraft. '''
        LOG.info("ActionThread start")
        while self.running.is_set():
            action = self.action_queue.get()
            self.action_queue.task_done()
            if action is None:
                break   # Action None to signal exit
            self.mcio_conn.send_action(action)
        LOG.info("Action-Thread shut down")

    def observation_thread_fn(self):
        ''' Loops. Receives observation packets from minecraft and places on observation_queue'''
        LOG.info("ObservationThread start")
        while self.running.is_set():
            observation = self.mcio_conn.recv_observation()
            if observation is None:
                continue    # Exiting or packet decode error
            self.observation_queue.put(observation)
        LOG.info("ObservationThread shut down")

    def shutdown(self):
        self.running.clear()
        self.mcio_conn.close()

        self.observation_thread.join()
        # Send empty action to unblock ActionThread
        self.action_queue.put(None)
        self.action_thread.join()

class MCioGUI:
    def __init__(self, scale=1.0, width=800, height=600, name="MCio GUI"):
        ''' scale allows you to use a window larger or smaller than the minecraft window '''
        # Initialize GLFW
        if not glfw.init():
            raise Exception("GLFW initialization failed")
            
        # This fixes only filling the bottom-left 1/4 of the window on mac.
        glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, glfw.FALSE)
        # Create window
        self.window = glfw.create_window(width, height, name, None, None)
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
        glfw.set_window_focus_callback(self.window, self.focus_callback)

        # Initialize
        self.frame_width = 0
        self.frame_height = 0
        self.scale = scale
        self.is_focused = glfw.get_window_attrib(self.window, glfw.FOCUSED)

        self.controller = mcio.Controller()
        
    def key_callback(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        # Quit handling
        if key == glfw.KEY_Q and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)
            return
        if action == glfw.REPEAT:
            # Skip action REPEAT.
            return

        action = mcio.network.ActionPacket(keys=[(key, action)])
        self.controller.send_action(action)

    # XXX When the cursor gets to the edge of the screen you turn any farther because the
    # cursor position doesn't change. Minecraft handles this, but doesn't show the cursor.
    def cursor_position_callback(self, window, xpos, ypos):
        """Handle mouse movement"""
        if self.is_focused:
            # If we're scaling the window, also scale the position so things line up
            scaled_pos = (xpos / self.scale, ypos / self.scale)
            action = mcio.network.ActionPacket(mouse_pos=[scaled_pos])
            self.controller.send_action(action)
        
    def mouse_button_callback(self, window, button, action, mods):
        """Handle mouse button events"""
        action = mcio.network.ActionPacket(mouse_buttons=[(button, action)])
        self.controller.send_action(action)

    def resize_callback(self, window, width, height):
        """Handle window resize"""
        gl.glViewport(0, 0, width, height)
        # Force a redraw
        glfw.post_empty_event()

    # Note: focused is 0 or 1
    def focus_callback(self, window, focused):
        self.is_focused = True if focused else False

    def render(self, observation: mcio.network.ObservationPacket):
        """Render graphics"""
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if observation.frame_png:
            # Link cursor mode to Minecraft. May regret this.
            glfw.set_input_mode(self.window, glfw.CURSOR, observation.cursor_mode)

            # Convert PNG bytes to image
            frame = observation.get_frame_with_cursor()
            # Prepare frame for opengl
            frame = np.flipud(np.array(frame))
            frame = np.ascontiguousarray(frame)

            # shape = (height, width, channels)
            height = frame.shape[0]
            width = frame.shape[1]

            # On first frame or if size changed, resize window
            if height != self.frame_height or width != self.frame_width:
                self.frame_width = width
                self.frame_height = height
                glfw.set_window_size(self.window, int(width * self.scale), int(height * self.scale))
            
            # Create and bind texture
            texture = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            
            # Set texture parameters for scaling down/up
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            
            # Upload the scaled image to texture
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGB, 
                width, height, 0,
                gl.GL_RGB, gl.GL_UNSIGNED_BYTE, frame
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
                observation = self.controller.recv_observation(block=False)
            except queue.Empty:
                pass
            else:
                LOG.debug(observation)
                self.render(observation)
            
        # Cleanup
        LOG.info("Exiting...")
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources"""
        self.controller.shutdown()
        glfw.terminate()

def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
            Provides a human GUI to MCio
            Q to quit
                                    '''),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Window scale factor')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    app = MCioGUI(args.scale)
    app.run()