# Phase 23: coding-assistants: Claude Code + herdr (replaces tmux) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-10
**Phase:** 23-coding-assistants-claude-code-herdr-replaces-tmux
**Areas discussed:** herdr session model, Claude Code defaults & context, herdr-web-service ingress, plugin install & pinning

---

## herdr session model
| Option | Selected |
|---|---|
| One shared session (recommended) | ✓ |
| Separate sessions | |
| You decide | |

Keybindings: herdr defaults ✓ (alternatives: port prefix+splits; port everything).

## Claude Code defaults & context
TOOLS.md: marked block in ~/.claude/CLAUDE.md ✓ (alt: @import, none). Updates: `claude update` allowed, no settings defaults ✓ (alt: auto-updater off; settings option).

## herdr-web-service ingress
`/services/` ✓ (alt: `/herdr/`, you decide).

## Plugin install & pinning
Release binary + git clone @tag ✓ (alt: all from source). Plugin failure: warn and continue ✓ (alt: conditional activation). tmux removal: hard ✓ (alt: keep fallback).

## Claude's Discretion
ARG names, nginx details, bootstrap ordering.

## Deferred Ideas
None.
