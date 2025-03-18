"""
This provides an environment compatible with the minerl 1.0 action and observation spaces.
"""

import enum
from dataclasses import dataclass
from typing import Any

import glfw  # type: ignore
import gymnasium as gym
import numpy as np
from gymnasium import spaces
from numpy.typing import NDArray

from mcio_remote import controller, gui, instance
from mcio_remote.types import RunOptions

"""
Notes:

Minerl Observation Space:
Dict(pov:Box(low=0, high=255, shape=(360, 640, 3)))
obs['pov'].shape
(360, 640, 3)
obs['pov'].dtype
dtype('uint8')

{'pov': array([[[17, 17, 17],
        [17, 17, 17],
        [17, 17, 17],
        ...,
        [16, 15, 14],
        [21, 19, 17],
        [21, 19, 16]],



Minerl Action Space:
Dict({
    "ESC": "Discrete(2)",
    "attack": "Discrete(2)",
    "back": "Discrete(2)",
    "camera": "Box(low=-180.0, high=180.0, shape=(2,))",
    "drop": "Discrete(2)",
    "forward": "Discrete(2)",
    "hotbar.1": "Discrete(2)",
    "hotbar.2": "Discrete(2)",
    "hotbar.3": "Discrete(2)",
    "hotbar.4": "Discrete(2)",
    "hotbar.5": "Discrete(2)",
    "hotbar.6": "Discrete(2)",
    "hotbar.7": "Discrete(2)",
    "hotbar.8": "Discrete(2)",
    "hotbar.9": "Discrete(2)",
    "inventory": "Discrete(2)",
    "jump": "Discrete(2)",
    "left": "Discrete(2)",
    "pickItem": "Discrete(2)", Mouse 2
    "right": "Discrete(2)",
    "sneak": "Discrete(2)",
    "sprint": "Discrete(2)",    Left Control
    "swapHands": "Discrete(2)", F
    "use": "Discrete(2)"
})

OrderedDict([('ESC', array(0)), ('attack', array(1)), ('back', array(0)), ('camera', array([-21.149803,  41.296047], dtype=float32)), ('drop', array(1)), ('forward', array(1)), ('hotbar.1', array(0)), ('hotbar.2', array(1)), ('hotbar.3', array(0)), ('hotbar.4', array(1)), ('hotbar.5', array(1)), ('hotbar.6', array(1)), ('hotbar.7', array(0)), ('hotbar.8', array(1)), ('hotbar.9', array(0)), ('inventory', array(1)), ('jump', array(1)), ('left', array(0)), ('pickItem', array(1)), ('right', array(0)), ('sneak', array(0)), ('sprint', array(0)), ('swapHands', array(1)), ('use', array(1))])

Camera is a relative movement:
"This action changes the orientation of the agent’s heading by the corresponding
number of degrees. The head changes its orientation pitch by the first component
and its yaw by the second component. Both components are limited to [-180, 180]
inclusive."
[pitch, yaw] - [-180, 180] for both.
absolute pitch is limited to -90 (up) to 90 (down). Relative motion past these limits is ignored.
yaw will wrap around. positive = right, negative = left

Mouse Sensitivity 0.0 - 1.0, default is 0.5

// Code from Mouse.java:updateMouse()
double d = this.client.options.getMouseSensitivity().getValue() * 0.6F + 0.2F;
double e = d * d * d;
double f = e * 8.0;

// Explanation
// Scale [0, 1] to [.2, .8]
double sensitivityScale = this.client.options.getMouseSensitivity().getValue() * 0.6F + 0.2F;
// Cube - Low sensitivity values increase very gradually, while high values increase more dramatically
// Scale is now [0.008, .512]
double cubicSensitivity = sensitivityScale * sensitivityScale * sensitivityScale;
// Scale to final range [0.064, 4.096]
double finalSensitivityMultiplier = cubicSensitivity * 8.0;

For default: .5 *.6 + .2 = .5; .5 * .5 * .5 = .125; .125 * 8 = 1

changeLookDirection() hardcodes degreesPerPixel = 0.15
		float f = (float)cursorDeltaY * 0.15F;
		float g = (float)cursorDeltaX * 0.15F;

        pitch = clamp((pitch + f) % 360, -90, 90)
        yaw = yaw + g

        

Summary
Mouse.updateMouse():
    mouseSensitivity (s) = [0, 1], default is 0.5
    finalScale = (s * 0.6 + 0.2)^3 * 8 = [0.008, 0.512], default = 1
    deltaX = finalScale * cursorDeltaX
    deltaY = finalScale * cursorDeltaY


Entity.changeLookDirection(cursorDeltaX, cursorDeltaY):
    degreesPerPixel = 0.15
    pitchDelta = cursorDeltaY * degreesPerPixel
    yawDelta = cursorDeltaX * degreesPerPixel

    pitch = clamp((pitch + pitchDelta) % 360, -90, 90)
    yaw = yaw + yawDelta





"""


