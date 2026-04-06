import asyncio
import tempfile

import pytest

from culture.clients.claude.config import (
    AgentConfig,
    DaemonConfig,
    ServerConnConfig,
    SupervisorConfig,
    WebhookConfig,
)
from culture.clients.claude.daemon import AgentDaemon


@pytest.mark.asyncio
async def test_poll_loop_sends_prompt_on_unread(server, make_client):
    """Poll loop should detect unread messages and send them to the agent."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
        poll_interval=1,  # 1 second for fast testing
    )
    agent = AgentConfig(nick="testserv-bot", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = AgentDaemon(config, agent, socket_dir=sock_dir, skip_claude=True)
    await daemon.start()
    await asyncio.sleep(0.5)

    # Human sends a message (no @mention)
    human = await make_client(nick="testserv-ori", user="ori")
    await human.send("JOIN #general")
    await human.recv_all(timeout=0.3)
    await human.send("PRIVMSG #general :hello everyone")
    await asyncio.sleep(0.3)

    # Verify message is in buffer
    msgs = daemon._buffer.read("#general")
    assert len(msgs) >= 1
    assert any("hello everyone" in m.text for m in msgs)

    await daemon.stop()


@pytest.mark.asyncio
async def test_poll_loop_skips_when_paused(server, make_client):
    """Poll loop should not process messages when the agent is paused."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
        poll_interval=1,
    )
    agent = AgentConfig(nick="testserv-bot", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = AgentDaemon(config, agent, socket_dir=sock_dir, skip_claude=True)
    await daemon.start()
    await asyncio.sleep(0.5)

    # Pause the daemon
    daemon._paused = True

    # Human sends a message
    human = await make_client(nick="testserv-ori", user="ori")
    await human.send("JOIN #general")
    await human.recv_all(timeout=0.3)
    await human.send("PRIVMSG #general :paused message")
    await asyncio.sleep(1.5)  # Wait past poll interval

    # Buffer should still have unread messages (poll didn't consume them)
    msgs = daemon._buffer.read("#general")
    assert len(msgs) >= 1
    assert any("paused message" in m.text for m in msgs)

    await daemon.stop()


@pytest.mark.asyncio
async def test_poll_loop_skips_empty_buffer(server):
    """Poll loop should not send prompts when buffer is empty."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
        poll_interval=1,
    )
    agent = AgentConfig(nick="testserv-bot", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = AgentDaemon(config, agent, socket_dir=sock_dir, skip_claude=True)
    await daemon.start()
    await asyncio.sleep(1.5)  # Wait past poll interval

    # Buffer should have no messages
    msgs = daemon._buffer.read("#general")
    assert len(msgs) == 0

    await daemon.stop()


@pytest.mark.asyncio
async def test_poll_loop_disabled_with_zero_interval(server):
    """Poll loop should exit immediately when poll_interval is 0."""
    config = DaemonConfig(
        server=ServerConnConfig(host="127.0.0.1", port=server.config.port),
        poll_interval=0,
    )
    agent = AgentConfig(nick="testserv-bot", directory="/tmp", channels=["#general"])
    sock_dir = tempfile.mkdtemp()
    daemon = AgentDaemon(config, agent, socket_dir=sock_dir, skip_claude=True)
    await daemon.start()
    await asyncio.sleep(0.5)

    # Poll task should have completed (returned immediately)
    assert daemon._poll_task.done()

    await daemon.stop()
