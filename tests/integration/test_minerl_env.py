"""Test gymnasium envs"""

import numpy as np
import pytest

from mcio_ctrl.envs import minerl_env

from .conftest import get_test_run_options


@pytest.mark.integration
def test_minerl_env(minecraft_session: None) -> None:
    run_opts = get_test_run_options(launch=False)
    env = minerl_env.MinerlEnv(run_opts)

    # Note: tp is absolute yaw, pitch vs. camera which is Δ-pitch, Δ-yaw
    setup_commands = [
        # /tp <target> <x> <y> <z> <yaw> <pitch>
        "teleport @s ~ ~ ~ -30 50",
    ]
    obs, info = env.reset(options={"commands": setup_commands})
    obs, reward, terminated, truncated, info = env.skip_steps(25)
    assert env.last_pitch == pytest.approx(50.0, abs=1.0)
    assert env.last_yaw == pytest.approx(-30.0, abs=1.0)

    action = env.get_noop_action()
    # Delta pitch, yaw
    action["camera"] = np.array((-10, 20), dtype=np.float32)
    obs, reward, terminated, truncated, info = env.step(action)
    assert env.last_pitch == pytest.approx(40.0, abs=1.0)
    assert env.last_yaw == pytest.approx(-10.0, abs=1.0)

    env.close()
