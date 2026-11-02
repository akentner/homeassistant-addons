# ntfy export format, schema 1

The admin GUI exports the current state of the add-on (`GET api/export`) as one versioned document, rendered as JSON or
YAML with identical content. It is the contract for Phase 25 (desired-state API) and for IaC repositories that consume
it. Decision D-09 fixed this schema.

## Fields

| Path                         | Type           | Description                                                  |
| ---------------------------- | -------------- | ------------------------------------------------------------ |
| `schema`                     | integer        | Schema version, currently `1`                                |
| `generated_at`               | string         | Export time, ISO 8601 UTC (`2026-11-02T10:00:00Z`)           |
| `source.addon`               | string         | Always `ntfy`                                                |
| `source.auth_schema`         | integer        | Schema version of ntfy's `auth.db` (currently `10`)          |
| `server.auth_default_access` | string         | Option `auth_default_access` (for example `deny-all`)        |
| `users[].name`               | string         | User name; the anonymous user is never listed here           |
| `users[].role`               | string         | `user` or `admin`                                            |
| `users[].tier`               | string or null | ntfy tier code, `null` when none                             |
| `users[].origin`             | string         | `gui`, `options` or `iac`                                    |
| `users[].password_hash`      | string         | bcrypt hash; present only when exported with password hashes |
| `acl[].user`                 | string         | User name, or `everyone` for the anonymous user              |
| `acl[].topic`                | string         | Topic or pattern with `*` wildcards                          |
| `acl[].permission`           | string         | `rw`, `ro`, `wo` or `deny`                                   |
| `acl[].origin`               | string         | `gui`, `options` or `iac`                                    |
| `tokens[].user`              | string         | Owner of the token                                           |
| `tokens[].label`             | string         | Token label (may be empty)                                   |
| `tokens[].expires`           | string or null | Expiry, ISO 8601 UTC, `null` for no expiry                   |
| `tokens[].origin`            | string         | `gui`, `options` or `iac`                                    |

Origins without a record in the sidecar (for example objects created with the ntfy CLI) are reported as `gui`.

## Example (JSON)

```json
{
  "schema": 1,
  "generated_at": "2026-11-02T10:00:00Z",
  "source": {
    "addon": "ntfy",
    "auth_schema": 10
  },
  "server": {
    "auth_default_access": "deny-all"
  },
  "users": [
    {
      "name": "admin",
      "role": "admin",
      "tier": null,
      "origin": "options"
    },
    {
      "name": "akentner",
      "role": "user",
      "tier": null,
      "origin": "gui"
    },
    {
      "name": "homeassistant",
      "role": "user",
      "tier": null,
      "origin": "options"
    }
  ],
  "acl": [
    {
      "user": "akentner",
      "topic": "Xk3fT9aQw2LmP7vB",
      "permission": "ro",
      "origin": "gui"
    },
    {
      "user": "everyone",
      "topic": "public",
      "permission": "ro",
      "origin": "gui"
    },
    {
      "user": "homeassistant",
      "topic": "Xk3fT9aQw2LmP7vB",
      "permission": "rw",
      "origin": "options"
    }
  ],
  "tokens": [
    {
      "user": "akentner",
      "label": "laptop",
      "expires": "2027-01-01T00:00:00Z",
      "origin": "gui"
    }
  ]
}
```

## Example (YAML)

```yaml
schema: 1
generated_at: "2026-11-02T10:00:00Z"
source:
  addon: "ntfy"
  auth_schema: 10
server:
  auth_default_access: "deny-all"
users:
  - name: "admin"
    role: "admin"
    tier: null
    origin: "options"
  - name: "akentner"
    role: "user"
    tier: null
    origin: "gui"
  - name: "homeassistant"
    role: "user"
    tier: null
    origin: "options"
acl:
  - user: "akentner"
    topic: "Xk3fT9aQw2LmP7vB"
    permission: "ro"
    origin: "gui"
  - user: "everyone"
    topic: "public"
    permission: "ro"
    origin: "gui"
  - user: "homeassistant"
    topic: "Xk3fT9aQw2LmP7vB"
    permission: "rw"
    origin: "options"
tokens:
  - user: "akentner"
    label: "laptop"
    expires: "2027-01-01T00:00:00Z"
    origin: "gui"
```

## Secrets policy

- Token values are never exported, in no mode.
- Password hashes appear only when the export is requested explicitly with password hashes (for migrating to another
  instance). Without that flag no `password_hash` key exists.
- The anonymous user appears only as `everyone` inside `acl`, never in `users`.
- Treat an export with hashes like a credential file.

## Ordering and determinism

Keys appear in the order of the table above. Lists are sorted: `users` by name, `acl` by (user, topic), `tokens` by
(user, label, expires). Two exports of the same state are byte-identical except for `generated_at`.

## Versioning

`schema` is an integer. Adding fields keeps `1`; consumers must ignore unknown fields. Removing or renaming a field, or
changing its meaning, bumps the number.

## Identity rules

- A user is identified by `name`, an ACL rule by (`user`, `topic`).
- A token is identified by (`user`, `label`), because token values are never exported. Labels should therefore be unique
  per user when a token is managed as code.
