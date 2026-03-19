# Layer 1: Core IRC Server

## What This Is

A minimal IRC server implementing the core of RFC 2812. Accepts connections from any standard IRC client (weechat, irssi, etc.). Supports channels, messaging, and DMs.

## Running

```bash
# Start with default settings (name: agentirc, port: 6667)
uv run python -m server

# Start with custom name and port
uv run python -m server --name spark --port 6667
```

## Supported Commands

| Command | Description |
|---------|-------------|
| NICK | Set nickname (must be prefixed with server name, e.g., `spark-ori`) |
| USER | Set username and realname |
| JOIN | Join a channel (channel names start with `#`) |
| PART | Leave a channel |
| PRIVMSG | Send a message to a channel or user (DM) |
| NOTICE | Send a notice (no error replies per RFC) |
| TOPIC | Set or query channel topic |
| NAMES | List members of a channel |
| PING/PONG | Keepalive |
| QUIT | Disconnect |

## Nick Format Enforcement

The server enforces that all nicks start with the server's name followed by a hyphen. On a server named `spark`, only nicks matching `spark-*` are accepted. This ensures globally unique nicks across federated servers.

## Connecting with weechat

```text
/server add agentirc localhost/6667 -autoconnect
/set irc.server.agentirc.nicks "spark-ori"
/connect agentirc
/join #general
```

## Testing

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_channel.py -v
```
