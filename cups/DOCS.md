# CUPS Add-on Configuration

Add-on icon and logo banner use the official CUPS project mark (github.com/OpenPrinting/cups), used under its Apache
License 2.0.

## Add-on Options

| Option             | Default      | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------ | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avahi_reflector`  | `false`      | Disabled by default. Avahi's legacy-unicast reflector keeps a fixed-size in-memory slot table that fills up under sustained legacy-unicast mDNS traffic (e.g. from a mesh Wi-Fi repeater) and silently drops all further mDNS queries once full, including resolves of this add-on's own advertised printers — the exact bug this add-on exists to fix. Only re-enable this if the add-on is run WITHOUT `host_network: true`, where reflection across network namespaces would actually be needed. |
| `avahi_hostname`   | `cups`       | Fixed Avahi host-name, independent of the container's transient hostname. Prevents the auto-rename-on-conflict behavior (`<hostname>-2`) that made the printer's advertised mDNS name diverge from its actual resolvable address.                                                                                                                                                                                                                                                                   |
| `avahi_use_ipv6`   | `false`      | Disabled by default. Avahi may resolve the add-on's mDNS hostname to an IPv6 ULA address that is unreachable/unrouted for some client devices, independent of the reflector bug. `false` also stops the add-on from publishing the host's IPv6 addresses (AAAA and ip6.arpa records) over IPv4 (`publish-aaaa-on-ipv4=no`), because `use-ipv6=no` alone only disables IPv6 sockets.                                                                                                                 |
| `server_aliases`   | `*`          | Space- and/or comma-separated list of hostnames cupsd's embedded web server accepts in the HTTP `Host:` header (e.g. `haos-op3050-1.tailxxxx.ts.net` for Tailscale MagicDNS access). `*` (the default) accepts any Host header. See [Design notes](#design-notes) for why this is safe as a default.                                                                                                                                                                                                |
| `admin_username`   | `""` (unset) | Username for CUPS's web admin UI (`/admin`) login. Leave empty (the default) to keep `/admin` exactly as unauthenticatable as before this option existed — a fail-safe default, not an open admin panel. Must be set together with `admin_password`. See [Design notes](#design-notes) for the security implication of setting this.                                                                                                                                                                |
| `admin_password`   | `""` (unset) | Password for the `admin_username` account above. Masked in the HA UI. Must be set together with `admin_username`. **Pick a real password** — this account is a real system account in the `lpadmin` group, reachable from the LAN (and Tailscale, when detected), not sandboxed by anything else.                                                                                                                                                                                                   |
| `printers`         | `[]`         | List of printers to register with CUPS at startup. See [Printers](#printers) below for the object shape.                                                                                                                                                                                                                                                                                                                                                                                            |
| `log_level`        | `warning`    | Log verbosity: `debug`, `info`, `warning`, `error`. `error_log` is always tailed into the add-on's own log output; `access_log` is additionally tailed only at the `debug` tier.                                                                                                                                                                                                                                                                                                                    |
| `paperless_upload` | (disabled)   | Optional feature: forwards every PDF printed to a second, disabled-by-default `cups-pdf` virtual queue to a [paperless-ngx](https://docs.paperless-ngx.com/) instance. See [Paperless-ngx PDF Upload](#paperless-ngx-pdf-upload) below for the full field list.                                                                                                                                                                                                                                     |

## Printers

Each entry in the `printers` list is an object with six fields:

| Field          | Type                      | Default   | Description                                                                                                           |
| -------------- | ------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| `name`         | `str`                     | —         | Printer queue name registered with CUPS (`lpadmin -p <name>`): letters, digits, hyphens and underscores, 1-127 chars. |
| `uri`          | `str`                     | —         | Device URI CUPS uses to reach the printer. See [Supported URI schemes](#supported-uri-schemes) below                  |
| `enabled`      | `bool?`                   | `true`    | Whether this printer entry is registered at startup                                                                   |
| `location`     | `str?`                    | —         | Optional CUPS Location string (`lpadmin -L <location>`, e.g. `"Office"`). Omitted entirely when unset.                |
| `driver`       | `list(generic\|brlaser)?` | `generic` | PPD driver used at registration. See [Printer driver](#printer-driver) below.                                         |
| `driver_model` | `str?`                    | —         | Required when `driver: brlaser`. Search term matched against `lpinfo -m` to find the exact PPD (e.g. `"MFC-7460DN"`). |

### Supported URI schemes

`printers[].uri` is typed `str` (not HA's built-in `url` schema type) with an explicit runtime scheme-allowlist
validated in `generate_config.py`: `ipp`, `ipps`, `socket`, `usb`, `dnssd`, `lpd`. This was a deliberate choice — HA's
`url` type's acceptance of non-`http` CUPS URI schemes was unverified, and getting it wrong would be a costly options
schema migration for every installed user. Example values:

```yaml
printers:
  - name: "office-ipp"
    uri: "ipp://192.168.1.50:631/ipp/print"
    enabled: true
    location: "Office"
  - name: "jetdirect-printer"
    uri: "socket://192.168.1.51:9100"
    enabled: true
  - name: "usb-printer"
    uri: "usb://Acme/ModelX?serial=ABC123"
    enabled: false
  - name: "Brother-MFC-7460DN"
    uri: "socket://192.168.178.44:9100"
    enabled: true
    location: "Office"
    driver: "brlaser"
    driver_model: "MFC-7460DN"
