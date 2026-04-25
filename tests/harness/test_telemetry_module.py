"""Unit tests for packages/agent-harness/telemetry.py.

Tests are isolated — no IRCd, no real OTLP exporter. Each test resets all
global OTEL provider state via ``reset_for_tests()`` before and after so
parallel xdist workers don't leak providers.
"""

from __future__ import annotations

import pytest

# Imported via sys.path set in conftest.py
# pylint: disable=import-error
from config import AgentConfig, DaemonConfig, ServerConnConfig, TelemetryConfig
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider as SdkMeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from telemetry import (
    HarnessMetricsRegistry,
    init_harness_telemetry,
    record_llm_call,
    reset_for_tests,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset all OTEL globals before and after every test."""
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def disabled_config():
    """DaemonConfig with telemetry disabled (default)."""
    return DaemonConfig()


@pytest.fixture
def harness_metrics_reader():
    """Install an InMemoryMetricReader against a fresh SdkMeterProvider.

    Returns the reader so tests can call ``reader.get_metrics_data()``.
    Resets harness module state before install and after teardown.
    """
    reset_for_tests()
    reader = InMemoryMetricReader()
    provider = SdkMeterProvider(
        resource=Resource.create({"service.name": "test-harness"}),
        metric_readers=[reader],
    )
    otel_metrics.set_meter_provider(provider)
    yield reader
    reset_for_tests()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_counter_sum(reader, metric_name: str) -> float:
    """Sum all data point values for a counter metric across all attributes."""
    data = reader.get_metrics_data()
    if data is None:
        return 0.0
    total = 0.0
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == metric_name:
                    for dp in m.data.data_points:
                        total += dp.value
    return total


# ---------------------------------------------------------------------------
# test_init_disabled_returns_noop_tracer_and_proxy_registry
# ---------------------------------------------------------------------------


def test_init_disabled_returns_noop_tracer_and_proxy_registry(disabled_config):
    """Disabled telemetry yields a no-op tracer and a registry that doesn't raise."""
    tracer, registry = init_harness_telemetry(disabled_config)

    # Tracer should be a proxy / no-op — starting a span yields a NonRecordingSpan.
    with tracer.start_as_current_span("test-span") as span:
        assert not span.is_recording()

    # All 4 instruments present on the registry.
    assert isinstance(registry, HarnessMetricsRegistry)
    assert registry.llm_tokens_input is not None
    assert registry.llm_tokens_output is not None
    assert registry.llm_call_duration is not None
    assert registry.llm_calls is not None

    # Calls on proxy instruments must not raise.
    registry.llm_calls.add(1, {"backend": "test", "model": "m", "outcome": "success"})
    registry.llm_call_duration.record(10.0, {"backend": "test", "model": "m", "outcome": "success"})
    registry.llm_tokens_input.add(5, {"backend": "test", "model": "m", "harness.nick": "n"})
    registry.llm_tokens_output.add(3, {"backend": "test", "model": "m", "harness.nick": "n"})


# ---------------------------------------------------------------------------
# test_init_idempotent
# ---------------------------------------------------------------------------


def test_init_idempotent(disabled_config):
    """Calling init twice with same config returns the same tracer + registry."""
    tracer1, registry1 = init_harness_telemetry(disabled_config)
    tracer2, registry2 = init_harness_telemetry(disabled_config)

    assert tracer1 is tracer2
    assert registry1 is registry2


# ---------------------------------------------------------------------------
# test_init_reinit_on_config_change
# ---------------------------------------------------------------------------


def test_init_reinit_on_config_change():
    """Mutating TelemetryConfig triggers fresh provider install on next call."""
    tcfg = TelemetryConfig(enabled=False)
    config = DaemonConfig(telemetry=tcfg)

    tracer1, registry1 = init_harness_telemetry(config)

    # Mutate config — snapshot diff should force reinit.
    tcfg.metrics_export_interval_ms = 1000

    tracer2, registry2 = init_harness_telemetry(config)
    assert registry1 is not registry2


# ---------------------------------------------------------------------------
# test_init_with_metrics_reader_records_calls
# ---------------------------------------------------------------------------


def test_init_with_metrics_reader_records_calls(harness_metrics_reader):
    """When a real MeterProvider is pre-installed, record_llm_call records data."""
    # Build a config that would be disabled so init_harness_telemetry uses the
    # proxy meter pointing at the already-installed test MeterProvider.
    config = DaemonConfig()
    _tracer_obj, registry = init_harness_telemetry(config)

    record_llm_call(
        registry,
        backend="claude",
        model="claude-opus-4-6",
        nick="spark-claude",
        usage=None,
        duration_ms=42.0,
        outcome="success",
    )

    assert _get_counter_sum(harness_metrics_reader, "culture.harness.llm.calls") == 1.0


# ---------------------------------------------------------------------------
# test_reset_for_tests_clears_globals
# ---------------------------------------------------------------------------


def test_reset_for_tests_clears_globals(disabled_config):
    """After reset_for_tests() all module globals are None and OTEL unset."""
    import telemetry as _tel_module

    init_harness_telemetry(disabled_config)

    # After reset: module globals cleared.
    reset_for_tests()
    assert _tel_module._initialized_for is None
    assert _tel_module._tracer is None
    assert _tel_module._meter_provider is None
    assert _tel_module._registry is None

    # OTEL trace provider unset.
    assert trace._TRACER_PROVIDER is None  # type: ignore[attr-defined]

    # OTEL metrics provider unset.
    import opentelemetry.metrics._internal as _mi  # type: ignore[attr-defined]

    assert _mi._METER_PROVIDER is None


# ---------------------------------------------------------------------------
# test_nick_identity_from_agents
# ---------------------------------------------------------------------------


def test_nick_identity_from_agents():
    """When agents list is non-empty, identity is built from agent nicks."""
    config = DaemonConfig(
        agents=[AgentConfig(nick="spark-claude"), AgentConfig(nick="spark-daria")],
    )
    tracer, registry = init_harness_telemetry(config)
    assert tracer is not None
    assert registry is not None


# ---------------------------------------------------------------------------
# test_nick_identity_from_server_name
# ---------------------------------------------------------------------------


def test_nick_identity_from_server_name():
    """When agents list is empty, identity falls back to server.name."""
    config = DaemonConfig(server=ServerConnConfig(name="mytestserver"))
    tracer, registry = init_harness_telemetry(config)
    assert tracer is not None
    assert registry is not None
