'''
Provide a simple gui interface.
cv2 can provide something similar with less code, but its window rendering
doesn't seem reliable - sometimes the window isn't updated.
Using glfw since we already use that as a requirement.
'''

import queue
import argparse
import textwrap
import time
import threading

import glfw
import OpenGL.GL as gl
from PIL import Image

import numpy as np

from mcio_remote import util, LOG

class ImageStreamGui:
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


        self._frame_queue = util.LatestItemQueue()

        # Initialize
        self.frame_width = 0
        self.frame_height = 0
        self.scale = scale
        self.is_focused = glfw.get_window_attrib(self.window, glfw.FOCUSED)

        # Start the gui thread 
        self._gui_thread = threading.Thread(target=self._gui_thread_fn, name="GuiThread")
        self._gui_thread.daemon = True
        self._gui_thread.start()


    def show(self, image: Image):
        self._frame_queue.put(image)

    def _gui_thread_fn(self, fps=60):
        LOG.info("GuiThread start")
        frame_time = 1.0 / fps  # Time per frame in seconds
        while self._running.is_set() and not glfw.window_should_close(self.window):
            start_time = time.perf_counter()
            glfw.poll_events() # Poll for events

            # Render next frame
            try:
                frame = self._frame_queue.get()
            except queue.Empty:
                pass
            else:
                self.render(frame)

            # FPS limit
            elapsed = time.perf_counter() - start_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)

        self.cleanup()
        LOG.info("GuiThread shutdown")

    def key_callback(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        # Quit handling
        if key == glfw.KEY_Q and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)
            return

    def cursor_position_callback(self, window, xpos, ypos):
        """Handle mouse movement"""
        pass
        
    def mouse_button_callback(self, window, button, action, mods):
        """Handle mouse button events"""
        pass

    def resize_callback(self, window, width, height):
        """Handle window resize"""
        gl.glViewport(0, 0, width, height)
        # Force a redraw
        glfw.post_empty_event()

    # Note: focused is 0 or 1
    def focus_callback(self, window, focused):
        pass

    def render(self, frame: Image):
        """Render graphics"""
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        # Link cursor mode to Minecraft. May regret this.
        # XXX
        #glfw.set_input_mode(self.window, glfw.CURSOR, observation.cursor_mode)

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
        
        # Upload the image to texture
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
        
    def cleanup(self):
        """Clean up resources"""
        self.controller.shutdown()
        glfw.terminate()
