# mcio_remote
A Python interface for connecting to [MCio](https://github.com/twoturtles/MCio), a Minecraft mod enabling AI agent development.

## Overview
[MCio](https://github.com/twoturtles/MCio) is a Fabric mod that creates a network interface to Minecraft. It enables programmatic control through simulated keyboard/mouse inputs and provides video frame and other state output via ZMQ. The mod is designed primarily for AI researchers developing agents in the Minecraft environment.

MCio can be installed directly from [Modrinth](https://modrinth.com/user/TwoTurtles) - without requiring a Java build!

This Python package (mcio_remote) provides the interface for connecting to MCio, including a [Gymnasium](https://gymnasium.farama.org/) environment for reinforcement learning.

## Documentation
For detailed documentation, see our [Wiki](../../wiki).
