# Gatus Add-on Configuration

## Add-on Options

| Option         | Default         | Description                                                          |
| -------------- | --------------- | -------------------------------------------------------------------- |
| `log_level`    | `info`          | Log verbosity: `debug`, `info`, `warning`, `error`                   |
| `storage_type` | `memory`        | Storage backend: `memory` (lost on restart) or `sqlite` (persistent) |
| `metrics`      | `false`         | Expose Prometheus metrics at `/metrics`                              |
| `timezone`     | `Europe/Berlin` | Timezone for scheduled checks and maintenance windows                |

## User Configuration File

Place your Gatus configuration at `/addon_config/config.yaml` on the HA host. This path maps to
`/usr/share/hassio/addons/data/local_gatus/` (or similar depending on your HA installation).

The add-on automatically merges the following fields from HA options — do **not** set them in your file:

- `web.port` — forced to `8099` for HA Ingress
- `web.address` — forced to `0.0.0.0`
- `storage` — controlled by `storage_type` and `storage_retention_days` options
- `metrics` — controlled by the `metrics` option

Everything else (`endpoints`, `alerting`, `ui`, `security`, `maintenance`) is taken from your file unchanged.

## Endpoints

```yaml
endpoints:
  - name: My Service
    url: https://myservice.example.com/health
    interval: 1m
    conditions:
      - "[STATUS] == 200"
      - "[RESPONSE_TIME] < 500"
      - "[BODY] == pat:*healthy*"
    alerts:
      - type: slack
```

### Supported endpoint types

| Type        | Example URL                  |
| ----------- | ---------------------------- |
| HTTP/HTTPS  | `https://example.com/health` |
| TCP         | `tcp://192.168.1.10:5432`    |
| ICMP (ping) | `icmp://192.168.1.1`         |
| DNS         | `dns://8.8.8.8?type=A`       |

## Alerting

Configure alert providers at the top level of your config:

```yaml
alerting:
  slack:
    webhook-url: "https://hooks.slack.com/services/xxx/yyy/zzz"
    default-alert:
      enabled: true
      failure-threshold: 2
      success-threshold: 1
      send-on-resolved: true

  discord:
    webhook-url: "https://discord.com/api/webhooks/xxx/yyy"

  email:
    from: "gatus@example.com"
    username: "gatus@example.com"
    password: "yourpassword"
    host: "smtp.example.com"
    port: 587
    to: "you@example.com"
```

Refer to [Gatus alerting documentation][alerting-docs] for all 40+ supported providers.

## SQLite Storage

When `storage_type: sqlite` is set, the database is stored at `/addon_config/gatus.db` which persists across add-on
restarts and is included in HA backups.

## Maintenance Windows

```yaml
maintenance:
  start: "23:00"
  duration: 1h
  timezone: "Europe/Berlin"
```

## UI Customization

```yaml
ui:
  title: "My Status Page"
  description: "Service health overview"
  logo: "https://example.com/logo.png"
  header: "Status"
  buttons:
    - name: "Home"
      link: "https://example.com"
```

[alerting-docs]: https://github.com/TwiN/gatus#alerting
