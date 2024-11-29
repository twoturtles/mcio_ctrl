from gymnasium.envs.registration import register

register(
    id="mcio_env/MCioEnv-v0",
    entry_point="mcio_env.envs:MCioEnv",
)
