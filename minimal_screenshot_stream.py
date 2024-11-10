import glfw
import OpenGL.GL as gl
from PIL import Image
import numpy as np
import time
import os

# Initialize GLFW and create window
glfw.init()
window = glfw.create_window(800, 600, "Image Viewer", None, None)
glfw.make_context_current(window)

# Create texture
texture = gl.glGenTextures(1)
gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)

# Load and display images from folder
folder = "path/to/your/images"  # Change this to your folder path
image_files = sorted(os.listdir(folder))

while not glfw.window_should_close(window):
    for img_file in image_files:
        # Load image
        img = Image.open(os.path.join(folder, img_file))
        img_data = np.array(img)
        
        # Upload texture
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, img.width, img.height, 
                       0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, img_data)
        
        # Draw fullscreen quad
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 0); gl.glVertex2f(-1, 1)
        gl.glTexCoord2f(1, 0); gl.glVertex2f(1, 1)
        gl.glTexCoord2f(1, 1); gl.glVertex2f(1, -1)
        gl.glTexCoord2f(0, 1); gl.glVertex2f(-1, -1)
        gl.glEnd()
        
        # Show image and poll events
        glfw.swap_buffers(window)
        glfw.poll_events()
        
        time.sleep(1/30)  # Limit to ~30 FPS
        
        if glfw.window_should_close(window):
            break

# Cleanup
glfw.terminate()