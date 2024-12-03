import numpy as np
import pytest
from mcio_remote.mcio_env.envs import mcio_env


@pytest.fixture
def action_space_dict1():
    return {
        "cursor_pos_rel": np.array([-637.4071, 344.94278], dtype=np.float32),
        "keys": {"32": 2, "340": 2, "65": 1, "68": 0, "83": 1, "87": 1},
        "mouse_buttons": {"0": 1, "1": 2},
    }


def test_key_space_to_pairs1(action_space_dict1):
    pairs = mcio_env._key_space_to_pairs(action_space_dict1["keys"])
    assert pairs == [(65, 1), (68, 0), (83, 1), (87, 1)]

def test_mb_space_to_pairs1(action_space_dict1):
    pairs = mcio_env._mb_space_to_pairs(action_space_dict1["mouse_buttons"])
    print(pairs)
    assert pairs == [(0, 1)]
