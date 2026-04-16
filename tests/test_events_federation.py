"""Events federate across linked servers via SEVENT."""

import asyncio

import pytest

from culture.agentirc.skill import Event, EventType


@pytest.mark.asyncio
async def test_event_federates_to_peer(linked_servers, make_client_b):
    """An event on server A is surfaced on server B's #system."""
    alpha, _ = linked_servers

    b = await make_client_b("beta-bob", "bob")
    await b.send("CAP REQ :message-tags")
    await b.recv_until("CAP")
    await b.send("JOIN #system")
    await b.recv_until("JOIN")

    # Emit on alpha.
    ev = Event(
        type=EventType.AGENT_CONNECT,
        channel=None,
        nick="system-alpha",
        data={"nick": "alpha-claude"},
    )
    await alpha.emit_event(ev)

    line = await b.recv_until("event=agent.connect")
    # Origin in the nick is alpha, not beta.
    assert ":system-alpha!" in line
    assert "alpha-claude connected" in line


@pytest.mark.asyncio
async def test_federated_event_does_not_loop(linked_servers, make_client_a, make_client_b):
    """A federated event surfaces once on each side — no loop."""
    alpha, _ = linked_servers

    a = await make_client_a("alpha-alice", "alice")
    await a.send("CAP REQ :message-tags")
    await a.recv_until("CAP")
    await a.send("JOIN #system")
    await a.recv_until("JOIN")

    b = await make_client_b("beta-bob", "bob")
    await b.send("CAP REQ :message-tags")
    await b.recv_until("CAP")
    await b.send("JOIN #system")
    await b.recv_until("JOIN")

    await alpha.emit_event(
        Event(
            type=EventType.AGENT_CONNECT,
            channel=None,
            nick="system-alpha",
            data={"nick": "alpha-claude"},
        )
    )

    # Each side sees exactly one PRIVMSG line mentioning the event.
    a_count = await a.count_until_idle("event=agent.connect", seconds=1.0)
    b_count = await b.count_until_idle("event=agent.connect", seconds=1.0)
    assert a_count == 1
    assert b_count == 1


@pytest.mark.asyncio
async def test_server_link_in_event_log(linked_servers):
    """server.link events land in both servers' _event_log after handshake."""
    alpha, beta = linked_servers

    alpha_link_events = [e for (_, e) in alpha._event_log if e.type == EventType.SERVER_LINK]
    beta_link_events = [e for (_, e) in beta._event_log if e.type == EventType.SERVER_LINK]

    assert len(alpha_link_events) >= 1, "alpha should have at least one server.link event"
    assert len(beta_link_events) >= 1, "beta should have at least one server.link event"

    # The event on alpha should mention beta as peer
    alpha_peers = {e.data.get("peer") for e in alpha_link_events}
    assert "beta" in alpha_peers

    # The event on beta should mention alpha as peer
    beta_peers = {e.data.get("peer") for e in beta_link_events}
    assert "alpha" in beta_peers


@pytest.mark.asyncio
async def test_server_unlink_on_disconnect(linked_servers):
    """server.unlink is emitted when a peer link drops."""
    alpha, _ = linked_servers

    # Grab the link object and close it from alpha's side
    link = alpha.links["beta"]
    link.writer.close()
    try:
        await link.writer.wait_closed()
    except ConnectionError:
        pass

    # Wait for cleanup to propagate
    for _ in range(50):
        if "beta" not in alpha.links:
            break
        await asyncio.sleep(0.05)

    unlink_events = [e for (_, e) in alpha._event_log if e.type == EventType.SERVER_UNLINK]
    assert len(unlink_events) >= 1, "Expected server.unlink in alpha's event log"
    assert unlink_events[0].data.get("peer") == "beta"
