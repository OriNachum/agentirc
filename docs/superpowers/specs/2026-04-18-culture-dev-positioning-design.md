# culture.dev positioning — Why Culture → What is Culture?

**Date:** 2026-04-18
**Status:** Approved
**Issue:** #267
**Scope:** Reframe culture.dev positioning away from "stateless vs persistent" contrast. Rename `why-culture.md` to `what-is-culture.md`, adjust `vision.md` to own the worldview axis, soften the persistence framing in `mental-model.md`, and establish a canonical positioning paragraph in `docs/resources/positioning.md`.

## Context

Issue #267 identifies a positioning problem: culture.dev's current "Why Culture" page opens with *"Culture exists because the current model for AI agents — isolated, ephemeral, single-task — doesn't match how real collaboration works"* and leads with *"Persistent, not ephemeral"*. That framing treats competitor agents (Codex, Claude Code, OpenClaw) as stateless one-shot tools — which they are not. All three persist context, all three can be taught. OpenClaw in particular externalizes memory and identity into files.

The stronger distinction Culture should be making is **not** about whether agents can persist or be taught. It is about:

1. **Professional workspace of specialized agents, not one growing individual agent.** The unit of design is the culture, not the single agent. "Professional" here inherits the meaning locked in the 7.1.3 hero — persistent (not ephemeral chat), production-grade (not toy demos), open/self-hosted (not vendor SaaS).
2. **Build-per-need, not have-everything-then-disable.** You compose the rooms, roles, and members you actually need.
3. **Teachability supports the workspace**, rather than serving as Culture's differentiator.

This spec makes those axes first-class on the site, reframes neighbor pages to match, and establishes a canonical positioning paragraph that can be reused across README, site meta, and LLM summarizers.

## Positioning axes (locked)

From the brainstorming session with the issue author:

**The canonical paragraph.** One block, reused verbatim in the new What-is-Culture page intro and in `docs/resources/positioning.md`:

> Culture is a professional workspace for specialized agents. Through AgentIRC, it provides the shared environment — rooms, presence, roles, coordination, and history that persists across sessions — where agents and humans work together. Harnesses are optional connectors: they let an agent stay present in the culture without being pushed to read every message, so participating in the workspace doesn't mean drowning in it.

The harness is deliberately framed as an attention layer, not a persistence layer. Persistence lives in the workspace (rooms, history, presence, roles survive across sessions) and — independently — in whatever memory or learning the agent itself carries.

**The OpenClaw reference paragraph.** Used verbatim in the Reference points section and in `docs/resources/positioning.md`:

> Systems like OpenClaw are useful reference points because they focus on the growth of an individual agent through files. Culture focuses instead on the workspace where specialized agents operate together. These are different models, not opposing ones.

**The Codex / Claude Code reference line.** Used verbatim in the Reference points section and in `docs/resources/positioning.md`:

> Codex and Claude Code are also useful reference points: they each have their own ways of persisting context and improving over time, but the center of gravity is still the individual agent or session flow rather than the culture as a workspace.

**Closing frame.** Two sentences at the end of Reference points:

> These are different shapes, not rivals. An agent that carries its own memory — built the OpenClaw way or with a skill that learns from each task — fits naturally in a culture; the workspace is a place for such agents to operate, not a replacement for what they already carry.

This closes the loop with #267's spirit: per-agent persistence is welcomed, not framed as a competitor to the workspace model.

## IA split (culture.dev)

| Page | Role | nav_order |
|---|---|---|
| `docs/culture/what-is-culture.md` (renamed from `why-culture.md`) | **What it is** — definition, unit of design, build-per-need, reference points | 1 |
| `docs/culture/vision.md` | **Where it's going** — broader social model, lifecycle, social contract, worldview | 2 |
| `docs/culture/mental-model.md` | Conceptual model (spaces, membership, persistence, reflection, organization) | unchanged |

`What is Culture?` is the definitional anchor; `Vision` is the longer-horizon expansion. Both sit under the "Vision & Patterns" sidebar group.

## Edit plan

### 1. Rename and rewrite `docs/culture/why-culture.md` → `docs/culture/what-is-culture.md`

**Frontmatter:**

```yaml
---
title: "What is Culture?"
parent: "Vision & Patterns"
nav_order: 1
sites: [culture]
description: Culture is a professional workspace for specialized agents. Here's what that means.
permalink: /what-is-culture/
redirect_from:
  - /why-culture/
---
```

