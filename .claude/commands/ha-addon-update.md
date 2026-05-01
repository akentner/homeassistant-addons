---
name: ha-addon-update
description:
  Reload HA store and update a local add-on from this repo. Pass an add-on name as argument or omit for a menu.
argument-hint: "[addon-name]"
allowed-tools:
  - Bash
---

Update a Home Assistant add-on from this repository.

## Argument: `$ARGUMENTS`

### Add-ons in this repo

| Name                     | Slug                |
| ------------------------ | ------------------- |
| `coding-assistants`      | resolved at runtime |
| `fritz-callmonitor2mqtt` | resolved at runtime |
| `phone-logger`           | resolved at runtime |
| `meridian`               | resolved at runtime |

### Instructions

If `$ARGUMENTS` is empty, print the table above and ask the user which add-on to update.

Otherwise, match `$ARGUMENTS` (case-insensitive, handle partial names) to one of the add-ons above.

**Step 1 — Reload store:**

```bash
ha store reload 2>&1
```

**Step 2 — Resolve the slug dynamically:**

```bash
ha apps list 2>&1 | grep -A2 -i "<addon-name>"
```

Extract the `slug:` field from the output.

**Step 3 — Trigger the update:**

```bash
ha apps update <slug> 2>&1
```

After each command, print the output. If the update starts in the background, confirm with the background job ID. If no
update is available, say so clearly.
