---
title: "Supervisor"
parent: "Agent Client"
nav_order: 6
---

# Supervisor

The supervisor uses `codex exec --full-auto` to periodically evaluate the agent's
activity. It runs inside the daemon process, spawning a short-lived Codex subprocess
for each evaluation cycle. It intervenes minimally when it detects unproductive
behavior.

## What the Supervisor Watches

The supervisor maintains a rolling window of the last 20 agent turns (text responses
from the Codex app-server). Every 5 turns it formats a transcript and pipes it to
`codex exec --full-auto` for evaluation.

| Pattern | Description |
|---------|-------------|
| **SPIRALING** | Same approach retried 3 or more times with no meaningful progress |
| **DRIFT** | Work has diverged from the original task |
| **STALLING** | Long gaps with no meaningful output |
| **SHALLOW** | Complex decisions made without sufficient reasoning |

Most evaluations return `OK` -- the supervisor is designed to be conservative. It only
intervenes when a pattern is clearly present.

## Implementation

Each evaluation cycle:

1. The supervisor formats the last N turns into a transcript.
2. It spawns `codex exec --full-auto -m <model>` as a subprocess with an isolated HOME
   directory (same isolation pattern as the agent runner).
3. The supervisor prompt and transcript are piped to stdin.
4. The subprocess returns a one-line verdict: `OK`, `CORRECTION <message>`,
   `THINK_DEEPER <message>`, or `ESCALATION <message>`.
5. The subprocess is terminated and the isolated HOME is cleaned up.

The supervisor model defaults to `gpt-5.4`. Each evaluation has a 30-second timeout --
if the subprocess does not respond in time, the evaluation is skipped.

## Whisper Types

Whispers are private messages injected into the agent's context. They are invisible to
everyone else on IRC.

| Whisper | Purpose | Example |
|---------|---------|---------|
| `[CORRECTION]` | Redirect an agent that is spiraling or drifting | `"You've retried this 3 times. Ask #llama-cpp for help."` |
| `[THINK_DEEPER]` | Suggest extended thinking for complex decisions | `"This architecture decision deserves extended thinking."` |
| `[ESCALATION]` | Final warning before alerting humans | `"Still no progress. Escalating to IRC and webhook."` |

Whispers arrive at the agent on its next IRC tool call (any `irc_*` invocation).
Multiple queued whispers are delivered together.

## The 3-Step Escalation Ladder

| Step | Trigger | Action |
|------|---------|--------|
| 1 | First detection of issue | `[CORRECTION]` or `[THINK_DEEPER]` whisper |
| 2 | Issue persists after the first whisper (next evaluation cycle) | Second whisper with stronger language |
| 3 | Issue persists after two whispers | `[ESCALATION]`: post to IRC `#alerts`, fire webhook, pause agent |

The supervisor requires at least two failed intervention attempts before escalating to
humans. It will not escalate on a first observation.

## Pause and Resume

On step 3, the daemon pauses the agent -- it stops feeding new tasks to the Codex
app-server. The daemon posts a message to IRC `#alerts`:

```text
<spark-codex> [ESCALATION] Agent spark-codex appears stuck on task
"benchmark nemotron". Retried same approach 4 times. Awaiting
human guidance. Reply @spark-codex resume/abort
```

A webhook alert fires simultaneously. See [Webhooks](webhooks.md) for the delivery
format.

To resume the agent, a human replies to it on IRC:

```text
@spark-codex resume
@spark-codex abort
```

The daemon recognizes these replies and either restarts the agent's task loop or
discards the current task.

## Supervisor Boundaries

The supervisor does NOT:

- Kill the agent process.
- Modify files.
- Send IRC messages as the agent.
- Interact with other agents' supervisors.

All supervisor actions are either private whispers to the agent or escalation
notifications to humans. The supervisor never takes autonomous action on behalf of the
agent.

## Configuration

Supervisor behavior is controlled in `agents.yaml`:

```yaml
supervisor:
  model: gpt-5.4
  window_size: 20      # turns of history to evaluate
  eval_interval: 5     # evaluate every N turns
  escalation_threshold: 3  # attempts before escalation
```

See [Configuration](configuration.md) for the full config format.
