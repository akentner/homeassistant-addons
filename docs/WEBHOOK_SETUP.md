# GitHub → Home Assistant Webhook Setup

This repository's build workflows (seven per-addon `build-<addon>.yml` callers, each invoking the reusable
`_build-template.yml`) POST a JSON payload to a Home Assistant inbound webhook each time a build starts and each time
it finishes. The caller invokes `.github/scripts/notify-ha.sh` from both steps, so the receiving HA automation sees
two events per leg (one `started`, one `finished`). HA automations can react to those events to push notifications,
update sensors, or trigger follow-on actions (e.g. restart the add-on after an update).

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

| Secret                   | Value                                                                       | Required |
| ------------------------ | --------------------------------------------------------------------------- | -------- |
| `HA_BASE_URL`            | `https://ha-nextgen.akentner.de` (no trailing slash, no `/api/webhook/...`) | yes      |
| `HA_WEBHOOK_ID`          | the random string from step 1                                               | yes      |
| `CF_ACCESS_CLIENT_ID`    | Cloudflare Access service-token Client ID                                   | optional |
| `CF_ACCESS_CLIENT_SECRET`| Cloudflare Access service-token Client Secret                               | optional |

The webhook has no HMAC or payload signature. Its only secret is the webhook ID itself, so use a long random value.
Transport-level protection comes from Cloudflare Access (see below), which is what prevents the path from being
triggerable by anyone who guesses the URL.

The two `CF_ACCESS_*` secrets are required when `HA_BASE_URL` sits behind Cloudflare Access — a GitHub runner always
takes the public path and gets a 302 to the Access login if the headers are absent. When either is unset the script
omits the headers entirely so LAN / split-horizon callers keep working unauthenticated.

### 4. Test the wiring

```bash
curl -X POST https://ha-nextgen.akentner.de/api/webhook/7f3c2b1a4e8d9f0c6a5b2d1e8f4c3a2b \
  -H "Content-Type: application/json" \
  -d '{"event":"test","addon":"manual","version":"0.0.0","arch":"amd64","conclusion":"success"}'
```

HA should fire the automation. If it doesn't:

- `local_only: false` is required for cloud GH Actions (GH IP ranges change; HA firewall rules may block them)
- If HA is behind Cloudflare Access, the unauthenticated `curl` above will get a 302 to the Access login instead of
  reaching HA — see the next section for the verification recipe
- A `200` from HA does **not** prove the event was processed. HA returns 200 for any POST to `/api/webhook/<id>`,
  registered or not. The reliable signal is the automation's `last_triggered` advancing, or Developer Tools → Events
  listening for `webhook_<id>` and showing the payload
- Check the HA logbook for the `webhook_...` event

## Cloudflare Access

Cloudflare Access fronts this HA instance on the public hostname. The webhook path is not exempt — an unauthenticated
POST from the internet is redirected to a login page instead of reaching HA. Build notifications have failed silently
in this state (the script catches the failure, logs a warning, and exits 0) since the secrets were first created on
2026-06-28. The fix is a Cloudflare Access Service Token; a Bypass policy is **not** acceptable and is rejected below.

### Why this matters here

DNS is split-horizon:

| Resolver           | Result                        | Path                          |
| ------------------ | ----------------------------- | ----------------------------- |
| local (`getent`)   | `192.168.178.3`               | LAN, direct to HA             |
| public (`1.1.1.1`) | `188.114.96.3`/`188.114.97.3` | Cloudflare edge, Access-gated |

A GitHub runner always resolves the public record and hits the Cloudflare edge. From the LAN, `curl` to the same
hostname reaches HA directly. A local test will succeed even when the runner is failing.

### Failure signature to recognise

An unauthenticated POST to the webhook path returns a 302 to the Cloudflare Access login:

```text
HTTP/2 302
location: https://akentner.cloudflareaccess.com/cdn-cgi/access/login/ha-nextgen.akentner.de?kid=…
www-authenticate: Cloudflare-Access resource_metadata="…/.well-known/cloudflare-access-protected-resource/api/webhook/…"
```

The decoded JWT `meta` payload (visible at the `kid=` query parameter after base64-decoding the middle segment) carries
`"auth_status":"NONE"` and `"service_token_status": false`. If you see this in `.github/scripts/notify-ha.sh` output,
the CF headers are missing.

### The fix — separate Access app + Service Auth policy

