"""Test configuration for tests/harness/.

Adds ``packages/agent-harness/`` to ``sys.path`` so tests can import the
reference modules (``telemetry``, ``config``) directly. This mirrors how a
cited backend copy works in practice — each backend owns its copy as a plain
Python module file, not as part of an installed package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Insert the agent-harness reference directory so tests can do:
#   from telemetry import init_harness_telemetry, ...
#   from config import DaemonConfig, TelemetryConfig, ...
_HARNESS_REF = str(Path(__file__).parent.parent.parent / "packages" / "agent-harness")
if _HARNESS_REF not in sys.path:
    sys.path.insert(0, _HARNESS_REF)
