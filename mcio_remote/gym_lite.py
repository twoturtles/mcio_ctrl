import cv2
import numpy as np
import logging

from mcio_remote import controller, network, LOG

class GymLiteAsync:
    '''
    Stub in how gymn will work. Higher level interface than Controller
    This is async in the sense that it doesn't ensure the received state follows the previous
    action. But it does still block on recv.
    '''
    def __init__(self, name: str|None = None, render_mode: str|None = "human"):
        self.name = name
        self.render_mode = render_mode
        self.ctrl = None
        self._window_width = None
        self._window_height = None

    def reset(self, send_reset=True):
        if self.render_mode == 'human':
            cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        self.ctrl = controller.Controller()
        action = network.ActionPacket(reset=True)
        state = self.ctrl.send_and_recv(action)
        # TODO return observation, info
        return state

    def render(self, state: network.StatePacket):
        if self.render_mode == 'human':
            frame = state.get_frame_with_cursor()
            arr = np.asarray(frame)
            cv2_frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            height, width, _ = cv2_frame.shape
            if height != self._window_height or width != self._window_width:
                # On first frame or if size changed, resize window
                self._window_width = width
                self._window_height = height
                cv2.resizeWindow(self.name, width, height)
            cv2.imshow(self.name, cv2_frame)
            cv2.waitKey(1)
            
    def step(self, action):
        # XXX Change recv to take action (or store) and do sync handling
        self.ctrl.send_action(action)
        # XXX Ignoring restarted for now
        state, restarted = self.ctrl.recv_check_state(block=True)
        self.render(state)
        # TODO return observation, reward, terminated, truncated, info
        return state

    def close(self):
        # TODO
        ...

class GymLiteSync(GymLiteAsync):
    '''
    Synchronous version of stub gym interface
    step() ensures that the returned state follows the sent action.
    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def step(self, action):
        state = self.ctrl.send_and_recv(action)
        self.render(state)
        # return observation, reward, terminated, truncated, info
        return state
