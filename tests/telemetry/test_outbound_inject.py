import pytest

from culture.agentirc.client import Client
from culture.agentirc.config import ServerConfig, TelemetryConfig
from culture.agentirc.ircd import IRCd
from culture.protocol.message import Message
from culture.telemetry.context import TRACEPARENT_TAG


class _FakeWriter:
    def __init__(self):
        self.buf = []

    def get_extra_info(self, key, default=None):
        return ("testaddr", 12345) if key == "peername" else default

    def write(self, data):
        self.buf.append(data)

    async def drain(self):
        pass


@pytest.mark.asyncio
async def test_send_injects_traceparent_when_span_active(tracing_exporter):
    from opentelemetry import trace

    cfg = ServerConfig(name="spark", telemetry=TelemetryConfig(enabled=False))
    ircd = IRCd(cfg)
    client = Client(reader=None, writer=_FakeWriter(), server=ircd)  # type: ignore[arg-type]
    client.caps = {"message-tags"}
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("outer"):
        await client.send(Message(command="PRIVMSG", params=["#c", "hi"]))
    wire = client.writer.buf[0].decode()
    assert TRACEPARENT_TAG in wire


@pytest.mark.asyncio
async def test_send_raw_injects_traceparent_when_span_active(tracing_exporter):
    from opentelemetry import trace

    cfg = ServerConfig(name="spark", telemetry=TelemetryConfig(enabled=False))
    ircd = IRCd(cfg)
    client = Client(reader=None, writer=_FakeWriter(), server=ircd)  # type: ignore[arg-type]
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("outer"):
        await client.send_raw("PRIVMSG #c :hi")
    wire = client.writer.buf[0].decode()
    assert TRACEPARENT_TAG in wire


@pytest.mark.asyncio
async def test_send_no_injection_when_no_active_span(tracing_exporter):
    cfg = ServerConfig(name="spark", telemetry=TelemetryConfig(enabled=False))
    ircd = IRCd(cfg)
    client = Client(reader=None, writer=_FakeWriter(), server=ircd)  # type: ignore[arg-type]
    client.caps = {"message-tags"}
    # No active span → no injection
    await client.send(Message(command="PRIVMSG", params=["#c", "hi"]))
    wire = client.writer.buf[0].decode()
    assert TRACEPARENT_TAG not in wire
