from collections import defaultdict
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from mcio_ctrl import network, types


class DegreesToPixels:
    """Convert a change in degrees of pitch and yaw to absolute pixels.
    This class allows an environment to use degrees of change of pitch and yaw and converts them into
    the equivalent absolute pixels for input into Minecraft.

    Minecraft takes in cursor position in terms of pixel coordinates and
    translates that into degrees of change in the viewpoint. When the mouse
    sensitivity is set to the default (0.5), the conversion is simply 1 pixel per 0.15
    degrees. This class is using that constant scaling factor.

    See Mouse.updateMouse() and Entity.changeLookDirection() in Minecraft (yarn mappings) for details.
    """

    DEGREES_PER_PIXEL = 0.15
    PIXELS_PER_DEGREE = 1 / DEGREES_PER_PIXEL

    def __init__(self, *, x: float = 0.0, y: float = 0.0) -> None:
        self.x, self.y = x, y

    def update(self, *, yaw_delta: float, pitch_delta: float) -> tuple[float, float]:
        """Delta arguments are in degrees. Returns the new cursor position in pixels."""
        self.x += yaw_delta * self.PIXELS_PER_DEGREE
        self.y += pitch_delta * self.PIXELS_PER_DEGREE
        return self.x, self.y

    def set(self, x: float, y: float) -> None:
        """Directly set the absolute current pixel location"""
        self.x, self.y = x, y


class InputStateManager:
    def __init__(self) -> None:
        """Tracks the state of input keys and mouse buttons. This converts a
        stream of actions to input events. Consecutive actions of the same type
        only generate a single event. E.g., if two Press actions are generated
        in a row, only the first Press action will generate a Press event.
        With this, consecutive Presses are treated as a Press and Hold.
        """
        self.pressed_set: set[types.InputID] = set()

    def update(
        self, pressed: set[types.InputID], released: set[types.InputID]
    ) -> list[types.InputEvent]:
        """Return set of updates to send to Minecraft. Also updates pressed_set."""
        update_events: list[types.InputEvent] = []

        new_presses = pressed - self.pressed_set
        for input_id in new_presses:
            update_events.append(
                types.InputEvent.from_id(input_id, types.GlfwAction.PRESS)
            )

        new_releases = self.pressed_set & released
        for input_id in new_releases:
            update_events.append(
                types.InputEvent.from_id(input_id, types.GlfwAction.RELEASE)
            )

        self.pressed_set |= new_presses
        self.pressed_set -= new_releases

        return update_events

    def process_action(
        self, action: dict[str, Any], input_map: dict[str, types.InputID]
    ) -> list[types.InputEvent]:
        """Prepare an action to be passed to update - Build sets of InputIDs based on Pressed or Not.
        Pass those sets to update and return the result.
        action - instance of an environment action. The keys are action names.
        input_map - maps action names to InputIDs.
        """
        # Build sets of which InputIDs are pressed or not
        pressed_set: set[types.InputID] = set()
        released_set: set[types.InputID] = set()
        for action_name, action_val in action.items():
            if action_name not in input_map:
                # The action will contain non-key/button fields
                continue
            input_id = input_map[action_name]
            # action_val is Discrete(2), so either np.int64(0) or np.int64(1)
            if bool(action_val):
                pressed_set.add(input_id)
            else:
                released_set.add(input_id)

        return self.update(pressed_set, released_set)


class StatsCache(defaultdict[str, defaultdict[str, int]]):
    """Cache stats to return full stats on request.
    Note: this is currently using a defaultdict, so reading a non-existent value
    will add that value to the cache.

    The cache is a two-level defaultdict: category -> id -> value
    Example: dirt_obtained = stats_cache["minecraft:picked_up"]["minecraft:dirt"]

    Use `MCIO_HELP_STATS=true mcio demo` to get a full list of stats.
    """

    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        super().__init__(lambda: defaultdict(int))

    def update_cache(self, obs: network.ObservationPacket) -> None:
        """Update the cache with stats from an observation packet."""
        opt = obs.get_option(types.StatsFullOption) or obs.get_option(
            types.StatsUpdateOption
        )
        if not isinstance(opt, (types.StatsFullOption, types.StatsUpdateOption)):
            return  # opt is None
        if isinstance(opt, types.StatsFullOption):
            self.clear()
        for cat_entry in opt.categories:
            for stat in cat_entry.stats:
                self[cat_entry.category][stat.id] = stat.value


def nf32(seq: Sequence[int | float] | int | float) -> NDArray[np.float32]:
    """Convert sequences or single values to np.float32 arrays. Turns single values into 1D arrays."""
    if isinstance(seq, (int, float)):
        seq = [float(seq)]
    arr = np.array([float(val) for val in seq], dtype=np.float32)
    return arr
