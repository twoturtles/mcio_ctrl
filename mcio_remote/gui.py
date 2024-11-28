'''
Provide a simple gui interface.
cv2 can provide something similar with less code, but its window rendering
doesn't seem reliable - sometimes the window isn't updated.
Using glfw since we already use that as a requirement.
'''

import time
from typing import Callable

import glfw
import OpenGL.GL as gl
from PIL import Image

import numpy as np

from mcio_remote import util

class ImageStreamGui:
    def __init__(self, scale=1.0, width=800, height=600, name="MCio GUI"):
        ''' scale allows you to use a window larger or smaller than the minecraft window '''
        self.window, self.is_focused = self._glfw_init(width, height, name)

        # Initialize
        self.frame_width = 0
        self.frame_height = 0
        self.scale = scale

    def _glfw_init(self, width, height, name):
        # Initialize GLFW
        if not glfw.init():
            raise Exception("GLFW initialization failed")

        # This fixes only filling the bottom-left 1/4 of the window on mac.
        glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, glfw.FALSE)
        # Create window
        window = glfw.create_window(width, height, name, None, None)
        if not window:
            glfw.terminate()
            raise Exception("Window creation failed")

        # Set up OpenGL context
        glfw.make_context_current(window)

        # Set callbacks
        glfw.set_key_callback(window, self.key_callback)
        glfw.set_cursor_pos_callback(window, self.cursor_position_callback)
        glfw.set_mouse_button_callback(window, self.mouse_button_callback)
        glfw.set_window_size_callback(window, self.resize_callback)
        glfw.set_window_focus_callback(window, self.focus_callback)

        is_focused = glfw.get_window_attrib(window, glfw.FOCUSED)

        return window, is_focused

    def show(self, frame):
        glfw.poll_events() # Poll for events
        self.render(frame)
        return bool(glfw.window_should_close(self.window))

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

    def set_cursor_mode(self, mode: int):
        ''' Minecraft uses glfw.CURSOR_NORMAL (212993) and glfw.CURSOR_DISABLED (212995) '''
        glfw.set_input_mode(self.window, glfw.CURSOR, observation.cursor_mode)

    # Note: focused is 0 or 1
    def focus_callback(self, window, focused):
        pass

    def render(self, frame: Image):
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

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
        glfw.terminate()

class TestPattern:
    def __init__(self, width=640, height=480, frequency=0.1):
        self.width = width
        self.height = height
        self.frequency = frequency
        self.step = 0
        
    def get_frame(self):
        # Create image with background color
        color = self.cycle_spectrum(self.step, self.frequency)
        frame = np.full((self.height, self.width, 3), color, dtype=np.uint8)
        self.step += 1
        return frame

    def sin(self, x, frequency, phase_shift):
        # sin from 0 to 255. phase shift is fraction of 2*pi.
        return 127.5 * (np.sin(frequency * x + (phase_shift * 2 * np.pi)) + 1)

    def cycle_spectrum(self, step, frequency=0.1):
        """
        step: current step in the cycle
        frequency: how fast to cycle through colors
        """
        r = self.sin(step, frequency, 3/12)     # 0 = max
        g = self.sin(step, frequency, 11/12)    # 0 = going up
        b = self.sin(step, frequency, 7/12)     # 0 = going down
        return np.array([r, g, b], dtype=np.uint8)


def main():
    pat = TestPattern()
    gui = ImageStreamGui()
    while True:
        frame = pat.get_frame()
        if gui.show(frame):
            break
        time.sleep(.1)

if __name__ == "__main__":
    main()