```

### Printer driver

`driver` (default `generic`, omitted field) selects the PPD used to register a printer:

- **`generic`** (default): `drv:///sample.drv/generic.ppd`, a static generic PostScript driver. Unchanged from this
  add-on's original behavior — see [Generic driver, not driverless auto-detection](#design-notes) below for why this is
  the default.
- **`brlaser`**: uses the [brlaser](https://github.com/pdewacht/brlaser) CUPS driver, packaged for Alpine as
  [`brlaser`](https://pkgs.alpinelinux.org/package/edge/community/x86_64/brlaser) (installed unconditionally in this
  add-on's image). Required for Brother monochrome laser/LED printers with no real PostScript support, connected via a
  raw socket (JetDirect) URI. See [Generic PostScript over a raw socket](#design-notes) below for the exact bug this
  fixes. `driver_model` must be set to a search term (e.g. `"MFC-7460DN"`, a substring of the printer's model name) —
  the exact PPD is resolved at add-on startup by matching this term (case-insensitive, literal substring) against
  `lpinfo -m`'s output. If the term matches zero or more than one brlaser PPD, that printer is skipped (logged as a
  `WARNING`) rather than guessed — see brlaser's own project page for the full list of supported models.

## Print History

Every completed print job is appended as one JSON line to `/data/print-history.jsonl` (survives add-on restarts/updates,
since `/data` is this add-on's persistent volume). A lightweight background poller (`print-history-poller.py`, started
by `run.sh`) queries `lpstat -W completed -o` every ~20 seconds and tracks the last-seen CUPS job id in
`/data/print-history-state.json` so a restart never replays already-recorded jobs. On the very first-ever run (no state
file yet), the poller baselines to whatever jobs already exist at that moment WITHOUT backfilling them — this is a
forward-only history, not a retroactive import.

Each JSONL line has these fields:

| Field         | Type                   | Notes                                                                                                                 |
| ------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `timestamp`   | ISO 8601 string (UTC)  | When the poller observed the job as completed, not CUPS's own (locale-dependent, unreliable to parse) completion time |
| `printer`     | string                 | The CUPS destination name                                                                                             |
| `job_id`      | integer                | CUPS's own job id                                                                                                     |
| `user`        | string or `null`       | Submitting user, from `lpstat`'s output                                                                               |
| `title`       | `null` (always)        | See Known limitations below                                                                                           |
| `page_count`  | `null` (always)        | See Known limitations below                                                                                           |
| `final_state` | `"completed"` (always) | See Known limitations below                                                                                           |

### Known limitations (print history)

- **`final_state` does not currently distinguish canceled/aborted jobs from a normal completion.** CUPS's own
  `lpstat -W completed` classification already groups completed, canceled, and aborted jobs together, and this add-on
  confirmed empirically (during this feature's design) that `lpstat -l`'s `Alerts:` field is not a reliable text signal
  either — a job explicitly canceled while queued showed `Alerts: none`, indistinguishable from a normal successful
  completion. Disambiguating these three states reliably would require an IPP client (e.g. `ipptool`, not present in
  this image) querying the job's `job-state` attribute directly — out of proportionate scope for this add-on's
  single-printer home use case.
- **`title`/`page_count` are always `null`.** Neither is exposed by any CUPS CLI text tool available in this image
  (`lpstat`, `lpq`) for a completed job, without the same additional IPP tooling noted above.
- **No automatic rotation or pruning of `print-history.jsonl`.** It grows indefinitely; prune it manually if it becomes
  large.

## Paperless-ngx PDF Upload

Optionally forwards every PDF produced by a second, dedicated `cups-pdf` virtual print queue to a
[paperless-ngx](https://docs.paperless-ngx.com/) instance's REST API. Disabled by default
(`paperless_upload.enabled: false`) — when disabled, no cups-pdf queue is registered, no `cups-pdf.conf` is generated,
no outbox directories are created under `/data/paperless_upload/`, and the background upload worker (`upload-worker.py`)
exits immediately without touching the filesystem or the network.

| Field         | Type        | Default        | Description                                                                                                                                     |
| ------------- | ----------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `enabled`     | `bool?`     | `false`        | Registers the second `cups-pdf` virtual queue and starts the background upload worker when `true`.                                              |
| `queue_name`  | `str?`      | `"PDF-to-DMS"` | CUPS queue name for the virtual printer (`lpadmin -p <queue_name>`). Validated with the same rules as `printers[].name`.                        |
| `location`    | `str?`      | `""` (unset)   | Optional CUPS Location string for the virtual queue, passed through to `lpadmin -L` exactly like `printers[].location`. Omitted when unset.     |
| `url`         | `str?`      | `""` (unset)   | Base URL of the paperless-ngx instance (e.g. `"http://paperless.local:8000"`); no trailing slash required.                                      |
| `token`       | `password?` | `""` (unset)   | Paperless-ngx API token, sent as `Authorization: Token <token>`. Masked in the HA UI, never written to the add-on's logs.                       |
| `timeout`     | `int?`      | `30`           | HTTP request timeout (seconds) for each upload attempt against paperless-ngx's `/api/documents/post_document/` endpoint.                        |
| `retry_count` | `int?`      | `5`            | Number of upload attempts before a document is given up on and moved to `failed/`.                                                              |
| `retry_delay` | `int?`      | `60`           | Fixed delay (seconds) between retry attempts — not exponential backoff. See [Known limitations](#known-limitations-paperless-ngx-upload) below. |

### Outbox lifecycle

Every PDF printed to the `paperless_upload` queue moves through four stage directories under `/data/paperless_upload/`
(this add-on's persistent volume — survives add-on restarts/updates):

1. **`incoming/`** — cups-pdf writes the PDF here directly (`Out`/`AnonDirName` both point at this single fixed
   directory, see [Design notes](#design-notes) below), alongside a same-basename `.json` title sidecar written
   best-effort by the `PostProcessing` hook.
2. **`processing/`** — the background upload worker (`upload-worker.py`, polling every ~20 seconds) atomically moves a
   new document here before its first upload attempt, and re-attempts it here on every later poll cycle once its retry
   backoff has elapsed.
3. **`sent/`** — on a successful upload (HTTP 2xx from paperless-ngx), the PDF and any leftover sidecar/retry-state
   files move here.
4. **`failed/`** — once `retry_count` attempts are exhausted, the PDF and its title sidecar (if still present) move
   here. **Documents in `failed/` are never automatically deleted or retried again** — they must be triaged and
   resubmitted manually (e.g. re-printed, or uploaded to paperless-ngx by hand). This mirrors
   [Print History](#print-history)'s own honesty about `print-history.jsonl`'s unbounded growth: nothing under
   `/data/paperless_upload/` is pruned automatically.

### Known limitations (paperless-ngx upload)

- **Retry is fixed-interval, not exponential.** Every retry waits exactly `retry_delay` seconds regardless of how many
  attempts have already failed — a deliberate simplicity choice (see [Design notes](#design-notes) below), not an
  oversight.
- **A document moved to `failed/` is not automatically retried again.** There is no automatic re-queue from `failed/`
  back into the pipeline; manual intervention is required.
- **No automatic rotation or pruning of `sent/`/`failed/`.** Both directories grow indefinitely under normal operation;
  prune them manually if they become large.

## Design notes

**Avahi is auto-scoped to the host's primary network interface.** Because this add-on runs `host_network: true`,
`avahi-daemon` binds to every host interface by default -- the real LAN NIC, HA Supervisor's internal `hassio`/`docker0`
bridges, and every veth pair. Supervisor's own always-on `hassio_multicast` service bridges mDNS traffic between the
`hassio` bridge and the real LAN via `mdns-repeater`, and with avahi listening on both sides of that bridge it sees its
own announcements re-injected on a second interface -- which looks exactly like a hostname conflict with another host,
triggering a continuous RFC 6762 §9 auto-rename loop (`cups`, `cups-2`, `cups-3`, ... `cups-N`, never settling). This
was discovered live on `haos-op3050-1` after the fixed-hostname fix (D-11) shipped and initially appeared to fix
nothing. `generate_config.py`'s `detect_primary_interface()` reads `/proc/net/route` at startup (stdlib only, no
`ip`/`iproute2` binary) to find the interface carrying the default route -- the real LAN NIC -- and writes
`allow-interfaces=<that interface>` into the generated `avahi-daemon.conf`, excluding the bridges/veths the repeater
bridges onto/from and breaking the hairpin. This is not exposed as an add-on option: detection is automatic and
host-independent, and a wrong manual value here would break Avahi entirely. If detection fails (no default route found),
avahi falls back to listening on all interfaces -- the pre-fix behavior -- rather than the add-on refusing to start.

**cupsd is scoped to the host's LAN interface, not left on `localhost` (network-reachability fix).** The stock Alpine
`cups` package ships `cupsd.conf` with `Listen localhost:631` and a top-level `<Location />` block with no `Allow`
directive beyond `Order allow,deny`. Because this add-on runs `host_network: true`, that `localhost` is the HOST's own
loopback -- unreachable from any other device on the LAN or via Tailscale. This was discovered when the CUPS web UI
didn't respond at `http://haos-op3050-1...:631/`, and matters even more for AirPrint itself: port 631 is cupsd's actual
IPP printing port, so an AirPrint client that successfully resolves the printer via mDNS (D-11's fix) would still get
connection-refused when it tried to send the print job. `generate_config.py`'s `build_cupsd_conf()` patches exactly two
lines, read from a pristine stock backup (`/etc/cups/cupsd.conf.stock`, created once by the Dockerfile) so repeated
add-on restarts on the same container never double-patch: the `Listen` line becomes `Listen <detected-lan-ip>:631`
(bound to the specific interface IP detected the same way as the Avahi fix above, not an unrestricted `0.0.0.0`), and
the top-level `<Location />` block gains `Allow from <detected-lan-subnet-cidr>` so printing/the web UI work from the
LAN but not from arbitrary addresses. The interface's IPv4 address and netmask are read via `SIOCGIFADDR`/
`SIOCGIFNETMASK` ioctl calls (stdlib `socket`+`fcntl`+`struct`, no `ip`/`iproute2` binary, consistent with this
project's no-extra-packages philosophy). The `/admin`, `/admin/conf`, `/admin/log` Location blocks and every `<Policy>`
block are never touched -- only network reachability changes, the admin-auth boundary (`Require user @SYSTEM`) is
untouched. If interface/IP detection fails for any reason, the add-on logs a WARNING and leaves `cupsd.conf` at its
current content (the stock, loopback-only default) rather than crashing or writing a broken config.

**cupsd's `Host:` header validation is separately widened via `ServerAlias` (configurable, `server_aliases`).** The
LAN-scoping fix above (`Listen`/`Allow from <subnet>`) makes cupsd's port 631 _reachable_ from the LAN, but cupsd's
embedded httpd applies a second, independent check: it validates the incoming HTTP `Host:` header against its own
auto-detected hostname/IPs and returns `400 Bad Request` for anything else, unless a `ServerAlias` directive widens that
accepted list. This was discovered when the CUPS web UI worked fine via direct LAN IP (`http://192.168.178.3:631/`,
HTTP 200) but returned `400 Bad Request` via the host's Tailscale MagicDNS hostname
(`http://haos-op3050-1.<magicdns-suffix>:631/`) — a Host-header rejection, not a network-reachability problem.
`generate_config.py`'s `parse_server_aliases()` splits, validates, and de-duplicates the `server_aliases` option
(space/comma-separated, matching this add-on's scalar-option convention — see `avahi_hostname`) and `build_cupsd_conf()`
inserts the result as a `ServerAlias <token> [<token> ...]` line directly after the patched `Listen` line. The default
is `"*"` (accept any Host header) rather than an empty/unset value, and this is deliberately safe: `ServerAlias` only
gates which Host header names cupsd is willing to accept, not which networks can connect — the real access boundary is
already the `Listen`/`Allow from <lan-subnet-cidr>` pair above, which `server_aliases` does not touch. Leaving this
unset by default would just reintroduce the exact 400 bug for every fresh install (nobody knows to configure it until
they hit the same failure), so `"*"` ships as the working-out-of-the-box default; set `server_aliases` explicitly if you
want to restrict accepted hostnames to a known allowlist instead.

**Tailscale-routed clients are separately allowed through the `<Location />` network boundary (auto-detected, not an
option).** The LAN-scoping fix above widens `ServerAlias` for Host-header validation, but the actual
network-reachability `Allow from <lan-subnet-cidr>` line still only covers the detected LAN subnet. This was discovered
when the web UI worked over the LAN IP but returned `403 Forbidden` over the real Tailscale-routed path -- Tailscale
traffic arrives with a `100.x.x.x` CGNAT-range source address (via the host's `tailscale0` interface), which is a
completely different network than the LAN subnet. `generate_config.py`'s `detect_tailscale_subnet()` checks whether a
`tailscale0` interface exists on the host (this add-on's `host_network: true` means the host's real interfaces are
visible inside the container) and, if so, `build_cupsd_conf()` adds a second `Allow from 100.64.0.0/10` line to the same
top-level `<Location />` block -- CUPS supports multiple `Allow from` lines under one `Order allow,deny`, each evaluated
independently. `100.64.0.0/10` (RFC 6598) is Tailscale's documented CGNAT allocation for every peer's IPv4 address --
deliberately NOT computed from `tailscale0`'s own interface address/netmask the way the LAN subnet is, because Tailscale
assigns that interface a `/32` (point-to-point) address, which would only ever permit traffic from this host's own
Tailscale IP, never from any other peer (e.g. the phone actually placing the AirPrint request). This is not exposed as
an add-on option: detection is automatic, and a deployment without Tailscale simply skips it (logged, not a hard
failure). `/admin`, `/admin/conf`, `/admin/log` are untouched -- same scope boundary as the LAN-scoping fix above.

**The CUPS web admin UI (`/admin`) is usable via `admin_username`/`admin_password` (opt-in, network + auth fixed
together).** Prior to this fix, `/admin` returned `403 Forbidden` for everyone, with no way to authenticate at all — a
two-part bug. First, the stock `<Location /admin>` block ships with no `Allow from` directive (only `AuthType Default` /
`Require user @SYSTEM` / `Order allow,deny`), so it rejected every client at the network layer before any auth challenge
was even offered — unlike the top-level `<Location />` block, which an earlier fix already widened. `build_cupsd_conf()`
now patches `<Location /admin>` with the exact same `Allow from <lan-subnet-cidr>` (+ Tailscale CGNAT CIDR, when
detected) lines as `<Location />` — same detected values, no separate detection. `<Location /admin/conf>` and
`<Location /admin/log>` are deliberately left untouched (still `@SYSTEM`-only, no network widening) — the user only
asked about `/admin` itself. Second, even with network access, nobody could ever log in: this image's only account
(`root`) has a shadow entry of `*` (password disabled, can never authenticate), and there is no PAM config — cupsd
authenticates directly against `/etc/shadow` via `crypt()`. When both `admin_username` and `admin_password` are set,
`generate_config.py`'s `build_admin_provisioning()` validates them and renders `/tmp/provision-admin.sh` (the same
generated-script pattern as `/tmp/register-printers.sh`); `run.sh` executes it, unconditionally, at **every** start,
before cupsd starts — creating the account if absent (or just resetting its password if present), adding it to the
`lpadmin` group (the `SystemGroup` `@SYSTEM` checks), and setting its password via `chpasswd`. This must re-run every
start because this container's filesystem is not persisted outside `/data`, so `/etc/passwd`/`/etc/shadow` reset to the
stock image on every restart/update. Leaving either option empty (the shipped default) writes no script at all,
preserving the exact pre-fix fail-safe behavior — `/admin` stays unauthenticatable, not an open admin panel by default.
`admin_username`/`admin_password` are validated defensively before being embedded into the generated script (a
disallowed character, a mismatched pair, or a value colliding with an existing system account below uid 1000 such as
`root` refuses provisioning with a `WARNING` rather than silently mutating an unrelated account), and the password is
never written to the add-on's logs.

**No slot-exhaustion watchdog (D-08).** There is no watchdog or log-monitoring for the
`No slot available for legacy unicast reflection` message anywhere in this add-on. With `avahi_reflector: false` as the
shipped default, this failure class cannot occur at all, so a watchdog for it would be dead code. If you re-enable
`avahi_reflector`, you re-inherit the original bug and are responsible for monitoring it yourself.

**cupsd's own file-based logs are tailed into the add-on's log output (`log_level`).** Previously, cupsd's
`error_log`/`access_log` under `/var/log/cups/` were invisible to `ha apps logs`/`docker logs` — nothing in this add-on
ever surfaced them. `run.sh` now backgrounds `tail -F /var/log/cups/error_log` unconditionally, and additionally
`tail -F /var/log/cups/access_log` only when `log_level: debug` is selected (the tier used for live diagnosis) — a
quieter default (`log_level: warning`, mapped to CUPS's own `LogLevel warn`) keeps routine operation quiet while `debug`
gives full request-level visibility on demand.

**Generic driver, not driverless auto-detection.** Printer registration uses `lpadmin -m drv:///sample.drv/generic.ppd`
(a static generic PostScript driver) rather than `-m everywhere` (CUPS driverless IPP-Everywhere). `-m everywhere`
performs a live IPP capability query against the device at registration time — a printer that is powered off or
unreachable when the add-on (re)starts would fail to register at all, which defeats the point of a persistent print
queue for a home printer that isn't always on. The generic driver registers the queue unconditionally; CUPS only
contacts the device when a job is actually printed.

**Printer `location` is passed through to `lpadmin -L` (optional, per-printer).** Each `printers[]` entry may set an
optional `location` string (e.g. `"Office"`, `"Kitchen"`) shown by CUPS's own web UI and `lpstat -l -p <name>`.
`generate_config.py`'s `build_printer_registration()` appends `-L "<location>"` to that printer's `lpadmin` argv only
when `location` is present and non-empty -- an empty/omitted value is skipped entirely (not passed as `-L ""`), since an
empty string would actively clear a location a user set manually via the web UI. The value is validated against
`LOCATION_RE` (printable ASCII, no quotes/control characters) before use; an invalid value is skipped with a WARNING
rather than aborting that printer's registration entirely.

**Generic PostScript over a raw socket connection can print a 1-page PDF as endless blank pages (`driver: brlaser`,
D-14).** Discovered during the real physical AirPrint test on `haos-op3050-1`: a Brother MFC-7460DN, connected via
`socket://192.168.178.44:9100` (a JetDirect port, not IPP), was registered with the `generic` driver above
(`drv:///sample.drv/generic.ppd`). Unlike IPP, a raw socket connection has no format- negotiation step — whatever bytes
CUPS sends are exactly what the printer receives. The MFC-7460DN has no genuine PostScript interpreter, so the generic
PostScript byte stream is misinterpreted as raw print data; the printer cycles form-feeds, and a 1-page PDF comes out as
an endless stream of blank pages. [brlaser](https://github.com/pdewacht/brlaser) is an open-source CUPS driver
purpose-built for Brother monochrome laser/LED printers (the MFC-7460DN is explicitly on its supported list) and is
packaged for Alpine as [`brlaser`](https://pkgs.alpinelinux.org/package/edge/community/x86_64/brlaser) — confirmed
available for this add-on's exact base image (`ghcr.io/home-assistant/amd64-base:3.24`, Alpine 3.24, `brlaser-6.2.8-r0`)
and installed unconditionally in the Dockerfile (small package, no cost for installs that leave every printer at the
`generic` default). brlaser's own model-id strings inside its generated PPD list (e.g. `br7460d`, `br7365d`, `br7360`
with no `d` suffix at all) are not a predictable function of the model name — empirically confirmed by installing
`brlaser` into this add-on's own base image locally and running `lpinfo -m` against a live `cupsd` (`lpinfo -m` requires
a running scheduler to answer at all; it cannot be queried at `generate_config.py`'s own build time, before `cupsd`
starts — see `build_printer_registration`/`build_brlaser_registration_snippet` in `cups/generate_config.py`). Rather
than hardcode a guessed identifier, the exact PPD is resolved at add-on startup — after `cupsd` is confirmed ready — by
a literal, case-insensitive substring match of the operator-supplied `driver_model` search term against `lpinfo -m`'s
live output; zero or more than one match is a hard skip with a `WARNING`, never a silent guess. For the MFC-7460DN
specifically, `driver_model: "MFC-7460DN"` resolves to `drv:///brlaser.drv/br7460d.ppd`.

**Printer UUIDs are stable across add-on restarts via a two-phase boot.** This add-on's `/etc/cups/` is not persisted
outside `/data`, so `cupsd` starts every single boot with a completely empty `printers.conf` — `lpadmin -m` therefore
creates every configured printer "fresh" from `cupsd`'s point of view, including a brand-new random `printer-uuid`, on
EVERY restart (confirmed live on `haos-op3050-1` across three consecutive restarts: `a12d7b3a-...` -> `01087e95-...` ->
`740a4011-...`). iOS/AirPrint caches discovered printers keyed by UUID, so enough restarts leave the user with multiple
"ghost" duplicate entries for the same printer name in iOS's print sheet.
`lpadmin -p <name> -o printer-uuid=urn:uuid:<value>` was tried first and confirmed REJECTED — tested live against this
add-on's own running CUPS v2.4.19, `lpadmin` exited `0` but the on-disk UUID in `printers.conf` was completely unchanged
afterward (`printer-uuid` is also absent from `lpadmin`'s own documented `-o` attribute list). A live `printers.conf`
edit followed by a `SIGHUP` reload was also deliberately NOT used: the file's own generated header says, verbatim, "DO
NOT EDIT THIS FILE WHEN CUPSD IS RUNNING", and a real GitHub issue (`apple/cups#2590`) documents the corruption/crash
risk of ignoring that warning. Instead, `generate_config.py`'s `compute_stable_printer_uuid()` derives a deterministic
`uuid.uuid5()` value from each printer's own `name` (a fixed, hardcoded namespace constant — same name always derives
the same UUID, on every host, forever; a renamed printer correctly gets a new identity), and
`build_printer_uuid_fixup_script()` renders `/tmp/fixup-printer-uuids.sh`, which patches ONLY the target printer's own
`UUID urn:uuid:...` line inside its own `<Printer NAME>...</Printer>` stanza — provably scoped, never touching a sibling
printer's UUID or any other directive. `run.sh` runs this ONLY while `cupsd` is fully stopped: it gracefully stops the
already-running `cupsd` (the same `kill -TERM`/`wait` mechanism its own shutdown trap uses), runs the fixup script,
starts a fresh `cupsd`, and re-runs the same readiness-polling wait used on the first boot — printer registration is NOT
re-run a second time, since `printers.conf`/PPDs are otherwise untouched by this cycle. This adds roughly one `cupsd`
start/stop/readiness-wait cycle to every single container boot — an accepted, one-time cost for a stable, non-flickering
AirPrint identity across restarts.

**Paperless-ngx upload reuses a single fixed outbox path, a corrected PostProcessing mechanism, a world-writable outbox,
and deliberately minimal failure visibility (D-05).** The `cups-pdf` virtual queue's `Out`/`AnonDirName` directives both
point at the same fixed `/data/paperless_upload/incoming` path rather than `${HOME}`/`${USER}`-style per-user
substitution -- this container has no meaningful per-user home-directory concept (single-tenant, headless), so every job
lands flat in one shared directory regardless of which user cups-pdf resolves the job to (or falls back to its
`AnonUser="nobody"` default). The original design assumption that cups-pdf's PostProcess hook would receive the job's
title via an environment variable was verified WRONG against cups-pdf's own upstream C source
(`preparetitle()`/`system()` call): the directive is actually named `PostProcessing`, not `PostProcess` (confirmed
against the stock `cups-pdf.conf`'s own `### Key: PostProcessing (config, lptoptions)` documentation), and it invokes
the configured script with exactly three plain positional arguments -- `$1` the final PDF path, `$2` the resolved job
user, `$3` the original submitting user -- never a title-carrying environment variable. The real job title is instead
recovered from the PDF's own already-title-derived filename: cups-pdf's own `preparetitle()` logic derives the PDF's
filename directly from the print job's title, and this add-on's `Label 2` directive appends a `-job_<id>` disambiguating
suffix for collision-safety in the shared outbox directory; the `PostProcessing` hook strips that suffix from `$1`'s
basename to recover the title, rather than looking for any separate title parameter. The outbox directories
(`incoming/`, `processing/`, `sent/`, `failed/`) are created world-writable (`0o777`) as a deliberate choice, not an
oversight: cups-pdf's own `PostProcessing` hook and the PDF-writing step itself run under cups-pdf's resolved job user
(typically `nobody`), not root, so the shared outbox must be writable by an unknown non-root uid -- an acceptable,
low-risk trade-off for a single-tenant home add-on with no other local users. Finally, exhausted-retry visibility is
deliberately minimal: exactly one `WARNING`-level log line is emitted per document once `retry_count` attempts are
exhausted (a single call site in `upload-worker.py`), with no dashboard or notification integration -- consistent with
this add-on's existing plain `print(...)`-based logging convention used everywhere else in this file. Confirmed
empirically end-to-end (real cups-pdf print job -> title sidecar written -> upload-worker.py upload -> `sent/`) by
`internal/verify-cups-paperless-upload.sh` against a real built image.

**Avahi startup guard (D-11).** Earlier versions started `avahi-daemon` in the background and then started cupsd without
checking whether avahi had actually kept the configured host name, so a lost claim silently left the printers published
under a stale name (`cups-2`). The add-on now runs avahi in a way that its own log reaches the add-on log (the
container's `/dev/log` was a dead symlink, so earlier versions discarded avahi's messages) and starts cupsd only after
avahi reports the running state over D-Bus with an unchanged host name for a short hold window. Look for these lines in
the add-on log: `[avahi-guard] INFO: hostname claimed: <name>.local` (normal), `ERROR: hostname lost` (avahi is running
under a different name; the guard stops it and retries), `ERROR: giving up` (all attempts used) and the closing
`[avahi-guard] RESULT:` line (`claimed`, `degraded` or `unsettled`). The retry schedule is immediately, after 30 s, and
after another 90 s: a foreign responder on the LAN that claimed the name often goes away within that time, and a longer
total wait would only delay printing. After the last attempt the add-on keeps running under the renamed host and logs
one loud ERROR rather than exiting, so the published services stay consistent with the name avahi really uses and remain
resolvable. The guard is startup-only: a conflict that appears later is neither healed nor monitored (there is
deliberately no watchdog, D-08), so restart the add-on to retry. When printers are not found, check the add-on log
filtered for `avahi-guard` first.

## Migrating from f1c878cb_cups

This is the procedure actually executed on `haos-op3050-1` to replace the third-party `f1c878cb_cups` add-on with this
one (D-12, D-13):

1. **Get a ready-to-paste `printers:` suggestion from the old add-on's live config.**
   `internal/cups-migration-suggestion.sh` SSHes to the host, runs `ha apps info f1c878cb_cups` and (if no per-printer
   detail is exposed there) `lpstat -v` against the old add-on's container, and prints one YAML entry per discovered
   printer in exactly this add-on's `printers[]` schema shape (`name`/`uri`/`enabled`). It is read-only — no
   install/uninstall/restart verb anywhere in the script — so it is safe to re-run at any time, including before you've
   decided to migrate at all.

2. **Install this add-on and start it with an empty `printers` list.** Do not paste the Task 1 suggestion in yet —
   verify the mDNS fixes hold on the real host first, independent of any printer configuration. Confirm:
   - from a LAN client, `avahi-resolve-host-name -4 <avahi_hostname>.local` returns the host address (D-11)
   - from a LAN client, `avahi-browse -t -r _ipp._tcp` shows a resolved `=` line whose host is `<avahi_hostname>.local`,
     with no auto-renamed `-2` suffix and no IPv6 address (D-10, D-11)
   - the add-on's own logs contain zero occurrences of `No slot available for legacy unicast reflection` (D-07)

   Do not use a reverse lookup of the host IP (`avahi-resolve -a <host-ip>`) as proof: all add-ons and the HAOS host
   share that IP, and the answer comes from whichever of the host's avahi daemons replies first (the HAOS host, other
   host-network add-ons, this add-on), so it is not evidence either way. After every restart or update,
   `internal/verify-cups-mdns-live.sh --assert` runs the reliable checks in one command.

3. **Paste the suggested `printers:` snippet into this add-on's Options, save, and restart it.** Review/edit names and
   URIs first — the script's output is a starting point, not something to paste blindly.

4. **Physically test AirPrint from a real iOS/macOS device.** This is the one step in the migration that genuinely
   cannot be automated — no CLI/API exists for "does AirPrint actually work from a real device". On this host, the first
   physical test surfaced a real bug: a Brother MFC-7460DN connected via raw socket (`socket://`, JetDirect) printed a
   1-page PDF as endless blank pages under the `generic` driver, fixed by setting `driver: brlaser` + `driver_model` for
   that printer (see [Printer driver](#printer-driver) above, D-14). Re-test after any such fix until printing genuinely
   works.

5. **Only after physical confirmation, remove the old add-on:** `ha apps uninstall f1c878cb_cups`, then confirm via
   `ha apps list` that it no longer appears and this add-on still shows `state: started`.

This order — install alongside, verify empirically, migrate config, physically confirm, _then_ remove — means the old
add-on stays available as a fallback for the entire migration and is only ever removed after the replacement is proven
to work, never before.