# Stub in the action and observation space types
type MinerlAction = dict[str, Any]
type MinerlObservation = dict[str, Any]


class InputType(enum.Enum):
    KEY = 0
    MOUSE = 1


@dataclass()
class Input:
    type: InputType
    code: int


# Map from Minerl action name to Minecraft input
KEYMAP: dict[str, Input] = {
    "attack": Input(InputType.MOUSE, glfw.MOUSE_BUTTON_LEFT),
    "use": Input(InputType.MOUSE, glfw.MOUSE_BUTTON_RIGHT),
    "pickItem": Input(InputType.MOUSE, glfw.MOUSE_BUTTON_MIDDLE),
    "forward": Input(InputType.KEY, glfw.KEY_W),
    "left": Input(InputType.KEY, glfw.KEY_A),
    "right": Input(InputType.KEY, glfw.KEY_D),
    "back": Input(InputType.KEY, glfw.KEY_S),
    "drop": Input(InputType.KEY, glfw.KEY_Q),
    "ESC": Input(InputType.KEY, glfw.KEY_ESCAPE),
    "inventory": Input(InputType.KEY, glfw.KEY_E),
    "jump": Input(InputType.KEY, glfw.KEY_SPACE),
    "sneak": Input(InputType.KEY, glfw.KEY_LEFT_SHIFT),
    "sprint": Input(InputType.KEY, glfw.KEY_LEFT_CONTROL),
    "swapHands": Input(InputType.KEY, glfw.KEY_F),
    "hotbar.1": Input(InputType.KEY, glfw.KEY_1),
    "hotbar.2": Input(InputType.KEY, glfw.KEY_2),
    "hotbar.3": Input(InputType.KEY, glfw.KEY_3),
    "hotbar.4": Input(InputType.KEY, glfw.KEY_4),
    "hotbar.5": Input(InputType.KEY, glfw.KEY_5),
    "hotbar.6": Input(InputType.KEY, glfw.KEY_6),
    "hotbar.7": Input(InputType.KEY, glfw.KEY_7),
    "hotbar.8": Input(InputType.KEY, glfw.KEY_8),
    "hotbar.9": Input(InputType.KEY, glfw.KEY_9),
}


class MinerlEnv(gym.Env[MinerlObservation, MinerlAction]):
    metadata = {
        "render_modes": ["human", "rgb_array"],
    }

    def __init__(
        self,
        run_options: RunOptions,
        *,
        launch: bool = False,
        render_mode: str | None = None,
    ):
        """
        Attempt at Minerl 1.0 compatible environment. This only replicates the Minerl
        action and observation spaces.

        Args:
            run_options:
                If you're not using this env to launch Minecraft, the only options
                used are height, width, and mcio_mode.

                The remaining options are used if the env is launching an instance. At least
                instance_name is required in that case.

            launch: Should the env launch Minecraft

            render_mode: human, rgb_array
        """
        self.run_options = run_options
        self.launch = launch
        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        self.last_frame: NDArray[np.uint8] | None = None
        self.last_cursor_pos: tuple[int, int] = (0, 0)
        self.keys_pressed: set[str] = set()
        self.mouse_buttons_pressed: set[str] = set()

        # These need closing when done. Handled in close().
        self.gui: gui.ImageStreamGui | None = None
        self.ctrl: controller.ControllerCommon | None = None
        self.launcher: instance.Launcher | None = None

        self.observation_space = spaces.Dict(
            {
                "pov": spaces.Box(
                    low=0,
                    high=255,
                    # shape=(height, width, channels)
                    shape=(self.run_options.height, self.run_options.width, 3),
                    dtype=np.uint8,
                ),
            }
        )

        _action_space: dict[str, Any] = {
            key: spaces.Discrete(2) for key in KEYMAP.keys()
        }
        _action_space["camera"] = spaces.Box(low=-180.0, high=180.0, shape=(2,))
        self.action_space = spaces.Dict(_action_space)
