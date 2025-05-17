# Changelog

## 1.1.0 - 2025-05-15
- Default to the MineRL cursor
- Fractional cursor positions. This allows for POV changes
  of < 0.15 degrees, matching MineRL.
- MCIO_PROTOCOL_VERSION = 5

## 1.0.2 - 2025-05-15
- Fix using a relative path for mcio_dir
- Fix minerl_env cursor centering
- MCIO_PROTOCOL_VERSION = 4

## 1.0.1 - 2025-05-14
- Update readme on pypi
- MCIO_PROTOCOL_VERSION = 4

## 1.0.0 - 2025-05-09
- Add command to install mods
- MCIO_PROTOCOL_VERSION = 4

## 0.7.0 - 2025-05-05
- Rename to mcio_ctrl
- MCIO_PROTOCOL_VERSION = 4

## 0.6.0 - 2025-05-03
- Better handling of env vars
- Add headless gpu option
- Set doImmediateRespawn in worlds so agents
  don't have to click respawn.
- Env termination handling
- Speed test updates
- MCIO_PROTOCOL_VERSION = 4

## 0.5.0 - 2025-04-06
- Fix multiple resets
- Improve exit handling
- Easier env creating with a base env
- Add minerl compatible env
- MCIO_PROTOCOL_VERSION = 4

## 0.4.0 - 2025-03-11
- Add option to hide Minecraft window
- Add clear_input action
- Add raw frame support and make it the default
- Remove png and jpeg frame types
- Support other MCio 0.4.0 changes
- MCIO_PROTOCOL_VERSION = 3

## 0.3.2 - 2025-01-15
- Silence log warning during install
- MCIO_PROTOCOL_VERSION = 2

## 0.3.1 - 2025-01-14
- Remove debug print
- MCIO_PROTOCOL_VERSION = 2

## 0.3.0 - 2025-01-14
- Breaking config change: instance id -> instance name
- Set gamerule allowCommands to true in generated worlds
- Add gamemode selection to world create
- Many networking changes including switching to zmq push/pull sockets.
  This allows detecting connections.
- Launch instances from env.reset()
- Send commands through env.step()
- Minor command and logging changes
- Configurable action/observation ports
- Option to receive frames as JPEG
- MCIO_PROTOCOL_VERSION = 2

## 0.2.0 - 2024-12-22
- Add installer / launcher / world manager
- Add stop command
- Reverse bind/connect for the action port
- MCIO_PROTOCOL_VERSION = 1

## 0.1.1 - 2024-12-09
- Fix frame alignment issue
- MCIO_PROTOCOL_VERSION = 0

## 0.1.0 - 2024-12-07
- Initial release of mcio_remote
- MCIO_PROTOCOL_VERSION = 0
