---
created: 2026-11-17
title: Evaluate herdr-tty for mobile browser usability
area: coding-assistants
status: deferred
files:
  - coding-assistants/index.html
  - coding-assistants/run.sh
  - coding-assistants/nginx.conf
  - coding-assistants/Dockerfile
---

## Future feature candidate

Consider [herdr-tty](https://github.com/dark2momo/herdr-tty) for improvements to the Coding Assistants browser
terminal, especially on phones and tablets. Recorded at the user's request on 2026-11-17; no migration is scheduled.
Keep the current ttyd/herdr integration for now.

## Potential benefits

- Touch scrolling with inertia, long-press selection and two-finger right-click.
- Better viewport handling when the virtual keyboard opens or closes, including iOS/iPad behavior.
- A mobile input/paste toolbar with explicit input and Escape controls.

Evaluate selective reuse of the MIT-licensed frontend improvements as well as adopting the complete application.
Preserve license notices if code is reused.

## Findings to retain

- In the source reviewed on 2026-11-17, copying uses `window.term.getSelection()` and touch selection simulates Shift.
  It therefore selects the rendered terminal screen and can include herdr UI. It does not replace pane-only copying
  through herdr's OSC 52 output.
- Keyboard events are largely passed through unchanged; adopting it alone does not fix Shift+Enter in Codex.
- Assets use root-absolute paths such as `/_herdr/mobile.js`. HA ingress subpaths require adaptation and verification.
- The complete application adds a Go gateway with its own authentication and ttyd lifecycle. Assess whether this is
  useful alongside HA ingress authentication and the existing nginx/attach wrapper before replacing them.

## Before implementation

Verify mobile keyboard and paste behavior, pane-only copying, ingress assets and WebSocket routing, and attachment to
the same persistent herdr session used by SSH. Retain existing terminal appearance options and test on actual mobile
browsers. Recheck upstream behavior when revisiting this candidate; the findings above describe the reviewed version.
