# OTEL Metrics Pillar (Server-Side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the metrics pillar of OTEL — 15 server-side instruments across 5 categories — so an operator can answer SLO questions about message throughput, federation health, client lifecycle, and trace-context hygiene from a Prometheus / Grafana Cloud / Tempo backend.

**Architecture:** New `culture/telemetry/metrics.py` mirrors `tracing.py`'s idempotency + no-op pattern. Public `MetricsRegistry` dataclass holds every instrument; `init_metrics(config)` returns one instance and is called next to `init_telemetry(config)` from `IRCd.__init__`. Per-category wiring touches the same span sites Plans 1+2 already established. Closes Plan 2's deferred `culture.trace.inbound` counter.

**Tech Stack:** OpenTelemetry SDK metrics (`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc` — already a dependency for traces, includes `OTLPMetricExporter`).

---

## Context

Plans 1 and 2 shipped the **traces** pillar of OTEL: server-side spans (Plan 1, PR #292, 8.2.0) and federation trace-context relay (Plan 2, PR #293, 8.3.0). Plan 3 adds the second pillar — **metrics** — for everything the server can measure: message flow, event throughput, federation health, client/session lifecycle, and trace-context hygiene.

After this plan ships, an operator with `otelcol-contrib` pointed at Prometheus / Grafana Cloud / etc. can answer: how many messages per second is the mesh moving, what's the federation relay latency, how many active links / clients / channels, what fraction of inbound peer traceparents were malformed, and how do command-duration histograms look per verb. This is the foundation for SLO dashboards on the mesh.

**Out of scope** (deferred to later plans, but already designed in the spec):

- Bot metrics (`culture.bot.invocations`, `culture.bot.webhook.duration`) → **Plan 6** (bot instrumentation).
- Audit sink metrics (`culture.audit.writes`, `culture.audit.queue_depth`) → **Plan 4** (audit JSONL sink).
- Harness LLM metrics (`culture.harness.llm.*`) → **Plan 5** (harness tracing).

Plan 3 instruments **15 server-side metrics across 5 categories**. The full catalog is in `docs/superpowers/specs/2026-04-24-otel-observability-design.md:109-150`; this plan implements the server-side subset. Plan 4/5/6 will each add their own metric registrations alongside the registry Plan 3 creates.

## Critical files to read before implementing

- `docs/superpowers/specs/2026-04-24-otel-observability-design.md:109-150` — the full metrics catalog with exact name/type/unit/labels.
- `docs/superpowers/plans/2026-04-25-otel-federation.md` — Plan 2 reference for tone, TDD discipline, two-stage review pattern, version-bump shape.
- `culture/telemetry/tracing.py` — pattern to mirror (idempotency snapshot, `enabled=False` no-op short-circuit, per-call tracer access). New `metrics.py` will use the same shape.
- `culture/telemetry/__init__.py` — re-exports for the public surface.
- `culture/agentirc/config.py:16-27` — `TelemetryConfig` dataclass; needs two new fields.
- `tests/conftest.py:328-344` — `tracing_exporter` fixture; pattern for the new `metrics_reader` fixture.
- `culture/agentirc/ircd.py:212-227` — `emit_event` (event metric site).
- `culture/agentirc/client.py:80-97, 124-147, 149-197, 714-760` — send/send_raw, _process_buffer, handle, dispatch, PRIVMSG delivery (most client-side metric sites).
- `culture/agentirc/server_link.py:132-225, 942-963` — send_raw, handle, _dispatch, relay_event (federation metric sites).
- `pyproject.toml:25-28` — current OTEL deps; `opentelemetry-exporter-otlp-proto-grpc` already includes `OTLPMetricExporter`, no new deps needed.

## Approach

### 1. `TelemetryConfig` — two new fields

In `culture/agentirc/config.py::TelemetryConfig`, add:

```python
metrics_enabled: bool = True
metrics_export_interval_ms: int = 10000
```

`metrics_enabled` is gated by the existing `enabled` (parent gate). Both must be true for the SDK to install. Default `True` matches `traces_enabled` symmetry — when telemetry is `enabled`, both pillars come up by default.

### 2. New module `culture/telemetry/metrics.py`

Mirror `tracing.py`'s shape:

```python
_CULTURE_METER_NAME = "culture.agentirc"
_initialized_for: dict | None = None
_meter_provider: MeterProvider | None = None
_registry: MetricsRegistry | None = None


def reset_for_tests() -> None:
    """Reset module state so each test gets a fresh provider. Test-only."""
    global _initialized_for, _meter_provider, _registry
    ...
    metrics._METER_PROVIDER = None  # type: ignore[attr-defined]


@dataclass
class MetricsRegistry:
    """All Plan-3 instruments, registered once during init_metrics(config).

    Plan 4/5/6 will extend by registering their own instruments alongside —
    Plan 3 owns server-side; later plans own audit / harness / bots.
    """
    # Message flow
    irc_bytes_sent: Counter
    irc_bytes_received: Counter
    irc_message_size: Histogram
    privmsg_delivered: Counter
    # Events
    events_emitted: Counter
    events_render_duration: Histogram
    # Federation
    s2s_messages: Counter
    s2s_relay_latency: Histogram
    s2s_links_active: UpDownCounter
    s2s_link_events: Counter
    # Clients & sessions
    clients_connected: UpDownCounter
    client_session_duration: Histogram
    client_command_duration: Histogram
    # Trace-context hygiene
    trace_inbound: Counter


def init_metrics(config: ServerConfig) -> MetricsRegistry:
    """Initialize MeterProvider + register instruments. Idempotent.

    Returns a MetricsRegistry. When telemetry is disabled or
    metrics_enabled is False, returns a no-op registry whose instruments
    are all silently bound to the no-op meter — call sites can record()
    unconditionally.
    """
    global _initialized_for, _meter_provider, _registry

    tcfg = config.telemetry
    snapshot = asdict(tcfg)
    if _initialized_for == snapshot and _registry is not None:
        return _registry

    if not tcfg.enabled or not tcfg.metrics_enabled:
        # No-op meter — instruments still satisfy the type, record() is a no-op.
        meter = metrics.get_meter(_CULTURE_METER_NAME)
        _registry = _build_registry(meter)
        _initialized_for = snapshot
        return _registry

    resource = Resource.create({...})  # service.name + service.instance.id
    exporter = OTLPMetricExporter(
        endpoint=tcfg.otlp_endpoint,
        timeout=tcfg.otlp_timeout_ms / 1000.0,
        compression=(None if tcfg.otlp_compression == "none" else tcfg.otlp_compression),
    )
    reader = PeriodicExportingMetricReader(
        exporter=exporter,
        export_interval_millis=tcfg.metrics_export_interval_ms,
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(_CULTURE_METER_NAME)
    _registry = _build_registry(meter)
    _initialized_for = snapshot
    _meter_provider = provider
    return _registry
```

`_build_registry(meter)` is a private function that calls `meter.create_counter(...)`, `meter.create_histogram(...)`, `meter.create_up_down_counter(...)` for each metric in the spec, with the names/units from the catalog. Single source of truth so name/unit drift is impossible.

Add to `culture/telemetry/__init__.py` `__all__`:

```python
"MetricsRegistry",
"init_metrics",
```

### 3. Test fixture `metrics_reader` in `tests/conftest.py`

Mirror `tracing_exporter`:

```python
@pytest_asyncio.fixture
async def metrics_reader():
    """In-memory metric reader for telemetry integration tests."""
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    _reset_metrics()  # parallel to _reset_telemetry()
    reader = InMemoryMetricReader()
    provider = SdkMeterProvider(
        resource=Resource.create({"service.name": "test"}),
        metric_readers=[reader],
    )
    metrics.set_meter_provider(provider)
    try:
        yield reader
    finally:
        _reset_metrics()
```

Tests assert via `reader.get_metrics_data()` → walk resource_metrics → scope_metrics → metrics → data points. Helpers `get_counter_value(reader, name, **attrs)`, `get_histogram_count(reader, name, **attrs)`, `get_up_down_value(reader, name, **attrs)` live in `tests/telemetry/_metrics_helpers.py` (parallel to `tests/telemetry/_fakes.py`).

### 4. Instrument wiring (per-category tasks)

Each task = wire one category + write its tests + commit. Categories are mostly independent (different files / different choke points), so they can land in any order; for code-review legibility we'll order them by impact.

**Order:**

1. Trace-context hygiene (`culture.trace.inbound`) — closes Plan 2's explicit deferral.
2. Events (`culture.events.emitted`, `culture.events.render.duration`) — single choke point in `IRCd.emit_event`.
3. Message flow (`culture.irc.bytes_*`, `culture.irc.message.size`, `culture.privmsg.delivered`) — touches `Client.send_raw`, `ServerLink.send_raw`, `_process_buffer` (both), and PRIVMSG delivery.
4. Clients & sessions (`culture.clients.connected`, `culture.client.session.duration`, `culture.client.command.duration`) — `Client.handle` entry/exit + command-span duration via OTEL's existing span timing.
5. Federation (`culture.s2s.messages`, `culture.s2s.relay_latency`, `culture.s2s.links_active`, `culture.s2s.link_events`) — `ServerLink._dispatch`, `relay_event`, `handle`, `_try_complete_handshake`, `_remove_link`.

### 4a. Trace-context hygiene metric — `culture.trace.inbound`

Increment after every `extract_traceparent_from_tags` call, with `result=<extract.status>` and `peer=<peer or "">` labels:

- `culture/agentirc/client.py::_dispatch` — peer is `""` (client-side; spec reserves the peer label for federation).
- `culture/agentirc/server_link.py::_dispatch` — peer is `self.peer_name or ""`.

Tests cover all four `result` values for both code paths (8 total, but consolidate to ~4 representative cases — the four states are already exhaustively tested for span attrs in Plan 2; metrics tests just verify the counter increments).

### 4b. Events metrics

In `IRCd.emit_event`:

- `events_emitted.add(1, {"event.type": event_type_str, "origin": "federated" if event.data.get("_origin") else "local"})` at span open.
- `events_render_duration.record(elapsed_ms, {"event.type": event_type_str})` after `_run_skill_hooks` + `_dispatch_to_bots` + `_surface_event_privmsg` (the actual rendering work — wrap with a `time.perf_counter()` stopwatch).

Test: emit N events, assert `events_emitted` counter == N with right labels and `events_render_duration` has N data points.

### 4c. Message-flow metrics

Sites:

- **`Client.send_raw`** (line 80–97): `irc_bytes_sent.add(len(line.encode("utf-8")) + 2, {"direction": "s2c"})` (the `+2` is `\r\n`).
- **`ServerLink.send_raw`** (line 132–143): `irc_bytes_sent.add(len(line) + 2, {"direction": "s2s"})`.
- **`Client._process_buffer`** (line 124–147): `irc_bytes_received.add(len(line.encode("utf-8")) + 2, {"direction": "c2s"})` per parsed line; `irc_message_size.record(len(...), {"verb": msg.command, "direction": "c2s"})`.
- **`ServerLink._process_buffer`** (line 152–160): same shape with `direction="s2s"`.
- **`_send_to_channel`** / **`_send_to_client`** (lines 714–760): `privmsg_delivered.add(1, {"kind": "channel", "channel": channel.name})` / `("kind": "dm")`.

Tests use the `metrics_reader` fixture and a single client + a single PRIVMSG, asserting expected counter increments.

### 4d. Clients & sessions

- **`Client.handle`** entry: `clients_connected.add(1, {"kind": kind})` where `kind` is heuristic; for v1 default `"human"` everywhere — Plan 5 (harness) and Plan 6 (bots) will refine the label.
- **`Client.handle`** exit (in `finally` of the existing session-span block): `clients_connected.add(-1, {"kind": kind})` and `client_session_duration.record(session_duration_s, {"kind": kind})`.
- **`Client._dispatch`**: wrap with `time.perf_counter()` to measure dispatch duration; `client_command_duration.record(elapsed_ms, {"verb": verb})` after the handler runs.

### 4e. Federation metrics

- **`ServerLink._dispatch`**: `s2s_messages.add(1, {"verb": verb, "direction": "inbound", "peer": self.peer_name or ""})`.
- **`ServerLink.relay_event`**: stopwatch around the dispatch+handler block; `s2s_relay_latency.record(elapsed_ms, {"event.type": event_type_str, "peer": self.peer_name or ""})`.
- **`ServerLink._try_complete_handshake`** (after `self._authenticated = True`): `s2s_links_active.add(1, {"peer": self.peer_name, "direction": "outbound" if self.initiator else "inbound"})` AND `s2s_link_events.add(1, {"peer": self.peer_name, "event": "connect"})`.
- **`ServerLink.handle`** finally: `s2s_links_active.add(-1, {"peer": self.peer_name or "", "direction": ...})` AND `s2s_link_events.add(1, {"peer": ..., "event": "disconnect"})` (only if `self._authenticated` was true — never-authenticated drops shouldn't decrement).
- **Auth-failure paths** in `_validate_peer_credentials` / `_handle_pass`: `s2s_link_events.add(1, {"peer": ..., "event": "auth_fail"})`.
- **Backfill choke points** in `_handle_backfill` start / `_handle_backfillend`: `s2s_link_events.add(1, {"peer": ..., "event": "backfill_start"|"backfill_complete"})`.

### 5. Documentation

Update `docs/agentirc/telemetry.md`:

- Add "What you get in 8.4.0" section listing the 15 new metrics with units and labels (the spec catalog can be referenced rather than duplicated; one-line bullet per metric is enough).
- Update "What's not in" to remove "Metrics pillar" and add a note that bot/audit/harness metrics are still upcoming.

Update `culture/protocol/extensions/tracing.md` "Inbound handling" section: cross-reference the new `culture.trace.inbound{result, peer}` metric (the protocol doc already mentions it as a future hook — Plan 2 left this dangling).

### 6. Version bump

`/version-bump minor` → `8.3.0` → `8.4.0`. Updates `pyproject.toml` and `CHANGELOG.md`.

## Files to modify / create

**New:**

- `culture/telemetry/metrics.py` — `init_metrics`, `MetricsRegistry`, `_build_registry`, `reset_for_tests`.
- `tests/telemetry/_metrics_helpers.py` — `get_counter_value(reader, name, **attrs)`, `get_histogram_count(reader, name, **attrs)`, `get_up_down_value(reader, name, **attrs)`.
- `tests/telemetry/test_metrics_init.py` — `init_metrics` idempotency, no-op when disabled, reset behavior.
- `tests/telemetry/test_metrics_trace_inbound.py` — `culture.trace.inbound` for both client and server_link dispatch, all four result values.
- `tests/telemetry/test_metrics_events.py` — `culture.events.*`.
- `tests/telemetry/test_metrics_irc.py` — bytes, message size, privmsg.delivered.
- `tests/telemetry/test_metrics_clients.py` — `clients_connected`, `client_session_duration`, `client_command_duration`.
- `tests/telemetry/test_metrics_s2s.py` — federation metrics.

**Modified:**

- `culture/agentirc/config.py` — add `metrics_enabled` + `metrics_export_interval_ms` to `TelemetryConfig`.
- `culture/telemetry/__init__.py` — re-export `MetricsRegistry`, `init_metrics`.
- `culture/agentirc/ircd.py` — call `init_metrics` next to existing `init_telemetry`; instrument `emit_event`.
- `culture/agentirc/client.py` — instrument `send_raw`, `_process_buffer`, `_dispatch`, `handle`, `_send_to_channel`, `_send_to_client`.
- `culture/agentirc/server_link.py` — instrument `send_raw`, `_process_buffer`, `_dispatch`, `relay_event`, `handle`, `_try_complete_handshake`, `_remove_link`-callsite, `_handle_backfill`, `_handle_backfillend`.
- `tests/conftest.py` — add `metrics_reader` fixture parallel to `tracing_exporter`.
- `culture/protocol/extensions/tracing.md` — cross-reference `culture.trace.inbound` metric.
- `docs/agentirc/telemetry.md` — "What you get in 8.4.0" section.
- `pyproject.toml`, `CHANGELOG.md` — version bump.

## Tests

Per-category tests live in `tests/telemetry/test_metrics_*.py`. Each test:

1. Uses `metrics_reader` fixture (and `linked_servers` for federation tests).
2. Triggers the instrumented behavior.
3. Asserts on `reader.get_metrics_data()` via the helpers.

Cross-category invariant: full suite runs in <60s. Metrics tests should be fast — no real OTLP export, just in-memory reader. New tests target ~25-30 cases.

## Verification

1. `bash ~/.claude/skills/run-tests/scripts/test.sh -p` — full suite green (current baseline: 992 + Plan 3 additions).
2. `bash ~/.claude/skills/run-tests/scripts/test.sh -p tests/telemetry/` — telemetry suite green.
3. Manual: start `otelcol-contrib` with the project's debug-exporter template; start a server with `telemetry.enabled: true` and `metrics_enabled: true`; connect weechat; send PRIVMSG; verify counters/histograms appear in collector debug output every `metrics_export_interval_ms`.
4. `Agent(subagent_type="doc-test-alignment", ...)` — flag any new public API (`MetricsRegistry`, `init_metrics`) not mentioned in `docs/`.
5. `Agent(subagent_type="superpowers:code-reviewer", ...)` on staged diff — `metrics.py` is a new public module + multiple shared choke-point edits, exactly the CLAUDE.md case for pre-push review.
6. `bash ~/.claude/skills/pr-review/scripts/pr-status.sh <PR>` after push — clean CI + SonarCloud quality gate.

## Out of scope (future plans)

- Bot metrics (`culture.bot.invocations`, `culture.bot.webhook.duration`) → Plan 6.
- Audit metrics (`culture.audit.writes`, `culture.audit.queue_depth`) → Plan 4.
- Harness LLM metrics (`culture.harness.llm.*`) → Plan 5.
- `culture.events.render.duration` per-skill breakdown — current scope only measures total render time per event; per-skill would need per-skill spans/metrics, deferred.
- Process / GC / memory metrics — collector-side `hostmetrics` receiver or `opentelemetry-instrumentation-system-metrics`; out-of-band of Culture proper.

## Carry-forward notes (for compaction / future plans)

- **MetricsRegistry pattern is extensible.** Plans 4/5/6 will register their own instruments alongside Plan 3's by extending `MetricsRegistry` (audit fields, harness fields, bot fields). Keep the registry a single dataclass and grow it — DON'T spawn parallel registries per category.
- **Config field naming.** `metrics_enabled` mirrors `traces_enabled` — Plan 4 should use `audit_enabled` (already in spec), Plan 5 `harness_metrics_enabled` (or similar — TBD when Plan 5 lands). Avoid abbreviations; keep parallelism with existing `*_enabled` fields.
- **No-op meter behavior.** When telemetry is disabled, `metrics.get_meter()` returns a no-op meter whose `create_counter` etc. return no-op instruments — `instrument.add(...)` becomes a free statement. This means call sites NEVER need `if registry is not None` guards; just call `registry.foo.add(...)` unconditionally. Same model as the no-op tracer pattern.
- **Idempotency snapshot.** Same `dataclasses.asdict(tcfg)` snapshot pattern as Plan 1 — needed because `TelemetryConfig` is mutable. Carry forward to Plan 4's `init_audit(config)` if it follows the same shape.
- **Plan 2's deferred `culture.trace.inbound` metric** finally lands here; the spec attribute (`culture.trace.dropped_reason`) on `_dispatch` spans already records the same data, but the counter is what dashboards typically scrape.
- **Test-suite runtime budget.** Adding 25-30 metrics tests must keep the suite under 60s. Use `linked_servers` only when federation metrics need it; for client/event tests use the lighter `server` fixture.
