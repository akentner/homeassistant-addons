# ntfy add-on documentation

This add-on runs the upstream [ntfy][ntfy] server and an ingress-only admin GUI for users, ACL rules and tokens.

## Install and first start

1. Install the add-on, set `base_url` to the public address of your server and `admin_password` to a strong password.
2. Start the add-on. ntfy starts first. The admin from `admin_user` and `admin_password` and the baseline are created by
   a bootstrap step a few seconds later (the log line `[bootstrap] done` marks the end). Until then the user list can be
   empty, and ntfy already delivers messages.
3. Open the **ntfy** panel in the Home Assistant sidebar and manage users, rules and tokens there.

If `admin_password` is empty, no admin is created and the log says so. Set it and restart the add-on.

## Options

`listen_port`, `reset_data` and `users` do not exist in this add-on (see the migration guide below).

| Option                         | Type     | Default                    | Effect                                      |
| ------------------------------ | -------- | -------------------------- | ------------------------------------------- |
| `base_url`                     | url      | `https://ntfy.example.com` | Public URL for links, attachments, web app  |
| `enable_web_ui`                | bool     | `true`                     | Web app on `/`, `false` disables            |
| `behind_proxy`                 | bool     | `true`                     | Trust `X-Forwarded-For` of the proxy        |
| `auth_default_access`          | list     | `deny-all`                 | Access on topics without a matching rule    |
| `admin_user`                   | string   | `admin`                    | Admin account, created when missing         |
| `admin_password`               | password | empty                      | Only creates the admin, never overwrites    |
| `baseline_users`               | list     | empty                      | Users and optional rules, additive          |
| `baseline_overwrite_passwords` | bool     | `false`                    | Set baseline passwords again at every start |
| `backup_keep`                  | int      | `10`                       | `auth.db` backups to keep (1 to 100)        |
| `cache_duration`               | string   | `12h`                      | How long messages are cached                |
| `attachments_enabled`          | bool     | `true`                     | Allow attachments                           |
| `attachment_total_size_limit`  | string   | `1G`                       | Total attachment storage                    |
| `attachment_file_size_limit`   | string   | `15M`                      | Maximum size of one attachment              |
| `attachment_expiry_duration`   | string   | `12h`                      | How long attachments are kept               |
| `log_level`                    | list     | `info`                     | Log verbosity of ntfy                       |

Each `baseline_users` entry has `username`, `password`, `topic` and `write_access`, exactly like the `users` list of the
old add-on.

## Network and reachability

- The add-on uses the bridge network (`host_network: false`). ntfy listens on container port 8000, which is not
  published on the host by default. You can map a host port in the add-on's network settings in the HA UI.
- Inside the Home Assistant network, ntfy is reachable as `72a005f5-ntfy:8000`. Point Cloudflared or Traefik at this
  address.
- The admin GUI listens on the ingress port 8099 and is available only through the HA sidebar, not from the LAN.

## Baseline and origins

- The baseline is applied additively at every start through the ntfy CLI and never deletes anything. A baseline user is
  created when missing. The password of an existing user is not changed unless `baseline_overwrite_passwords` is `true`
  (default `false`); then the baseline password is set again at every start. Nothing is created or deleted by that, and
  users that the baseline does not name are never affected.
- For an entry with a non-empty `topic`, the rule `rw` (`write_access: true`) or `ro` is set when no rule exists for
  that user and topic. It is synced again at each start while the rule still has the origin `options`. A rule created or
  edited in the GUI has the origin `gui` and is left alone. An empty `topic` creates only the user.
- Entries removed from the options are not deleted. Their origin becomes `gui` at the next start.
- A baseline entry that names `admin_user` is ignored with a warning.
- The admin from `admin_user` and `admin_password` is created only when missing. A password changed in the GUI is never
  overwritten, and `baseline_overwrite_passwords` does not affect the admin.
- Origins are kept in the sidecar file `/data/origins.json`. `gui` and `options` are written by this add-on, `iac` is
  reserved for a later infrastructure-as-code phase and never written yet. Entries without a record, for example created
  with the ntfy CLI, count as `gui`.

## Admin GUI guide

- **Users**: role, tier, token count and origin. Create users, change passwords, promote or demote.
- **ACL rules**: per topic and user, including `everyone` and wildcards such as `alerts-*`. A topic x user matrix shows
  all rules at a glance.
- **Tokens**: create with a label and an optional expiry, revoke, reveal a value on demand.
- **Effective rights**: pick a user and a topic and see what ntfy would allow, and why.
- **Topic generator**: creates a random 16-character topic and sets the default rules, `homeassistant` read-write and
  `akentner` read-only.
- **Health**: status, database size and schema version, and a test publish.
- **Export**, **backups** and **reset actions** are described below.

### Guardrails

- The last admin and the `admin_user` from the options cannot be deleted or demoted. Changing their password is allowed.
- Deleting a user needs the user name typed as confirmation.
- Promoting a user to admin drops their explicit rules, because admins can do everything. The rules are stashed and
  restored on demotion. A backup is created first.

### Backups

- Backups live in `/data/backups` and are named `auth-<UTC timestamp>-<reason>.db`. The reasons are `daily`, `manual`,
  `user-delete`, `role-change`, `reset-acls`, `clear-cache` and `reset-everything`.
