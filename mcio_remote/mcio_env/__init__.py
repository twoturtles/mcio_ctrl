from . import envs

from gymnasium.envs.registration import register

register(
    id="mcio_env/MCioEnv-v0",
    entry_point="mcio_remote.mcio_env.envs:MCioEnv",
)
