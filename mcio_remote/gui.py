import time
from typing import Callable, Any

import glfw  # type: ignore
import OpenGL.GL as gl  # type: ignore
from numpy.typing import NDArray

import numpy as np


class ImageStreamGui:
    """
    Provides a simple interface to send a stream of images to a window.
    cv2 can provide something similar with less code, but its window rendering
    doesn't seem reliable - sometimes the window isn't updated.
    Uses glfw since we already use that as a requirement.
    """

    """ scale allows you to use a window larger or smaller than the minecraft window """

    def __init__(
        self,
        name: str = "MCio GUI",
        scale: float = 1.0,
        width: int = 800,
        height: int = 600,
    ):
        """Create ImageStreamGui. Use show() to stream images to the window.

        Args:
            name (str, optional): Window title. Defaults to "MCio GUI".
            scale (float, optional): Allows you to use a window larger or smaller than the Minecraft window. Defaults to 1.0.
            width (int, optional): Initial window width in pixels. Defaults to 800.
            height (int, optional): Initial window height in pixels. Defaults to 600.
        """
        self.window = self._glfw_init(width, height, name)
        self.set_callbacks()
        self.is_focused = bool(glfw.get_window_attrib(self.window, glfw.FOCUSED))

        # Initialize
        self.frame_width = 0
        self.frame_height = 0
        self.scale = scale

    def poll(self) -> None:
        glfw.poll_events()  # Poll for events

    def show(self, frame: NDArray[np.uint8], poll: bool = True) -> bool:
        """Display the next frame
        Args:
            frame (NDArray[np.uint8]): The new frame image
        Returns:
            bool: should_close - received request to quit / close the window
        """
        if poll:
            self.poll()
        self._render(frame)
        should_close = bool(glfw.window_should_close(self.window))
        return should_close

    type KeyCallback = Callable[[Any, int, int, int, int], None]
    type CursorPositionCallback = Callable[[Any, float, float], None]
    type MouseButtonCallback = Callable[[Any, int, int, int], None]
    type ResizeCallback = Callable[[Any, int, int], None]
    type FocusCallback = Callable[[Any, int], None]

    def set_callbacks(
        self,
        key_callback: KeyCallback | None = None,
        cursor_position_callback: CursorPositionCallback | None = None,
        mouse_button_callback: MouseButtonCallback | None = None,
        resize_callback: ResizeCallback | None = None,
        focus_callback: FocusCallback | None = None,
    ) -> None:
        """Set GLFW callbacks. See defaults for examples

        Args:
            key_callback (Callable | None, optional): Defaults to None.
            cursor_position_callback (Callable | None, optional): Defaults to None.
            mouse_button_callback (Callable | None, optional): Defaults to None.
            resize_callback (Callable | None, optional): Defaults to None.
            focus_callback (Callable | None, optional): Defaults to None.
        """
        # Use provided callbacks or fall back to defaults
        self.key_callback = key_callback or self.default_key_callback
        self.cursor_position_callback = (
            cursor_position_callback or self.default_cursor_position_callback
        )
        self.mouse_button_callback = (
            mouse_button_callback or self.default_mouse_button_callback
        )
        self.resize_callback = resize_callback or self.default_resize_callback
        self.focus_callback = focus_callback or self.default_focus_callback

        # Set the callbacks in GLFW
        glfw.set_key_callback(self.window, self.key_callback)
        glfw.set_cursor_pos_callback(self.window, self.cursor_position_callback)
        glfw.set_mouse_button_callback(self.window, self.mouse_button_callback)
        glfw.set_window_size_callback(self.window, self.resize_callback)
        glfw.set_window_focus_callback(self.window, self.focus_callback)

    def set_cursor_mode(self, mode: int) -> None:
        """Set the cursor mode. Minecraft uses glfw.CURSOR_NORMAL (212993) and glfw.CURSOR_DISABLED (212995)"""
        glfw.set_input_mode(self.window, glfw.CURSOR, mode)

    def cleanup(self) -> None:
        """Clean up resources"""
        glfw.set_window_should_close(self.window, True)
        glfw.terminate()

    # Default Callbacks
    # I think window is actually a pointer.
    def default_key_callback(
        self, window: Any, key: int, scancode: int, action: int, mods: int
    ) -> None:
        """Handle keyboard input"""
        # Quit handling
        if key == glfw.KEY_Q and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)
            return

    def default_cursor_position_callback(
        self, window: Any, xpos: float, ypos: float
    ) -> None:
        """Handle mouse movement"""
        pass

    def default_mouse_button_callback(
        self, window: Any, button: int, action: int, mods: int
    ) -> None:
        """Handle mouse button events"""
        pass

    def default_resize_callback(self, window: Any, width: int, height: int) -> None:
        """Handle window resize"""
        gl.glViewport(0, 0, width, height)
        # Force a redraw
        glfw.post_empty_event()

    def default_focus_callback(self, window: Any, focused: int) -> None:
        """Handle focus change Note: focused is 0 or 1"""
        self.is_focused = bool(focused)

    #
    # Internal functions
    #

    def _glfw_init(self, width: int, height: int, name: str) -> Any:
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

        return window

    def _render(self, frame: NDArray[np.uint8]) -> None:
        """glfw portion of render"""
        self._auto_resize(frame)
        self._render_gl(frame)
        glfw.swap_buffers(self.window)

    def _auto_resize(self, frame: NDArray[np.uint8]) -> None:
        # shape = (height, width, channels)
        height = frame.shape[0]
        width = frame.shape[1]
        # On first frame or if size changed, resize window
        if height != self.frame_height or width != self.frame_width:
            self.frame_width = width
            self.frame_height = height
            glfw.set_window_size(
                self.window, int(width * self.scale), int(height * self.scale)
            )

    def _render_gl(self, frame: NDArray[np.uint8]) -> None:
        """opengl portion of render"""
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

        # Prepare frame for opengl
        frame = np.flipud(np.array(frame))
        frame = np.ascontiguousarray(frame)

        # Create and bind texture
        texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)

        # Set texture parameters for scaling down/up
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

        # Upload the image to texture
        # shape = (height, width, channels)
        height = frame.shape[0]
        width = frame.shape[1]
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGB,
            width,
            height,
            0,
            gl.GL_RGB,
            gl.GL_UNSIGNED_BYTE,
            frame,
        )

        # Enable texture mapping
        gl.glEnable(gl.GL_TEXTURE_2D)

        # Draw a quad (rectangle made of two triangles) that fills the screen
        # The quad goes from -1 to 1 in both x and y (OpenGL normalized coordinates)
        gl.glBegin(gl.GL_QUADS)
        # For each vertex, set texture coordinate (0-1) and vertex position (-1 to 1)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(-1, -1)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(1, -1)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(1, 1)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(-1, 1)
        gl.glEnd()

        # Clean up
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDeleteTextures([texture])


