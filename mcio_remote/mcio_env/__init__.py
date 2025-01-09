from gymnasium.envs.registration import register

from . import envs as envs

register(
    id="mcio_env/MCioEnv-v0",
    entry_point="mcio_remote.mcio_env.envs:MCioEnv",
)