- One backup is made daily at start (at most one per UTC day), one before user deletion, one before a promotion to admin
  that drops rules, and one before every reset. `manual` backups are created with the button in the GUI.
- Rotation runs after each new backup and keeps the newest `backup_keep` backups of all reasons, so many manual backups
  can push out the daily one. Backups can be downloaded in the GUI.
- Backups contain password hashes and clear-text tokens. Treat them like the database itself.

### Reset actions

Reset actions replace the `reset_data` option of the old add-on. Each one needs a typed confirmation phrase and writes a
backup first.

| Phrase             | Effect                                                                          |
| ------------------ | ------------------------------------------------------------------------------- |
| `reset acls`       | Removes all ACL rules. Baseline rules return at the next start                  |
| `clear cache`      | Deletes the cached messages and attachment files while ntfy keeps running       |
| `reset everything` | Removes all users and rules, then recreates admin and baseline from the options |

- `reset acls` leaves users, tokens and passwords untouched. The origin of the removed rules is forgotten.
- `reset everything` also forgets all origins and tokens. The admin and the baseline users get the passwords from the
  options again, so passwords changed in the GUI are gone. It is refused while `admin_password` is empty.

### Tokens

- Lists never contain token values. A value is revealed per row on demand (a POST request).
- A new token shows its value once at creation and can be revealed again later.
- "Last used" is approximate, because ntfy updates it lazily.
- Revoking a token passes it as a command argument for a moment inside the container.
- Label and expiry are set at creation.

### Effective rights

The lookup follows ntfy: the admin role may do everything. For other users, the user's own matching rules beat rules for
`everyone`, then the longest pattern wins, then write-capable rules first. When nothing matches, `auth_default_access`
applies. Matching is case-sensitive: `pub*` does not match `PUB1`.

### Test publish

The test publish creates a two-minute token for `admin_user`, publishes one real message and removes the token. The
result is `ok` with the HTTP status of ntfy. A rate limit of ntfy shows as `ok: false` with status 429, and an
unreachable ntfy as `ok: false` with status 0.

## Export

The GUI exports the current state as YAML or JSON in one versioned format (schema 1, see
[docs/EXPORT_SCHEMA.md](docs/EXPORT_SCHEMA.md) in the add-on directory of the repository). By default it has no secrets:
users with role and tier, ACL rules, token metadata. Password hashes are included only on explicit request. Token values
are never part of an export.

## Migration from the mrschloemps ntfy Server add-on

Migration is options-based only. There is no database import and the message cache starts empty by design.

1. Install this add-on next to the old one. Both can run side by side because they use different hostnames and no host
   port.
2. Copy `base_url`, `auth_default_access`, `admin_user`, `admin_password` and `enable_web_ui` 1:1.
3. Copy the old `users` list 1:1 as `baseline_users`. The fields are the same.
4. Set `baseline_overwrite_passwords: true` if you want the old behavior, where the baseline passwords were set again at
   every start. The new default leaves existing passwords alone.
5. Do not copy `listen_port` and `reset_data`. The port is fixed at 8000 inside the container, and resets are now GUI
   actions.
6. Start the add-on and check users and rules in the GUI.
7. Repoint the Cloudflared or Traefik target of `ntfy.akentner.de` from `f6c6b703-ntfy-server:8000` to
   `72a005f5-ntfy:8000`.
8. Check whether any client still uses `http://<HA-IP>:8000` directly, for example the HA ntfy integration or Gatus.
   Port 8000 is not published by default, so map a host port or change those clients before you rely on it.
9. Stop the old add-on last.

Moving `auth.db` by hand stays possible, but is not supported. When the web UI is enabled, it is served at `/` and
`/app`.

## Security notes

- The GUI answers only to the HA ingress proxy (peer `172.30.32.2` plus an `X-Ingress-Path` header), including static
  files and read requests.
- Passwords reach the ntfy CLI only through the environment. Secrets are never logged.
- Add-on options, and so HA backups, hold the admin and baseline passwords in clear text.
- ntfy stores tokens in clear text. `auth.db` and its backups contain password hashes and clear-text tokens.
- Port 8000 is not published on the host by default.

## Troubleshooting

- **Degraded mode**: if the `auth.db` schema version is not 10, the health page shows the status `degraded`, and every
  request that touches users, rules, tokens, export or resets is refused with the error `db_unsupported`. ntfy keeps
  delivering messages. Check the add-on version against the upstream release notes.
- **Database locked**: ntfy and the GUI share the database. Writes are serialized and retried. If the problem stays,
  restart the add-on.
- **No admin**: `admin_password` is empty. Set it and restart.

## Limitations

- Tiers are shown read-only.
- Token label and expiry are set at creation.
- There is no import in the GUI.
- A machine-readable API for infrastructure as code is planned as a separate later phase.

## Credits

- Upstream ntfy by Philipp C. Heckel (binwiederhier), Apache-2.0 and GPLv2.
- The icon comes from the upstream repository.
- The GUI vendors htm and Preact; their licences are in `app/web/static/vendor`.

[ntfy]: https://github.com/binwiederhier/ntfy
