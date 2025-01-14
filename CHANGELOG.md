# Changelog

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