**Body outline:**

```
# What is Culture?

<Intro paragraph — the canonical paragraph, verbatim from the
 Positioning axes section above.>

## A professional workspace for specialized agents

~4 sentences. Expand "professional workspace" concretely: rooms,
presence, roles, humans alongside. The subject is the group of
specialists, not a single smart agent. Key vocabulary: professional
workspace, members, specialists. Echo the 7.1.3 hero tagline; this
section is where the body text picks up the same word the visitor
already saw at the top of the site.

## The unit of design is the culture, not the single agent

~4 sentences. Build-per-need. You compose the rooms, roles, and members
you actually need; the system starts minimal and becomes more structured
as the culture grows. Positive framing, no competitor name-checking
here.

## Teachability supports the workspace

Two short paragraphs. First paragraph covers where continuity lives:
the workspace itself persists (rooms, history, presence, roles survive
across sessions, so new members join an ongoing context rather than a
blank slate), and the agent can bring its own persistence on top — a
skill that learns from each task, a memory system, per-project notes.
That belongs to the agent, and it fits naturally inside a culture.

Second paragraph: teachability is real and important, but it is not
what sets Culture apart. What sets Culture apart is the shared
professional workspace of specialized agents.

## Reference points

<OpenClaw paragraph, verbatim from Positioning axes section above.>

<Codex and Claude Code reference line, verbatim from Positioning axes
 section above.>

<Closing sentences:>
 These are different shapes, not rivals. An agent that carries its own
 memory — built the OpenClaw way or with a skill that learns from each
 task — fits naturally in a culture; the workspace is a place for such
 agents to operate, not a replacement for what they already carry.

<Closing relationship callout, three links:>
- For the broader model and where this is going → **Vision**.
- For the conceptual model (spaces, membership, reflection) → **Mental model**.
- For the capability list → **Features**.
```

**Tone rules for this page:**

- No "not X" framing where X describes another agent's shape. No "not ephemeral", "not one-shot", "not stateless".
- No "vs" or "compare" language.
- OpenClaw, Codex, and Claude Code are named only in the Reference points section.

### 2. `docs/culture/vision.md`

**Frontmatter:** keep `title: "Vision"`, `permalink: /vision/`. Update `nav_order` to `2` (was `1`).

**Body edits:**

| Current | Disposition |
|---|---|
| `# What is Culture?` (H1) | Change to `# The Culture vision` |
| First paragraph: *"Culture is a space where humans and AI agents live and work side by side. You decide what that space looks like."* | Remove the first sentence (migrates to `what-is-culture.md`). Keep the second as the lead into "You design the structure". |
| `## You design the structure` | Unchanged. |
| `## Members` | Unchanged. |
| `## The lifecycle` | Unchanged. |
| `## Why IRC?` | Unchanged. (IA question deferred — flagged in Out of scope.) |

### 3. `docs/culture/mental-model.md` — Persistence section

**Current:**

```
## Persistence

Messages, room state, and agent context survive restarts. An agent that crashes
and restarts picks up where it left off. Humans who reconnect see what they
missed.

This persistence is what makes ongoing collaboration possible — not one-shot
task execution, but work that continues over time.
```

**New:**

```
## Persistence

Messages, room state, and agent context survive restarts. An agent that crashes
and restarts picks up where it left off. Humans who reconnect see what they
missed.

Persistence gives agents a stable ongoing context for work, so they can continue
participating in the culture over time. It is one of the properties that helps
the workspace hold together across sessions.
```

No other sections of `mental-model.md` change.

### 4. `docs/resources/positioning.md` (new)

**Frontmatter:**

```yaml
---
title: "Positioning"
---
```

**Body outline:**

```
# Positioning

Canonical copy for the README, GitHub repo description, site meta,
and anywhere an LLM summarizer might ingest one paragraph about
Culture. Keep these blocks in sync with the site; this file is the
source of truth.

## The paragraph

<Canonical paragraph, verbatim from Positioning axes section above.>

## Reference points

<OpenClaw paragraph, verbatim.>

<Codex and Claude Code reference line, verbatim.>

## When to use which

- **Site meta description / short bios (≤160 chars):** the first sentence
  only — "Culture is a professional workspace for specialized agents."
- **README, GitHub "About", LLM summaries:** the full paragraph.
- **Comparison or positioning questions:** the full paragraph plus the
  Reference points block.
```

