from gymnasium.envs.registration import register

from . import base_env, mcio_env, minerl_env

__all__ = [
    "base_env",
    "mcio_env",
    "minerl_env",
]

register(
    id="MCio/MCioEnv-v0",
    entry_point="mcio_ctrl.envs.mcio_env:MCioEnv",
)

register(
    id="MCio/MinerlEnv-v0",
    entry_point="mcio_ctrl.envs.minerl_env:MinerlEnv",
)
