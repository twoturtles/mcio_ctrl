import multiprocessing as mp
import threading
import time
import sys
import os

import queue
import argparse
import textwrap

import glfw
import OpenGL.GL as gl
from PIL import Image

import numpy as np

from mcio_remote import util

def pp(msg):
    print(f'{os.getpid()}: {msg}')

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
        r = self.sin(step, frequency, 3/12)
        g = self.sin(step, frequency, 11/12)
        b = self.sin(step, frequency, 7/12)
        return np.array([r, g, b], dtype=np.uint8)


class DisplayManager:
    def __init__(self):
        # Create a queue for communication between processes
        self._frame_queue = mp.Queue(maxsize=2)
        self._cmd_queue = mp.Queue()
        self._process = None
        
        # Start the display process (which will be our parent process)
        self._start_display_process()
        
    def _start_display_process(self):
        if sys.platform == 'darwin':
            # On macOS, we need to use 'spawn' instead of 'fork'
            mp.set_start_method('spawn', force=True)
            
        self._process = mp.Process(
            target=self._run_display_loop,
            args=(self._frame_queue, self._cmd_queue)
        )
        self._process.daemon = True
        self._process.start()
        
    def show_frame(self, frame):
        """Non-blocking frame send"""
        try:
            # Remove old frame if queue is full
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except:
                    pass
            self._frame_queue.put_nowait(frame)
        except:
            pass  # Skip frame if queue is full
            
    def close(self):
        """Cleanup and close the display"""
        self._cmd_queue.put("QUIT")
        if self._process is not None:
            self._process.join(timeout=1.0)
            if self._process.is_alive():
                self._process.terminate()
    
    @staticmethod
    def _run_display_loop(frame_queue, cmd_queue):
        """Main display loop that runs in the parent process"""
        pp("Display loop running on parent process")
        
        while True:
            # Check for commands
            try:
                cmd = cmd_queue.get_nowait()
                if cmd == "QUIT":
                    break
            except:
                pass
                
            # Check for new frames
            try:
                frame = frame_queue.get_nowait()
                pp(f"Received frame: {frame}")  # In real GUI, would display the frame
            except:
                pass
                
            time.sleep(0.016)  # Simulate 60 FPS

class ImageStreamGui:
    def __init__(self, scale=1.0, width=800, height=600, name="MCio GUI"):
        ''' scale allows you to use a window larger or smaller than the minecraft window '''
        self.window, self.is_focused = self._glfw_init(width, height, name)

        # Initialize
        self.frame_width = 0
        self.frame_height = 0
        self.scale = scale

        self._frame_queue = util.LatestItemQueue()
        # Flag to signal gui thread to stop.
        self._running = threading.Event()
        self._running.set()

        # Start the gui thread 
        # self._gui_thread = threading.Thread(target=self._gui_thread_fn, name="GuiThread")
        # self._gui_thread.daemon = True
        # self._gui_thread.start()

        self.test_thread = threading.Thread(target=self.test_pattern,
                                            args=[width, height], name='TestThread')
        self.test_thread.daemon = True
        self.test_thread.start()
        self._gui_thread_fn()

    def show(self, image: Image):
        self._frame_queue.put(image)

    def test_pattern(self, width, height, frequency=0.1):
        pat = TestPattern(width, height, frequency=frequency)
        while True:
            frame = pat.get_frame()
            self.show(frame)
            time.sleep(.1)

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
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)

        # Set callbacks
        glfw.set_key_callback(window, self.key_callback)
        glfw.set_cursor_pos_callback(window, self.cursor_position_callback)
        glfw.set_mouse_button_callback(window, self.mouse_button_callback)
        glfw.set_window_size_callback(window, self.resize_callback)
        glfw.set_window_focus_callback(window, self.focus_callback)

        is_focused = glfw.get_window_attrib(window, glfw.FOCUSED)

        return window, is_focused

    def _gui_thread_fn(self, fps=60):
        print("GuiThread start")
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
        print("GuiThread shutdown")

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
        glfw.terminate()

def main1():
    pp('start')

    # Create the display manager
    display = DisplayManager()
    
    # Simulate sending frames
    try:
        frame_count = 0
        while frame_count < 10:  # Send 10 test frames
            frame = f"Frame {frame_count}"
            display.show_frame(frame)
            pp(f"Sent {frame} ")
            frame_count += 1
            time.sleep(0.1)
    finally:
        display.close()

def main2():
    pat = TestPattern()
    gui = ImageStreamGui()
    while True:
        frame = pat.get_frame()
        gui.show(frame)
        time.sleep(.1)

def main3():
    gui = ImageStreamGui()

if __name__ == "__main__":
    main3()