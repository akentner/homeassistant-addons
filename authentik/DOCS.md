# Authentik Add-on Configuration

## Add-on Options

| Option                   | Default         | Description                                         |
| ------------------------ | --------------- | --------------------------------------------------- |
| `log_level`              | `info`          | Log verbosity: `debug`, `info`, `warning`, `error`  |
| `timezone`               | `Europe/Berlin` | Timezone for authentik and the bundled database     |
| `disable_startup_wizard` | `false`         | Skip the first-start setup wizard                   |
| `email_host`             | _(empty)_       | SMTP server hostname — leave empty to disable email |
| `email_port`             | `587`           | SMTP port                                           |
| `email_from`             | _(empty)_       | Sender address for outgoing email                   |
| `email_username`         | _(empty)_       | SMTP authentication username                        |
| `email_password`         | _(empty)_       | SMTP authentication password                        |
| `email_use_tls`          | `true`          | Use STARTTLS for SMTP                               |

## Bundled Services

This add-on runs three processes inside a single container:

| Service          | Description                                   | Port             |
| ---------------- | --------------------------------------------- | ---------------- |
| PostgreSQL       | Relational database for authentik data        | `127.0.0.1:5432` |
| Valkey           | Redis-compatible store for sessions and cache | `127.0.0.1:6379` |
| Authentik server | Web UI, REST API, SSO flows                   | `0.0.0.0:9000`   |
| Authentik worker | Background tasks, email delivery, scheduling  | _(internal)_     |

Neither PostgreSQL nor Valkey are reachable from outside the container.

## Persistent Data

All data is stored in the HA add-on persistent storage directory (mapped to `/data` in the container):

| Path                   | Contents                            |
| ---------------------- | ----------------------------------- |
| `/data/postgresql/`    | PostgreSQL database files           |
| `/data/postgresql.log` | PostgreSQL log file                 |
| `/data/.pg_password`   | Auto-generated database password    |
| `/data/.secret_key`    | Auto-generated authentik secret key |

**Do not delete these files.** The `.pg_password` and `.secret_key` files are generated once on first start and must
remain stable across restarts. Losing the secret key invalidates all tokens and sessions.

## Custom Configuration via `/addon_config`

The `/addon_config` directory (mapped from HA add-on config storage) is available inside the container. Use it to
provide custom blueprints or other authentik configuration files as needed.

## Reverse Proxy Setup

Authentik requires a stable external HTTPS URL for OAuth2/OIDC callback URLs.

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name auth.example.com;

    location / {
        proxy_pass http://<ha-ip>:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

After setting up the reverse proxy, configure the external URL in authentik: _Admin Interface → System → Settings →
"Authentik URL"_ → set to `https://auth.example.com`.

## First Login

On first start, authentik creates a default admin user:

- **Username:** `akadmin`
- **Password:** set during the setup wizard

If `disable_startup_wizard` is enabled, the wizard is skipped and a temporary password is generated. Check the add-on
log for the generated credentials.

## Backup

Back up the entire HA add-on storage directory (accessible via _Supervisor → Add-ons → Authentik → Backups_) or use the
standard HA backup functionality, which includes add-on data.
