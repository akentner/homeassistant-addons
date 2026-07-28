# Cloudflare + Traefik + OpenCode GUI — Setup Guide

How the **OpenCode GUI** add-on (a.k.a. "Coding Assistants", slug `72a005f5_coding_assistants`) is exposed from the HA
stack through three access layers:

1. **Cloudflare Access** (Zero Trust) — auth via GitHub org + Google Workspace IdPs.
2. **Cloudflare Tunnel** — via the Cloudflared HA add-on (`haos-op3050-1`).
3. **Traefik** (HA add-on `c1e8c6b3_traefik`) — local routing, TLS termination.

DNS resolves the same hostname differently depending on where the client is, so the app stays usable on the LAN even
when the internet is down. Tailscale users get the cleanest path via Magic DNS.

> **Source of truth for the rollout:** `~/Projects/ha-stack-configs/PLAN.md` (this file is the architectural overview;
> the PLAN holds step-by-step + rollback).

## Architecture

<!-- markdownlint-disable MD040 MD013 -->

```text
                       Off-LAN (Cloudflare)        Tailnet                  LAN (no Tailnet)
                       ─────────────────────       ───────                  ────────────────

  Browser ──► DNS ──► Cloudflare edge           Tailscale Magic DNS       AdGuard Home
                 │      (TLS, WAF,               (100.113.3.8)             (192.168.178.53)
                 │       Access/JWT)                  │                       │
                 │                                   │                       │
                 │      ┌────────────┐               │                       │
                 └─────►│ Cloudflared│◄──────────────┴───────────────────────┘
                        │ addon      │
                        │ (tunnel    │
                        │ haos-op3050│
                        │  -1)       │
                        └─────┬──────┘
                              │  http://c1e8c6b3-traefik:443
                              ▼
                        ┌─────────────┐
                        │  Traefik    │  dynamic config:
                        │  add-on     │  /config/traefik/dynamic/opencode.yaml
                        └─────┬───────┘
                              │  http://72a005f5-coding-assistants:4096
                              ▼
                        ┌─────────────┐
│  OpenCode   │  Coding Assistants add-on, port 4096
                         │  GUI        │
                         └─────────────┘
```

<!-- markdownlint-enable MD040 MD013 -->

## Stack (concrete values)

<!-- markdownlint-disable MD013 -->

| Component                   | Real value                             | Notes                                                  |
| --------------------------- | -------------------------------------- | ------------------------------------------------------ |
| OpenCode GUI add-on slug    | `72a005f5_coding_assistants`           | Container: `72a005f5-coding-assistants`, port **4096** |
| Public hostname             | `opencode.akentner.de`                 | Resolves differently per network (see above)           |
| Cloudflare zone             | `akentner.de`                          | DNS proxied through Cloudflare                         |
| Tunnel name                 | `haos-op3050-1`                        | HAOS host as seen by Cloudflare                        |
| Tunnel UUID                 | `0b558ee5-831b-4546-8860-aaa64ffa867d` | Stored in Cloudflared container at `/data/tunnel.json` |
| Cloudflare Account ID       | `2c33a743eae212159248358adf305a87`     | For API/curl examples                                  |
| HAOS host (LAN)             | `192.168.178.3` (Fritz!Box subnet)     | Traefik listens on 80/443                              |
| HAOS host (Tailnet)         | `100.113.3.8` (Tailscale)              | Tailscale HA add-on `a0d7b954_tailscale`               |
| AdGuard Home (LAN DNS)      | `192.168.178.53`                       | Haushalts-DNS, primary split-horizon                   |
| GitHub IdP org              | `akentner`                             | Org-membership for Access                              |
| Google Workspace IdP domain | `lexsign.de`                           | Email-domain for Access                                |
| Traefik add-on              | `c1e8c6b3_traefik` (v3.7.6)            | `dynamic_configuration_path: /config/traefik`          |
| Cloudflared add-on          | `9074a9fa_cloudflared` (v7.0.9)        | Configured via **Options UI**, not YAML                |

<!-- markdownlint-enable MD013 -->

## Components & where to find the templates

<!-- markdownlint-disable MD013 -->

| Component                      | Configured in                                                       | Template in `~/Projects/ha-stack-configs/`                   |
| ------------------------------ | ------------------------------------------------------------------- | ------------------------------------------------------------ |
| Cloudflare Access (Zero Trust) | Cloudflare dashboard                                                | `cloudflare-access/policy.example.yaml`                      |
| Cloudflared (tunnel + ingress) | **Add-on Options UI** (JSON payload)                                | `cloudflared/options.example.json` + `cloudflared/README.md` |
| Traefik (routing + TLS)        | `/homeassistant/traefik/*.yaml` (no `dynamic/` subdir on this HAOS) | `traefik/opencode.yaml`                                      |
| Split-horizon DNS              | AdGuard Home + Tailscale Magic DNS                                  | `dns/split-horizon.md`                                       |
| OpenCode GUI add-on source     | this repo, `coding-assistants/`                                     | (not templated, this is the addon itself)                    |