class TestPattern:
    """Generate a stream of images. Useful for testing."""

    __test__ = False  # tell pytest this isn't a test

    def __init__(self, width: int = 640, height: int = 480, frequency: float = 0.1):
        self.width = width
        self.height = height
        self.frequency = frequency
        self.step = 0

    def get_frame(self) -> NDArray[np.uint8]:
        # Create image with background color
        color = self.cycle_spectrum(self.step, self.frequency)
        frame = np.full((self.height, self.width, 3), color, dtype=np.uint8)
        self.step += 1
        return frame

    def sin(self, x: int, frequency: float, phase_shift: float) -> float:
        # sin from 0 to 255. phase shift is fraction of 2*pi.
        val: float = 127.5 * (np.sin(frequency * x + (phase_shift * 2 * np.pi)) + 1)
        return val

    def cycle_spectrum(self, step: int, frequency: float = 0.1) -> NDArray[np.uint8]:
        """
        step: current step in the cycle
        frequency: how fast to cycle through colors
        """
        r = self.sin(step, frequency, 3 / 12)  # 0 = max
        g = self.sin(step, frequency, 11 / 12)  # 0 = going up
        b = self.sin(step, frequency, 7 / 12)  # 0 = going down
        return np.array([r, g, b], dtype=np.uint8)


# Testing
def main() -> None:
    pat = TestPattern()
    gui = ImageStreamGui()

    def cursor_position_callback(window: Any, xpos: float, ypos: float) -> None:
        print(xpos, ypos)

    gui.set_callbacks(cursor_position_callback=cursor_position_callback)

    while True:
        frame = pat.get_frame()
        if gui.show(frame):
            break
        time.sleep(0.1)
    gui.cleanup()


if __name__ == "__main__":
    main()