Create a **second** Cloudflare Access application, scoped to `ha-nextgen.akentner.de/api/webhook/*`, with a single
`Service Auth` policy that grants access to a fresh Service Token. Leave the existing hostname-wide application and
its human-facing policies alone. Cloudflare resolves the most specific path match first, so the narrow app wins for
webhook requests only.

Why not a Bypass policy on the existing app: the webhook has no HMAC, so a Bypass would make the path
world-triggerable. That is a security downgrade from the protected state — the script's own header calls this out as
"not acceptable for public exposure". Service Auth + per-token credentials keeps the path gated while letting the
runner through.

Generate the token from Zero Trust → Access → Service Auth → Create Service Token. The two values Cloudflare shows
become `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` in the GitHub repository secrets table above.

The script then sends both as request headers (note the hyphenated form, not the env-var form):

```text
CF-Access-Client-Id:     <CF_ACCESS_CLIENT_ID>
CF-Access-Client-Secret: <CF_ACCESS_CLIENT_SECRET>
```

### Verification recipe

The `--resolve` flag forces the public IP regardless of the local resolver, so the test exercises the same path the
runner takes.

Negative probe — without CF headers, must return 302 to the login page:

```bash
curl -sS -o /dev/null -D - --resolve ha-nextgen.akentner.de:443:188.114.97.3 \
    -X POST https://ha-nextgen.akentner.de/api/webhook/nonexistent-probe-20310 -d '{}'
# Expect: HTTP/2 302
# Expect: location: https://akentner.cloudflareaccess.com/cdn-cgi/access/login/ha-nextgen.akentner.de?kid=…
```

Positive probe — with CF headers, must return 2xx (HA returns 200 for any webhook ID, registered or not):

```bash
curl -sS -o /dev/null -D - --resolve ha-nextgen.akentner.de:443:188.114.97.3 \
    -H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" \
    -H "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET" \
    -X POST https://ha-nextgen.akentner.de/api/webhook/nonexistent-probe-20310 -d '{}'
# Expect: HTTP/2 200
```

If the negative probe returns 200, the Access app is not actually scoped to `/api/webhook/*` (most common cause: scope
was set to the hostname rather than the path). If the positive probe returns 302, the Service Token is not attached
to the Service Auth policy, or the `kid` query parameter does not match the Access app the policy lives in.

A 200 response only proves the request traversed Access and reached HA. It does not prove the automation ran. After a
real build, confirm the receiving automation's `last_triggered` advanced, or watch Developer Tools → Events for
`webhook_<HA_WEBHOOK_ID>`.

## Payload schema

### Started event

```json
{
  "event": "started",
  "workflow": "Build Coding Assistants",
  "run_id": "12345678901",
  "run_number": "42",
  "actor": "akentner",
  "ref": "refs/heads/main",
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
  "workflow": "Build Coding Assistants",
  "run_id": "12345678901",
  "run_number": "42",
  "actor": "akentner",
  "ref": "refs/heads/main",
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

The `ref` value is `refs/heads/main` for the common case (a `paths:` push to `main` under `<addon>/**`) and
`refs/tags/<addon>/v<version>` when the build was triggered by a tag push — see `.github/RELEASE.md` for which add-ons
have the tag-trigger currently enabled.

`conclusion` is one of: `success`, `failure`, `cancelled`, `skipped`. `image_tag` is the exact GHCR tag that was pushed
(or attempted) — feed it directly to a `docker pull` automation if you want to update HA add-on images without manual
intervention.

## Failure handling

`.github/scripts/notify-ha.sh` is intentionally non-blocking: a notification failure can never fail a build. Three
mechanisms in order of preference:

- **3xx (auth-proxy redirect) — fail fast.** A redirect from a Cloudflare or other auth proxy is structurally never
  transient. The script logs an actionable warning naming the Access policy to check and exits. There is no retry and
  no backoff: three identical attempts against a permanent misconfiguration would burn ~7 s and bury the signal.
- **5xx / connect errors — three retries with exponential backoff** (1 s, 2 s, 4 s). Genuinely transient failures
  (HA rebooting, broker flapping, brief DNS hiccup) recover inside this window. The response body is logged for the
  last attempt so the next reader does not have to re-derive what the server actually said.
- **Always `exit 0`.** Every path ends with `exit 0` so a flaky HA cannot break a build. Notification failures are
  surfaced as `::warning::` annotations on the workflow run for visibility — they do not turn the run red.
