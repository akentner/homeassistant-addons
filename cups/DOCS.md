# CUPS Add-on Configuration

Add-on icon is the official CUPS project logo (github.com/apple/cups), used under its Apache License 2.0.

## Add-on Options

| Option            | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avahi_reflector` | `false` | Disabled by default. Avahi's legacy-unicast reflector keeps a fixed-size in-memory slot table that fills up under sustained legacy-unicast mDNS traffic (e.g. from a mesh Wi-Fi repeater) and silently drops all further mDNS queries once full, including resolves of this add-on's own advertised printers — the exact bug this add-on exists to fix. Only re-enable this if the add-on is run WITHOUT `host_network: true`, where reflection across network namespaces would actually be needed. |
| `avahi_hostname`  | `cups`  | Fixed Avahi host-name, independent of the container's transient hostname. Prevents the auto-rename-on-conflict behavior (`<hostname>-2`) that made the printer's advertised mDNS name diverge from its actual resolvable address.                                                                                                                                                                                                                                                                   |
| `avahi_use_ipv6`  | `false` | Disabled by default. Avahi may resolve the add-on's mDNS hostname to an IPv6 ULA address that is unreachable/unrouted for some client devices, independent of the reflector bug.                                                                                                                                                                                                                                                                                                                    |
| `server_aliases`  | `*`     | Space- and/or comma-separated list of hostnames cupsd's embedded web server accepts in the HTTP `Host:` header (e.g. `haos-op3050-1.tailxxxx.ts.net` for Tailscale MagicDNS access). `*` (the default) accepts any Host header. See [Design notes](#design-notes) for why this is safe as a default.                                                                                                                                                                                                |
| `printers`        | `[]`    | List of printers to register with CUPS at startup. See [Printers](#printers) below for the object shape.                                                                                                                                                                                                                                                                                                                                                                                            |
| `log_level`       | `info`  | Log verbosity: `debug`, `info`, `warning`, `error`                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

## Printers

Each entry in the `printers` list is an object with four fields:

| Field      | Type    | Default | Description                                                                                            |
| ---------- | ------- | ------- | ------------------------------------------------------------------------------------------------------ |
| `name`     | `str`   | —       | Printer queue name registered with CUPS (`lpadmin -p <name>`)                                          |
| `uri`      | `str`   | —       | Device URI CUPS uses to reach the printer. See [Supported URI schemes](#supported-uri-schemes) below   |
| `enabled`  | `bool?` | `true`  | Whether this printer entry is registered at startup                                                    |
| `location` | `str?`  | —       | Optional CUPS Location string (`lpadmin -L <location>`, e.g. `"Office"`). Omitted entirely when unset. |

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
```

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

**No slot-exhaustion watchdog (D-08).** There is no watchdog or log-monitoring for the
`No slot available for legacy unicast reflection` message anywhere in this add-on. With `avahi_reflector: false` as the
shipped default, this failure class cannot occur at all, so a watchdog for it would be dead code. If you re-enable
`avahi_reflector`, you re-inherit the original bug and are responsible for monitoring it yourself.

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

## Migrating from f1c878cb_cups

See the rollout runbook — filled in by a later plan.
