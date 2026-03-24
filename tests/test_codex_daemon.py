import asyncio
import os
import tempfile
import pytest

from agentirc.clients.codex.daemon import CodexDaemon
from agentirc.clients.codex.config import (
    DaemonConfig, ServerConnConfig, AgentConfig,
    SupervisorConfig, WebhookConfig,
)


@pytest.mark.asyncio
async def test_codex_daemon_starts_and_connects(server):
    """CodexDaemon with skip_codex=True connects to IRC without needing codex CLI."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
        supervisor=SupervisorConfig(),
        webhooks=WebhookConfig(url=None),
    )
    agent = AgentConfig(nick="testserv-codex", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = CodexDaemon(config, agent, socket_dir=sock_dir, skip_codex=True)
    await daemon.start()
    try:
        await asyncio.sleep(0.5)
        assert "testserv-codex" in server.clients
        assert "#general" in server.channels
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_codex_daemon_ipc_irc_send(server, make_client):
    """IPC irc_send works through the Codex daemon."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
    )
    agent = AgentConfig(nick="testserv-codex", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = CodexDaemon(config, agent, socket_dir=sock_dir, skip_codex=True)
    await daemon.start()
    await asyncio.sleep(0.5)

    human = await make_client(nick="testserv-ori", user="ori")
    await human.send("JOIN #general")
    await human.recv_all(timeout=0.3)

    from agentirc.clients.codex.ipc import encode_message, decode_message, make_request
    sock_path = os.path.join(sock_dir, "agentirc-testserv-codex.sock")
    reader, writer = await asyncio.open_unix_connection(sock_path)

    req = make_request("irc_send", channel="#general", message="hello from codex skill")
    writer.write(encode_message(req))
    await writer.drain()

    data = await asyncio.wait_for(reader.readline(), timeout=2.0)
    resp = decode_message(data)
    assert resp["ok"] is True

    msg = await human.recv(timeout=2.0)
    assert "hello from codex skill" in msg

    writer.close()
    await writer.wait_closed()
    await daemon.stop()


@pytest.mark.asyncio
async def test_codex_config_defaults():
    """Codex config has correct backend-specific defaults."""
    agent = AgentConfig()
    assert agent.agent == "codex"
    assert agent.model == "gpt-5.4"

    supervisor = SupervisorConfig()
    assert supervisor.model == "gpt-5.4"


@pytest.mark.asyncio
async def test_codex_backend_dispatch():
    """CLI dispatch selects CodexDaemon for agent='codex'."""
    agent = AgentConfig(nick="test-codex", agent="codex", directory="/tmp")
    backend = getattr(agent, "agent", "claude")
    assert backend == "codex"

    # Verify CodexDaemon can be imported and constructed
    config = DaemonConfig()
    daemon = CodexDaemon(config, agent, skip_codex=True)
    assert daemon.agent.agent == "codex"
    assert daemon.agent.model == "gpt-5.4"
