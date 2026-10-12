---
status: testing
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
source: [23-VERIFICATION.md]
started: 2026-10-12T00:58:49Z
updated: 2026-10-12T00:58:49Z
---

## Current Test

number: 1
name: Services tab in a real browser behind HA ingress
expected: |
  /services/ loads inside the iframe under the ingress prefix, login with herdr_web_password works,
  roster and WebSocket work, no console errors
awaiting: user response

## Tests

### 1. Services tab in a real browser behind HA ingress
expected: /services/ loads in the iframe under the ingress prefix (no CSP frame block, no asset 404), login works, roster renders, WebSocket connects, no console errors
result: [pending]

### 2. claude update end to end, then container re-creation
expected: a newer version lands in /data/.local/share/claude/versions, ~/.local/bin/claude points to it, and the newer persisted version still wins over the image seed after re-creation
result: [pending]

### 3. subagent-watch opt-in setup inside herdr
expected: key binding / sidebar row appears and the viewer opens for a running Claude subagent
result: [pending]

### 4. Deleting the web-service auth.json
expected: POST /services/api/login answers 503 again without restarting the add-on
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