This file is not built into the site — `docs/resources/` is already in `_config.base.yml`'s `exclude:` list. It is a reference for human and agent editors of this repo.

### 5. Install `jekyll-redirect-from`

**`Gemfile`:** add one line after `gem "jekyll-sitemap"`:

```ruby
gem "jekyll-redirect-from"
```

**`_config.base.yml`:** add one entry to the `plugins:` list:

```yaml
plugins:
  - jekyll-seo-tag
  - jekyll-relative-links
  - jekyll-sitemap
  - jekyll-redirect-from
```

After `bundle install`, `uv.lock` is unaffected but `Gemfile.lock` will update — commit it.

## Verification

1. `bundle install` succeeds and adds `jekyll-redirect-from` to `Gemfile.lock`.
2. `bundle exec jekyll build --config _config.base.yml,_config.culture.yml --destination _site_culture` exits 0.
3. `markdownlint-cli2 "docs/culture/what-is-culture.md" "docs/culture/vision.md" "docs/culture/mental-model.md" "docs/resources/positioning.md"` reports no new violations.
4. On the built site, `/why-culture/` redirects to `/what-is-culture/` (the `redirect_from` entry generates a static redirect page).
5. On the built site, the "Vision & Patterns" sidebar shows **What is Culture?** above **Vision**.
6. Vision's H1 reads "The Culture vision", and the first paragraph no longer contains the sentence "Culture is a space where humans and AI agents live and work side by side."
7. Mental model's Persistence section no longer contains "not one-shot task execution".
8. The canonical paragraph in `docs/culture/what-is-culture.md` intro and `docs/resources/positioning.md` is character-identical. Same for the OpenClaw paragraph and the Codex / Claude Code reference line.
9. Grep gate before commit: running `grep -rn "not one-shot\|not ephemeral\|isolated, ephemeral" docs/culture/` returns zero hits. (`docs/agentirc/` and `docs/superpowers/plans/` hits are out of scope.)

## Rollout

- Branch: `docs/culture-positioning-267`.
- `/version-bump patch` → 7.1.5. Docs-only change; no code, protocol, CLI, or backend harness surface touched.
- Two commits recommended for review clarity, but one is acceptable:
  1. Rename `why-culture.md` → `what-is-culture.md`, rewrite body, install `jekyll-redirect-from`, update `vision.md` H1 and intro, bump `nav_order`.
  2. Rewrite `mental-model.md` Persistence section, add `docs/resources/positioning.md`.
- No `doc-test-alignment` agent invocation required: no new public API surface (no exceptions, CLI commands, IRC verbs, backend config fields).
- No pre-push code review required: no library or protocol code changed.
- SonarCloud check via `/sonarclaude` before marking the PR ready, per `CLAUDE.md`.

## Acceptance criteria (from #267), mapped

| Criterion | Where it is met |
|---|---|
| Site no longer implies competing agents are merely one-shot tools | Rewritten `what-is-culture.md` uses positive framing only; `mental-model.md` Persistence section softened; `why-culture.md` contents retired. |
| OpenClaw acknowledged as a stronger comparison target | Reference points section of `what-is-culture.md` names OpenClaw first; `docs/resources/positioning.md` mirrors it. |
| Readers can quickly understand what is unique about Culture | Intro paragraph + "A professional workspace for specialized agents" section deliver the answer in the first screen. |
| Explanation usable both for technical readers and LLM summarizers | `docs/resources/positioning.md` provides a canonical block; the page intro is character-identical to it. |

## Out of scope

- Moving or rewriting the `## Why IRC?` section of `vision.md`. Technical justification content; does not serve #267.
- Touching the just-shipped (7.1.3) homepage hero on `docs/culture/index.md`. The current copy is definitional, not adversarial.
- Updating `docs/agentirc/why-agentirc.md` (contains "not one-shot API calls"). Different site, different audience, different scope.
- Updating the root `README.md` to cite `docs/resources/positioning.md`. Worth doing as a follow-up PR; not blocking for #267.
- LLM-summarizer-specific tooling (schema.org metadata, `llms.txt`, etc.). `positioning.md` is the low-tech first step.
