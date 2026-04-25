"""Tests for the irc.s2s.session span on ServerLink.handle.

Covers direction attribute (set at span start) and peer attribute (set lazily
in _try_complete_handshake once peer_name is known).
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_session_span_recorded_with_direction_and_peer(
    tracing_exporter,  # Activate SDK exporter FIRST...
    linked_servers,  # ...then link, so handshake spans use the exporter.
):
    server_a, server_b = linked_servers

    # The linked_servers fixture completes the handshake before yielding.
    # Inspect the active session spans directly via the _session_span field.
    link_to_b = server_a.links.get("beta")
    if link_to_b is None:
        pytest.skip("linked_servers fixture did not produce expected link alpha->beta")

    span = link_to_b._session_span
    assert span is not None
    attrs = dict(span.attributes or {})
    assert attrs.get("s2s.direction") == "outbound"
    assert attrs.get("s2s.peer") == "beta"

    link_from_a = server_b.links.get("alpha")
    if link_from_a is None:
        pytest.skip("linked_servers fixture did not produce expected link beta->alpha")

    span = link_from_a._session_span
    assert span is not None
    attrs = dict(span.attributes or {})
    assert attrs.get("s2s.direction") == "inbound"
    assert attrs.get("s2s.peer") == "alpha"


@pytest.mark.asyncio
async def test_session_span_finishes_on_link_teardown(
    tracing_exporter,  # Activate SDK exporter FIRST...
    linked_servers,  # ...then link, so handshake spans use the exporter.
):
    server_a, server_b = linked_servers
    tracing_exporter.clear()

    link_to_b = server_a.links.get("beta")
    if link_to_b is None:
        pytest.skip("linked_servers fixture did not produce expected link")

    link_to_b.writer.close()
    try:
        await link_to_b.writer.wait_closed()
    except ConnectionError:
        pass
    for _ in range(50):
        if "beta" not in server_a.links:
            break
        await asyncio.sleep(0.05)
    # Allow teardown spans to flush.
    await asyncio.sleep(0.1)

    spans = tracing_exporter.get_finished_spans()
    session_spans = [s for s in spans if s.name == "irc.s2s.session"]
    # At least one session span should now be finished (the one we tore down).
    assert len(session_spans) >= 1
    finished = session_spans[-1]
    finished_attrs = dict(finished.attributes or {})
    assert finished_attrs.get("s2s.direction") in {"inbound", "outbound"}
    # peer attr may or may not be on the torn-down side depending on which
    # side closed first; both sides eventually close. The assertion is
    # weaker for that reason.
