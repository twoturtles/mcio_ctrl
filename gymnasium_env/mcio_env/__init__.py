from gymnasium.envs.registration import register

register(
    id="mcio_env/GridWorld-v0",
    entry_point="mcio_env.envs:GridWorldEnv",
)