<!-- markdownlint-enable MD013 -->

## Auth model

Cloudflare Access sits at the edge. The user authenticates with one of the configured IdPs (GitHub org membership
`akentner` or Google Workspace `lexsign.de`). After successful auth, Cloudflare injects a signed JWT into the
`Cf-Access-Jwt-Assertion` request header. Cloudflared forwards the request through Traefik to OpenCode GUI. Traefik can
validate the JWT locally (defense-in-depth) but currently doesn't.

## Setup steps (summary — full version in `PLAN.md`)

1. **Tailscale** — already running; tailnet devices reach `opencode.akentner.de` directly via Magic DNS, no Access
   needed.
2. **Cloudflare Access** — create self-hosted application for `opencode.akentner.de`, allow GitHub-org `akentner` +
   email-domain `lexsign.de`.
3. **Traefik** — drop `traefik/opencode.yaml` into `/homeassistant/traefik/`.
4. **Cloudflared** — paste `cloudflared/options.example.json` into the add-on's Options UI; restart.
5. **DNS** — AdGuard rewrite `opencode.akentner.de` → `192.168.178.3`.
6. **Verify** — LAN (`dig` should hit 192.168.178.3), WAN (Cloudflare Access login flow).

## Pitfalls / things to remember

- **TLS at Cloudflare, plain HTTP inside the tunnel.** Cloudflared uses HTTP/2 between itself and Cloudflare; inside the
  tunnel, traffic to Traefik is plain HTTP. Traefik should terminate TLS for LAN clients on a separate entrypoint
  (`websecure`) but accept plain HTTP from Cloudflared. Don't accidentally force HTTPS-only on the Cloudflared
  entrypoint.
- **Cloudflare Access JWT validation.** Trust Cloudflare's JWTs as proof of authentication, but **do not** rely on them
  for authorization beyond the edge. OpenCode GUI itself doesn't currently have user accounts — anyone in the allow-list
  has full access.
- **DNS TTL.** When changing the public DNS record, browsers may cache. Use Cloudflare's proxy (orange cloud) so DNS
  responses are CNAME-flattened and not cached aggressively.
- **Hairpin NAT.** If a LAN device queries `opencode.akentner.de` and the local DNS override is missing, it will get the
  Cloudflare anycast IP — and likely fail because the router doesn't support hairpin NAT. That's why the AdGuard rewrite
  is important.
- **Tunnel credentials.** `cert.pem` and `tunnel.json` live in the Cloudflared container at `/data/` and are sensitive.
  The tunnel UUID `0b558ee5-...` is recoverable from the dashboard; the secret inside `tunnel.json` is not stored in any
  template — back it up separately or risk having to delete + recreate the tunnel.
- **Traefik LetsEncrypt placeholder bug.** The Traefik add-on's `letsencrypt.email` field is currently set to
  `deine-email@example.com`. Certificate registration emails go nowhere. Set this to a real address before relying on
  cert renewal.
- **Coding Assistants port 4096 is LAN-exposed.** The container publishes `0.0.0.0:4096` to the host, so anyone on the
  LAN can hit the OpenCode GUI directly, bypassing Cloudflare Access entirely. For real defense-in-depth, either block
  it at the Fritz!Box firewall or modify the add-on manifest. Splithorizon DNS doesn't fix this — clients on the LAN can
  still reach `192.168.178.3:4096` directly.
- **Three-tier DNS resolution** (Tailnet → LAN → WAN). When on the tailnet, devices see the Tailscale IP `100.113.3.8`
  (no Access auth needed). When off-tailnet on the LAN, AdGuard rewrites to `192.168.178.3` (no Access auth either).
  Only when off-LAN do Cloudflare Access IdPs kick in.

## Files

Templates with real values live in `~/Projects/ha-stack-configs/`:

<!-- markdownlint-disable MD013 -->

```text
~/Projects/ha-stack-configs/
├── README.md
├── .gitignore
├── PLAN.md                                # rollout steps, risks, rollback
├── cloudflared/
│   ├── README.md                          # how to apply options.example.json
│   └── options.example.json               # Cloudflared add-on Options UI payload
├── traefik/
│   └── opencode.yaml                      # → /homeassistant/traefik/opencode.yaml
├── dns/
│   └── split-horizon.md                   # AdGuard primary, Tailscale Magic DNS, fallbacks
└── cloudflare-access/
    └── policy.example.yaml                # Access policy (filled-in values)
```

<!-- markdownlint-enable MD013 -->

Status: see `PLAN.md` end-of-file for the datei-map table with current `erledigt` / `offen` status.
