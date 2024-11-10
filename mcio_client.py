import zmq
import json
import cv2
import numpy as np
import base64
import threading
import time
import pyautogui
from typing import Dict, Any

class MinecraftClient:
    def __init__(self):
        # Configure PyAutoGUI
        pyautogui.FAILSAFE = True  # Move mouse to corner to stop
        pyautogui.PAUSE = 0.0  # No delay between commands
        
        # ZMQ setup
        self.context = zmq.Context()
        
        # SUB socket for game state and video
        self.state_socket = self.context.socket(zmq.SUB)
        self.state_socket.connect("tcp://localhost:5556")
        self.state_socket.setsockopt_string(zmq.SUBSCRIBE, "gamestate")
        
        # REQ socket for sending commands
        self.command_socket = self.context.socket(zmq.REQ)
        self.command_socket.connect("tcp://localhost:5555")
        
        # State tracking
        self.latest_state: Dict[str, Any] = {}
        self.running = True
        
        # Movement settings
        self.move_speed = 1.0
        self.look_speed = 5.0
        
        # Key state tracking
        self.key_states = {
            'w': False,
            'a': False,
            's': False,
            'd': False,
            'space': False,
            'shift': False
        }

    def start(self):
        # Start state receiving thread
        state_thread = threading.Thread(target=self.receive_state)
        state_thread.daemon = True
        state_thread.start()
        
        # Start input handling thread
        input_thread = threading.Thread(target=self.handle_input)
        input_thread.daemon = True
        input_thread.start()
        
        # Main display loop
        self.display_loop()

    def receive_state(self):
        """Thread function to receive and process game state"""
        while self.running:
            try:
                # Receive topic and message
                topic = self.state_socket.recv_string()
                message = self.state_socket.recv_string()
                
                # Parse state
                state = json.loads(message)
                self.latest_state = state
                
            except Exception as e:
                print(f"Error receiving state: {e}")
                time.sleep(0.1)

    def send_command(self, command: dict):
        """Send a command to the Minecraft mod"""
        try:
            self.command_socket.send_string(json.dumps(command))
            response = self.command_socket.recv_string()
            return response
        except Exception as e:
            print(f"Error sending command: {e}")
            return None

    def handle_input(self):
        """Thread function to handle input using PyAutoGUI"""
        last_mouse_x, last_mouse_y = pyautogui.position()
        
        while self.running:
            try:
                # Check key states
                for key in self.key_states:
                    self.key_states[key] = pyautogui.keyIsPressed(key)
                
                # Handle movement based on key states
                x, y, z = 0, 0, 0
                
                if self.key_states['w']:
                    z = self.move_speed
                if self.key_states['s']:
                    z = -self.move_speed
                if self.key_states['a']:
                    x = -self.move_speed
                if self.key_states['d']:
                    x = self.move_speed
                if self.key_states['space']:
                    y = self.move_speed
                if self.key_states['shift']:
                    y = -self.move_speed
                
                if x != 0 or y != 0 or z != 0:
                    self.send_command({
                        "type": "MOVE",
                        "x": x,
                        "y": y,
                        "z": z
                    })
                
                # Handle mouse movement
                mouse_x, mouse_y = pyautogui.position()
                dx = mouse_x - last_mouse_x
                dy = mouse_y - last_mouse_y
                
                if dx != 0 or dy != 0:
                    self.send_command({
                        "type": "LOOK",
                        "yaw": dx * 0.5,
                        "pitch": dy * 0.5
                    })
                    last_mouse_x, last_mouse_y = mouse_x, mouse_y
                
                # Handle mouse buttons
                if pyautogui.primaryButton:
                    self.send_command({
                        "type": "CLICK",
                        "leftClick": True
                    })
                elif pyautogui.secondaryButton:
                    self.send_command({
                        "type": "CLICK",
                        "leftClick": False
                    })
                
                time.sleep(0.016)  # ~60 Hz polling
                
            except Exception as e:
                print(f"Error in input handling: {e}")
                time.sleep(0.1)

    def display_loop(self):
        """Main loop for displaying the game view"""
        cv2.namedWindow("Minecraft Remote View", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Minecraft Remote View", cv2.WND_PROP_TOPMOST, 1)
        
        while self.running:
            try:
                if self.latest_state and 'base64Screenshot' in self.latest_state:
                    # Decode and display screenshot
                    img_data = base64.b64decode(self.latest_state['base64Screenshot'])
                    img_array = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    # Display game state
                    if 'health' in self.latest_state:
                        health_text = f"Health: {self.latest_state['health']}"
                        cv2.putText(frame, health_text, (10, 30), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    if 'position' in self.latest_state:
                        pos = self.latest_state['position']
                        pos_text = f"Pos: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})"
                        cv2.putText(frame, pos_text, (10, 60), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    cv2.imshow("Minecraft Remote View", frame)
                
                # Check for exit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running = False
                    break
                    
            except Exception as e:
                print(f"Error in display loop: {e}")
                time.sleep(0.1)
        
        cv2.destroyAllWindows()
        self.context.term()

if __name__ == "__main__":
    print("Starting Minecraft remote control client...")
    print("Controls:")
    print("  WASD: Movement")
    print("  Space/Shift: Up/Down")
    print("  Mouse: Look around")
    print("  Mouse buttons: Interact")
    print("  Q: Quit (in video window)")
    print("  Move mouse to screen corner to emergency stop (PyAutoGUI failsafe)")
    
    client = MinecraftClient()
    client.start()
