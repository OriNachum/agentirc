import asyncio
import pytest
from agentirc.clients.claude.irc_transport import IRCTransport
from agentirc.clients.claude.message_buffer import MessageBuffer


@pytest.mark.asyncio
async def test_connect_and_register(server):
    buf = MessageBuffer()
    transport = IRCTransport(
        host="127.0.0.1", port=server.config.port,
        nick="testserv-bot", user="bot", channels=["#general"], buffer=buf,
    )
    await transport.connect()
    try:
        await asyncio.sleep(0.3)
        assert transport.connected
        assert "testserv-bot" in server.clients
    finally:
        await transport.disconnect()


@pytest.mark.asyncio
async def test_joins_channels(server):
    buf = MessageBuffer()
    transport = IRCTransport(
        host="127.0.0.1", port=server.config.port,
        nick="testserv-bot", user="bot", channels=["#general", "#dev"], buffer=buf,
    )
    await transport.connect()
    try:
        await asyncio.sleep(0.3)
        assert "#general" in server.channels
        assert "#dev" in server.channels
    finally:
        await transport.disconnect()


@pytest.mark.asyncio
async def test_buffers_incoming_messages(server, make_client):
    buf = MessageBuffer()
    transport = IRCTransport(
        host="127.0.0.1", port=server.config.port,
        nick="testserv-bot", user="bot", channels=["#general"], buffer=buf,
    )
    await transport.connect()
    await asyncio.sleep(0.3)
    human = await make_client(nick="testserv-ori", user="ori")
    await human.send("JOIN #general")
    await human.recv_all(timeout=0.3)
    await human.send("PRIVMSG #general :hello bot")
    await asyncio.sleep(0.3)
    msgs = buf.read("#general", limit=50)
    assert any(m.text == "hello bot" and m.nick == "testserv-ori" for m in msgs)
    await transport.disconnect()


@pytest.mark.asyncio
async def test_send_privmsg(server, make_client):
    buf = MessageBuffer()
    transport = IRCTransport(
        host="127.0.0.1", port=server.config.port,
        nick="testserv-bot", user="bot", channels=["#general"], buffer=buf,
    )
    await transport.connect()
    await asyncio.sleep(0.3)
    human = await make_client(nick="testserv-ori", user="ori")
    await human.send("JOIN #general")
    await human.recv_all(timeout=0.3)
    await transport.send_privmsg("#general", "hello human")
    response = await human.recv(timeout=2.0)
    assert "hello human" in response
    await transport.disconnect()


@pytest.mark.asyncio
async def test_send_join_part(server):
    buf = MessageBuffer()
    transport = IRCTransport(
        host="127.0.0.1", port=server.config.port,
        nick="testserv-bot", user="bot", channels=["#general"], buffer=buf,
    )
    await transport.connect()
    await asyncio.sleep(0.3)
    await transport.join_channel("#new")
    await asyncio.sleep(0.2)
    assert "#new" in server.channels
    await transport.part_channel("#new")
    await asyncio.sleep(0.2)
    assert "#new" not in server.channels
    await transport.disconnect()
