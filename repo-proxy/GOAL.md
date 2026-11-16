# Goal: Repo Proxy

## Problem

The Home Assistant add-on store (and HACS) can only add repositories that are reachable without authentication. Add-ons
in a private GitHub repository therefore cannot be installed through the store, even though the Supervisor would handle
them fine once it can clone the repository.

## Idea

An add-on that acts as a proxy between the store and the private repository:

- It holds the GitHub credentials (deploy key or fine-grained token, stored as a `password` option).
- It mirrors the private repository and serves it as a read-only git repository (smart HTTP) the Supervisor can clone.
- The repository is published under a **hashed, unguessable URL path** (for example `/r/<hash>.git`), so the URL itself
  acts as the shared secret for the store entry.
- Optionally it is reachable **only inside the HA add-on network** (`http://<hostname>:<port>/...`, no published port),
  so nothing is exposed outside the host. Publishing the port (LAN, Tailscale) stays an explicit opt-in.

## Scope (first version)

- One or more configured source repositories (`url`, credential, branch/ref filter), each with its own hashed path.
- Periodic refresh of the mirror plus a manual refresh trigger.
- The served repository must contain a valid add-on repository (`repository.yaml` at the root) and keep `image:` keys
  usable (images may be private as well, see open questions).
- Startup log prints the store URL to add for each repository.
- Read-only, no write access to the upstream repository.

## Non-goals (for now)

- Proxying container images from private registries (separate problem, see open questions).
- User management or a GUI. If a GUI is added later it follows the shared admin-ui blueprint.
- Serving anything other than add-on repositories.

## Open questions

1. **Hash derivation:** random token generated once and persisted in `/data`, or derived (HMAC of repo URL + secret)?
   Needs a rotation story (revoke old URL, new URL, update the store entry).
2. **Transport:** does the Supervisor accept an `http://` repository URL for a store entry, or does it require
   `https://`/`git@`? If TLS is required, the options are Ingress-less HTTPS with a self-signed or add-on-network CA, or
   a Supervisor-supported scheme. Needs a spike against the Supervisor.
3. **Private images:** add-ons with `image:` keys pull from GHCR. A private image needs registry credentials on the
   host; either keep images public, or document the Supervisor registry settings, or fall back to local builds (strip
   `image:`, as done for local test deploys).
4. **Server choice:** `git http-backend` behind a minimal HTTP server (busybox httpd/nginx) versus a small custom
   service. Prefer the smallest thing that works on the HA base image.
5. **Refresh:** polling interval versus GitHub webhook (a webhook needs an inbound path, which conflicts with "internal
   only").
6. **Credential handling:** deploy key per repository versus one fine-grained token; never log the credential or the
   full hashed URL at levels above `info`.

## Success criteria

- A private repository, listed in the add-on options, can be added to the HA store with the printed URL and its add-ons
  can be installed and updated.
- Without the hashed path the repository is not reachable (404, no repository listing).
- With the port unpublished, the proxy is reachable only from other add-ons and the host.
- Credentials never appear in logs, options export or the served repository.

## Next steps

1. Spike: Supervisor behaviour for `http://` store repository URLs (question 2).
2. Decide hash scheme and server (questions 1 and 4).
3. Plan the implementation as a GSD phase or quick task in the main checkout.
