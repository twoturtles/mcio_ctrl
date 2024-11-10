import glfw
import OpenGL.GL as gl

def main():
    if not glfw.init():
        return 1
        
    window = glfw.create_window(640, 480, "Test", None, None)
    if not window:
        glfw.terminate()
        return 1
        
    glfw.make_context_current(window)
    
    while not glfw.window_should_close(window):
        glfw.poll_events()
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        glfw.swap_buffers(window)
        
    glfw.terminate()
    return 0

if __name__ == '__main__':
    main()
