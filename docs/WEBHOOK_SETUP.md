# GitHub → Home Assistant Webhook Setup

This repository's build workflows (`build.yml`, `build-network-tools.yml`) POST a JSON payload to a Home Assistant
inbound webhook each time a build starts and each time it finishes. HA automations can react to those events to push
notifications, update sensors, or trigger follow-on actions (e.g. restart the add-on after an update).

## Why a webhook?

HA's `webhook` integration is the standard, no-auth-required receiver for HTTP POSTs. Triggering an automation from a
webhook costs zero add-on resources and survives reboots — the trigger is the inbound POST itself, not a running
listener process.

## Setup

### 1. Pick a webhook ID

Choose a long, unguessable string. This is the only "secret" — anyone who knows both your HA URL and the webhook ID can
fire the event. Recommended format: a random 32-character hex string.

```bash
openssl rand -hex 16
# e.g. 7f3c2b1a4e8d9f0c6a5b2d1e8f4c3a2b
```

### 2. Create the HA automation

In HA → Settings → Automations → Create automation → **Webhook** trigger.

```yaml
trigger:
  - platform: webhook
    webhook_id: 7f3c2b1a4e8d9f0c6a5b2d1e8f4c3a2b # your random ID
    allowed_methods:
      - POST
    local_only: false # must be reachable from the internet if GH Actions is in the cloud
```

#### Example: notify on every build

```yaml
action:
  - service: notify.persistent_notification
    data:
      title: "GH Build {{ trigger.json.addon }}: {{ trigger.json.event }}"
      message: >-
        {{ trigger.json.conclusion | default('started') }} {% if trigger.json.image_tag is defined %} — {{
        trigger.json.image_tag }} {% endif %} — actor {{ trigger.json.actor }} — run {{ trigger.json.run_url |
        default('#') }}
```

#### Example: tag a sensor with the latest version

```yaml
action:
  - service: mqtt.publish # or rest_command, input_text.set, etc.
    data:
      topic: "homeassistant/addons/{{ trigger.json.addon }}/version"
      payload: "{{ trigger.json.version }}"
      retain: true
```

### 3. Configure GitHub repository secrets

In your repository → Settings → Secrets and variables → Actions → New repository secret.

| Secret          | Value                                                                       |
| --------------- | --------------------------------------------------------------------------- |
| `HA_BASE_URL`   | `https://ha-nextgen.akentner.de` (no trailing slash, no `/api/webhook/...`) |
| `HA_WEBHOOK_ID` | the random string from step 1                                               |

`HA_WEBHOOK_SECRET` is supported in the script but unused by default — the simple webhook trigger has no built-in HMAC
validation. To enable signed requests, switch your HA automation to a custom integration that reads the `X-HA-Signature`
header.

### 4. Test the wiring

```bash
curl -X POST https://ha-nextgen.akentner.de/api/webhook/7f3c2b1a4e8d9f0c6a5b2d1e8f4c3a2b \
  -H "Content-Type: application/json" \
  -d '{"event":"test","addon":"manual","version":"0.0.0","arch":"amd64","conclusion":"success"}'
```

HA should fire the automation. If it doesn't:

- `local_only: false` is required for cloud GH Actions (GH IP ranges change; HA firewall rules may block them)
- Check the HA logbook for the `webhook_...` event
- Use HA → Developer Tools → Events to listen for `webhook_<id>`

## Payload schema

### Started event

```json
{
  "event": "started",
  "workflow": "Build & Release",
  "run_id": "12345678901",
  "run_number": "42",
  "actor": "akentner",
  "ref": "refs/tags/v1.0.0",
  "sha": "abc123...",
  "repository": "akentner/homeassistant-addons",
  "trigger": "push",
  "addon": "coding-assistants",
  "version": "1.0.0",
  "arch": "amd64",
  "started_at": "2026-06-28T12:00:00Z"
}
```

### Finished event

```json
{
  "event": "finished",
  "workflow": "Build & Release",
  "run_id": "12345678901",
  "run_number": "42",
  "actor": "akentner",
  "ref": "refs/tags/v1.0.0",
  "sha": "abc123...",
  "repository": "akentner/homeassistant-addons",
  "trigger": "push",
  "addon": "coding-assistants",
  "version": "1.0.0",
  "arch": "amd64",
  "conclusion": "success",
  "image_tag": "ghcr.io/akentner/homeassistant-addons/amd64-coding_assistants:1.0.0",
  "run_url": "https://github.com/akentner/homeassistant-addons/actions/runs/12345678901"
}
```

`conclusion` is one of: `success`, `failure`, `cancelled`, `skipped`. `image_tag` is the exact GHCR tag that was pushed
(or attempted) — feed it directly to a `docker pull` automation if you want to update HA add-on images without manual
intervention.

## Failure handling

`.github/scripts/notify-ha.sh` retries 3× with exponential backoff (1s, 2s, 4s) and never fails the workflow — a flaky
HA can never break a build. Notification failures are surfaced as `::warning::` annotations on the workflow run for
visibility.
