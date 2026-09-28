#!/usr/bin/env python3
"""Render /etc/avahi/avahi-daemon.conf, /etc/cups/cupsd.conf,
/tmp/register-printers.sh, and /tmp/provision-admin.sh from HA add-on options.

Reads /data/options.json and generates:
  - /etc/avahi/avahi-daemon.conf: a minimal avahi-daemon.conf carrying the three
    permanent AirPrint/mDNS fixes (D-07 reflector off, D-10 IPv6 off, D-11 fixed
    host-name) -- everything else is left to Avahi's compiled-in defaults. It
    also carries an auto-detected `allow-interfaces=` restriction (see
    `detect_primary_interface`) that scopes Avahi to the host's real LAN NIC,
    fixing a live hostname-rename loop discovered on haos-op3050-1 after D-11
    shipped.
  - /etc/cups/cupsd.conf: patched (from a pristine stock backup, never the
    live file -- see `build_cupsd_conf`) so cupsd's `Listen` directive and the
    top-level `<Location />` access control are scoped to the host's real LAN
    interface/subnet instead of the stock package's `localhost`-only default.
    Because this add-on runs `host_network: true`, "localhost" inside the
    container IS the host's own loopback -- unreachable from any other LAN
    device, which meant AirPrint clients could resolve the printer via mDNS
    but never actually connect to port 631 to print. `<Location /admin>` gets
    the same network widening (see `build_cupsd_conf`'s docstring for the
    403-before-any-auth-challenge bug this fixes); `/admin/conf`, `/admin/log`,
    and every Policy block are left byte-for-byte untouched -- only network
    reachability changes, never the admin-auth boundary itself. Also
    emits a `ServerAlias` directive from the `server_aliases` option so
    cupsd's own separate Host-header validation accepts hostnames beyond its
    auto-detected one (e.g. a Tailscale MagicDNS name) -- see
    `parse_server_aliases`. If a `tailscale0` interface is present, a second
    `Allow from 100.64.0.0/10` line is added to the same `<Location />` block
    so Tailscale-routed clients (whose source IP is a CGNAT-range address
    unrelated to the detected LAN subnet) are not rejected with 403 -- see
    `detect_tailscale_subnet`.
  - /tmp/register-printers.sh: one `lpadmin` invocation per valid printers[]
    entry, built from a quoted argv list (never an interpolated shell string) so
    a malformed name or uri cannot inject extra shell commands (T-21-01). Each
    entry's optional `location` field is passed through as `-L <location>`
    when present, letting CUPS show a human-readable per-printer location
    string (e.g. "Office"). An entry's `driver` field (D-14) selects the PPD:
    `generic` (default) keeps the static `drv:///sample.drv/generic.ppd`
    behavior; `brlaser` defers to a runtime `lpinfo -m` lookup inside the
    generated script itself (see `build_brlaser_registration_snippet`) for
    Brother monochrome laser/LED printers with no real PostScript support.
  - /tmp/fixup-printer-uuids.sh: present ONLY when at least one printer
    passed build_printer_registration()'s own validation gates -- patches
    each such printer's `UUID urn:uuid:...` line in the LIVE
    /etc/cups/printers.conf to a value deterministically derived from
    that printer's own `name` (see `compute_stable_printer_uuid`),
    fixing a real bug: this container's /etc/cups/ is not persisted
    outside /data, so every restart previously assigned every printer a
    brand-new RANDOM UUID (cupsd always creates a printer "fresh" from
    its own point of view), which iOS/AirPrint's UUID-keyed printer
    cache surfaced as duplicate "ghost" printer entries after enough
    restarts. Executed by run.sh ONLY while cupsd is fully stopped
    (printers.conf must never be edited while cupsd is running -- see
    run.sh's new boot phase for the stop/patch/restart sequence) -- this
    script itself never starts or stops cupsd, it only performs the
    scoped, single-stanza-only patch.
  - /tmp/provision-admin.sh: one idempotent account-setup script, present ONLY
    when both `admin_username` and `admin_password` validate (see
    `build_admin_provisioning`) -- creates/updates a real system login for
    CUPS's web admin UI (`/admin`), added to the `lpadmin` group so it
    satisfies `Require user @SYSTEM`. Executed by run.sh before cupsd starts,
    every single start, because this container's filesystem is not persisted
    outside /data and /etc/passwd/shadow reset on every restart/update.
  - /tmp/cups-log-level.env: resolves the `log_level` option to both its raw
    value and its mapped `cupsctl LogLevel=` value (see `build_log_level_env`).
    Sourced by run.sh instead of calling `bashio::config 'log_level')` directly
    -- that call requires a live round-trip to the Supervisor API
    (`bashio::addon.config` has no local-file fallback), which is an
    unnecessary fragility for a value this script can already read straight
    out of /data/options.json exactly like every other option here. Also
    means this option is exercisable in a bare `docker run` test harness with
    no real Supervisor present (see internal/verify-cups-scaffold.sh).
"""

import ipaddress
import json
import re
import shlex
import socket
import struct
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover -- only unavailable off Linux/Unix
    fcntl = None

OPTIONS_PATH = "/data/options.json"
AVAHI_CONF_PATH = "/etc/avahi/avahi-daemon.conf"
REGISTER_SCRIPT_PATH = "/tmp/register-printers.sh"
CUPSD_CONF_PATH = "/etc/cups/cupsd.conf"
# Pristine copy of the stock cupsd.conf, written once (Dockerfile, or lazily
# by this script on first run if the Dockerfile step is missing). Every
# startup patches FROM this backup, never from the live CUPSD_CONF_PATH --
# otherwise a restart of the same long-lived container would re-patch an
# already-patched file (e.g. re-matching "Listen <ip>:631" against a regex
# that only recognizes the stock "Listen localhost:631" line, silently
# leaving cupsd unpatched on the second and every later boot).
CUPSD_STOCK_CONF_PATH = "/etc/cups/cupsd.conf.stock"

# Matches both a valid avahi host-name= value and a valid CUPS printer queue
# name. No dots, slashes, whitespace, or shell metacharacters -- closes the
# newline-injection surface into avahi-daemon.conf (T-21-01) and matches
# lpadmin's own accepted queue-name charset.
NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,63}$")

# CUPS device URI schemes this add-on is expected to support (D-03/D-04).
ALLOWED_URI_SCHEMES = {"ipp", "ipps", "socket", "usb", "dnssd", "lpd", "http"}

# Matches a Linux network interface name (IFNAMSIZ is 16 bytes including the
# NUL terminator, so 15 usable chars; dots/colons/@ cover VLAN and macvlan
# sub-interface naming). Defense-in-depth validation before writing an
# auto-detected interface name into avahi-daemon.conf (T-21-01's
# newline-injection concern, extended to a value this add-on derives itself
# from kernel data rather than HA options -- kernel-assigned names are not
# attacker-controlled, but the same validate-before-write discipline applies).
IFACE_RE = re.compile(r"^[A-Za-z0-9@.:_-]{1,15}$")

# Matches a single ServerAlias token: either the literal wildcard "*" (accept
# any Host header value -- the pragmatic default, since Listen/Allow above
# already scope network *reachability* to the detected LAN subnet;
# ServerAlias only gates which Host header cupsd is willing to accept, not
# which networks can connect) or a DNS-hostname-shaped value (letters,
# digits, hyphens, dots -- covers Tailscale MagicDNS names like
# haos-op3050-1.tailXXXX.ts.net as well as plain LAN hostnames). No
# whitespace, semicolons, or other characters that could break the generated
# cupsd.conf line (T-21-01-style defensive validation -- this value comes
# from an HA add-on option, i.e. attacker-controlled if the UI is exposed).
SERVER_ALIAS_TOKEN_RE = re.compile(r"^(\*|[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)$")

PROC_NET_ROUTE = "/proc/net/route"

# /tmp/provision-admin.sh -- see build_admin_provisioning. Written only when
# both admin_username and admin_password validate; run.sh checks for this
# file's presence (mirrors the REGISTER_SCRIPT_PATH pattern below) before
# executing it, so the fail-safe default (either option unset) leaves no
# file to run at all.
ADMIN_PROVISION_SCRIPT_PATH = "/tmp/provision-admin.sh"

# /tmp/cups-log-level.env -- see build_log_level_env. Sourced by run.sh in
# place of a direct `bashio::config 'log_level'` call.
LOG_LEVEL_ENV_PATH = "/tmp/cups-log-level.env"

# Must stay in sync with cups/config.yaml's `schema.log_level` enum.
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}

# cupsd's own `cupsctl LogLevel=` accepted values -- "warning" (this add-on's
# option name, matching HA's own convention) maps to CUPS's own "warn" token.
# An invalid/unrecognized log_level value falls back to "info", the same
# fallback the add-on has always used (originally as the `case ... *)` branch
# in run.sh, now here).
_LOG_LEVEL_TO_CUPSCTL = {
    "debug": "debug",
    "info": "info",
    "warning": "warn",
    "error": "error",
}

# CUPS's live printer registry -- see build_printer_uuid_fixup_script's
# docstring for why this is only ever patched while cupsd is fully
# stopped, never live (the file's own generated header says so verbatim:
# "DO NOT EDIT THIS FILE WHEN CUPSD IS RUNNING"; apple/cups#2590
# documents the corruption/crash risk of ignoring that warning).
PRINTERS_CONF_PATH = "/etc/cups/printers.conf"

# /tmp/fixup-printer-uuids.sh -- see build_printer_uuid_fixup_script.
# Written only when at least one printer passed
# build_printer_registration()'s own validation gates (mirrors the
# REGISTER_SCRIPT_PATH/ADMIN_PROVISION_SCRIPT_PATH presence-check pattern
# above); run.sh checks for this file's presence before executing it.
PRINTER_UUID_FIXUP_SCRIPT_PATH = "/tmp/fixup-printer-uuids.sh"

# Fixed, arbitrary namespace UUID for compute_stable_printer_uuid()'s
# uuid.uuid5() derivation -- generated once via uuid.uuid4() at design
# time and hardcoded here. Not a secret: it only needs to be a fixed
# constant so the SAME printer `name` always derives the SAME UUID, on
# every host running this add-on, forever. Never regenerate this value --
# doing so would change every already-deployed printer's "stable" UUID on
# its next restart, which is the exact bug this whole fix exists to
# prevent.
PRINTER_UUID_NAMESPACE = uuid.UUID("1d944d3a-d74c-4e0b-b273-fdce19c621d9")

# Linux/BusyBox username convention (adduser enforces a similar check itself,
# but this is validated BEFORE being embedded into the generated shell script
# below -- defense in depth, same posture as NAME_RE/IFACE_RE/LOCATION_RE):
# lowercase letters/digits/underscore/hyphen, must start with a letter or
# underscore, max 32 chars total.
ADMIN_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

# paperless_upload (Phase 22) -- see build_cups_pdf_conf / build_paperless_postprocess_hook
# / build_cups_pdf_registration_snippet below. Kept as a dedicated block of constants,
# mirroring the CUPSD_STOCK_CONF_PATH / REGISTER_SCRIPT_PATH naming convention above.
PAPERLESS_UPLOAD_CUPS_PDF_CONF_PATH = "/etc/cups/cups-pdf.conf"
# Pristine copy of the stock cups-pdf.conf, written by the Dockerfile (mirrors
# CUPSD_STOCK_CONF_PATH's own rationale: every startup patches FROM this backup,
# never from a possibly-already-patched live file).
PAPERLESS_UPLOAD_CUPS_PDF_CONF_STOCK_PATH = "/etc/cups/cups-pdf.conf.stock"
# Single shared outbox root (D-05) -- incoming/processing/sent/failed stage
# directories live directly under this path. Under /data so it survives
# container restarts (unlike /etc/cups/, which does not).
PAPERLESS_UPLOAD_OUTBOX_ROOT = "/data/paperless_upload"
# Rendered by build_paperless_postprocess_hook(), referenced as cups-pdf's own
# `PostProcessing` directive. /tmp (not /data) since it is regenerated every
# startup, exactly like REGISTER_SCRIPT_PATH/ADMIN_PROVISION_SCRIPT_PATH above.
PAPERLESS_UPLOAD_POSTPROCESS_HOOK_PATH = "/tmp/paperless-postprocess.sh"
# Literal (non-regex) case-insensitive search term matched against a live
# `lpinfo -m` listing to resolve cups-pdf's own auto-generated PPD -- mirrors
# build_brlaser_registration_snippet's driver_model search, but fixed (not an
# add-on option) since cups-pdf only ever ships the one PPD.
PAPERLESS_UPLOAD_PPD_SEARCH_TERM = "CUPS-PDF"
# cups-pdf's device URI scheme -- fixed, not user-configurable (unlike
# printers[].uri): this queue is always backed by the cups-pdf virtual backend.
CUPS_PDF_DEVICE_URI = "cups-pdf:/"

# Matches a CUPS printer Location string (lpadmin -L). Conservative
# printable-ASCII-minus-quotes allowlist -- defense in depth alongside the
# argv-array construction in build_printer_registration (T-21-01's
# no-interpolated-shell-string mitigation already prevents injection via
# shlex.quote, but this closes the door on control characters or values that
# would otherwise render oddly in `lpstat -l`/the HA UI).
LOCATION_RE = re.compile(r"^[A-Za-z0-9 ,.\-_/()]{1,127}$")

# Per-printer driver selection (D-14 -- Brother MFC-7460DN blank-page bug).
# "generic" (default, omitted field) preserves this add-on's original
# behavior byte-for-byte; "brlaser" is for raw-socket-connected Brother
# monochrome laser/LED printers with no real PostScript support (see
# `build_brlaser_registration_snippet` for the root cause and why the PPD
# lookup happens at runtime, not here).
ALLOWED_DRIVERS = {"generic", "brlaser"}
GENERIC_PPD = "drv:///sample.drv/generic.ppd"

# Matches a `driver_model` search term (e.g. "MFC-7460DN"): the free-text
# string an operator supplies to identify their printer's exact brlaser PPD
# among `lpinfo -m`'s listing (see build_brlaser_registration_snippet).
# Same conservative printable-ASCII-minus-quotes allowlist as LOCATION_RE --
# this value is embedded into the generated register-printers.sh via
# shlex.quote (T-21-01's no-interpolated-shell-string mitigation), this regex
# is defense in depth against control characters/newlines.
DRIVER_MODEL_RE = re.compile(r"^[A-Za-z0-9 ,.\-_/()]{1,127}$")

# Tailscale's standard Linux interface name -- not configurable by the user
# (Tailscale itself does not support renaming it), so this is a fixed check
# rather than a new add-on option.
TAILSCALE_IFACE = "tailscale0"

# Tailscale allocates every peer's IPv4 address from this CGNAT range (RFC
# 6598, documented at https://tailscale.com/kb/1015/100.x-addresses). The
# interface's OWN address is assigned with a /32 (point-to-point) netmask, so
# computing a CIDR from tailscale0's own ip+netmask the same way as the LAN
# detection below would only ever produce "<this-host's-own-tailscale-ip>/32"
# -- permitting traffic FROM THIS HOST'S OWN TAILSCALE ADDRESS ONLY, never
# from any other Tailscale peer (e.g. the phone actually placing the AirPrint
# request). Allowing the well-known CGNAT range instead of a per-host
# computed subnet is what actually fixes 403s from Tailscale-routed clients.
TAILSCALE_CGNAT_CIDR = "100.64.0.0/10"

# Matches the stock Alpine cups package's top-level Listen directive -- the
# thing this fix must replace. Anchored to the full line so a value that has
# already been patched (e.g. "Listen 192.168.178.3:631") never matches,
# reinforcing the stock-backup-based idempotency above.
LISTEN_LOCALHOST_RE = re.compile(r"^Listen localhost:631\s*$", re.MULTILINE)

# Matches the stock top-level `<Location />` block (CUPS's whole-server access
# control, distinct from `<Location /admin>` etc. -- the literal "/>" only
# appears for the root Location). Non-greedy body capture stops at this
# block's own `</Location>` since CUPS's Location blocks are never nested.
LOCATION_ROOT_RE = re.compile(r"(<Location />\n)(.*?)(\n</Location>)", re.DOTALL)

# Matches the stock `<Location /admin>` block (the CUPS web admin UI).
# Anchored to the exact ">" immediately after "/admin" so this never matches
# `<Location /admin/conf>` or `<Location /admin/log>` -- those two stay
# byte-for-byte untouched (see build_cupsd_conf's docstring for why).
LOCATION_ADMIN_RE = re.compile(r"(<Location /admin>\n)(.*?)(\n</Location>)", re.DOTALL)

# ioctl request numbers (Linux-specific, from <linux/sockios.h>) used by
# get_iface_ipv4 below to read an interface's IPv4 address/netmask without an
# `ip`/`iproute2` binary in the image.
_SIOCGIFADDR = 0x8915
_SIOCGIFNETMASK = 0x891B


def detect_primary_interface() -> str | None:
    """Return the interface name carrying the host's default IPv4 route.

    Root cause (found on haos-op3050-1 after this add-on shipped D-11's fixed
    hostname): this add-on runs `host_network: true`, so avahi-daemon binds to
    EVERY host interface -- the real LAN NIC, the `hassio` and `docker0`
    bridges, and every veth pair. HA Supervisor's own always-on
    `hassio_multicast` service runs `mdns-repeater -f hassio` on the host
    network, bridging mDNS traffic between the `hassio` bridge and the real
    LAN interfaces. Avahi ends up seeing its own announcements re-injected via
    a second interface, which looks exactly like another host claiming the
    same hostname -- triggering RFC 6762 SS9's probe-conflict auto-rename
    repeatedly (the observed cups-2, cups-3, ... cups-N loop that never
    settles).

    Scoping avahi to just the interface with a default route (the real LAN
    NIC, e.g. `enp2s0`) excludes the bridges/veths the repeater bridges
    onto/from, breaking the hairpin.

    Reads /proc/net/route directly (Python stdlib only -- this image
    deliberately does not carry an `ip`/`iproute2` binary) rather than
    shelling out. Because `host_network: true` shares the host's network
    namespace, /proc/net/route reflects the *host's* routing table, not a
    container-private one.

    Returns None -- rather than raising -- when no default route is found, so
    a detection failure degrades to the pre-fix behavior (avahi listens on
    every interface) instead of crashing the whole add-on.
    """
    path = Path(PROC_NET_ROUTE)
    if not path.exists():
        return None
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None

    # Header: Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT
    # A default route's Destination field is the all-zero mask "00000000".
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 2:
            continue
        iface, destination = fields[0], fields[1]
        if destination == "00000000":
            return iface
    return None


def get_iface_ipv4(iface: str) -> tuple[str, str] | None:
    """Return (ip, netmask) for `iface` via SIOCGIFADDR/SIOCGIFNETMASK ioctls.

    Stdlib-only (socket + fcntl + struct) -- consistent with
    `detect_primary_interface`, this image deliberately does not carry an
    `ip`/`iproute2` binary. Returns None on any failure (no fcntl on this
    platform, interface has no IPv4 address, permission denied, interface
    does not exist, etc.) so callers degrade gracefully rather than crash.
    """
    if fcntl is None:
        return None

    def _query(sock: socket.socket, request: int) -> str | None:
        # 256s buffer is the well-established recipe for these calls: the
        # kernel only reads the first IFNAMSIZ (16) bytes of the ifreq name
        # field but writes its response into the same buffer, so it must be
        # large enough to hold the returned sockaddr too.
        ifreq = struct.pack("256s", iface.encode("utf-8")[:15])
        try:
            result = fcntl.ioctl(sock.fileno(), request, ifreq)
        except OSError:
            return None
        return socket.inet_ntoa(result[20:24])

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            ip = _query(sock, _SIOCGIFADDR)
            netmask = _query(sock, _SIOCGIFNETMASK)
    except OSError:
        return None

    if ip is None or netmask is None:
        return None
    return ip, netmask


def compute_subnet_cidr(ip: str, netmask: str) -> str | None:
    """Return e.g. "192.168.178.0/24" for an interface's IP + dotted netmask.

    Returns None if `ip`/`netmask` do not form a valid IPv4 network (should
    not happen for kernel-reported values, but this is written into a
    security-relevant access-control directive, so refuse rather than guess).
    """
    try:
        network = ipaddress.ip_network(f"{ip}/{netmask}", strict=False)
    except ValueError:
        return None
    return str(network)


def detect_tailscale_subnet() -> str | None:
    """Return the Tailscale CGNAT CIDR if this host has a `tailscale0` interface.

    Root cause this fixes (found on haos-op3050-1 during the physical AirPrint
    test, after the LAN-scoping fix above already shipped): the user tested
    Web-UI access over the REAL Tailscale-routed path (not just a Host-header
    test) and got 403 Forbidden. `<Location />`'s `Allow from
    <lan-subnet-cidr>` only permits the detected LAN subnet, but
    Tailscale-routed traffic arrives with a `100.x.x.x` CGNAT-range source IP
    via the `tailscale0` interface -- outside that CIDR entirely, a
    completely separate network path from the LAN.

    Uses the same stdlib ioctl-based detection as `get_iface_ipv4` (this image
    deliberately carries no `ip`/`iproute2` binary), but does NOT compute a
    CIDR from the interface's own address/netmask -- see `TAILSCALE_CGNAT_CIDR`
    for why. Only the interface's PRESENCE is queried here.

    Returns None -- degrading gracefully, not a hard failure -- if no
    `tailscale0` interface exists (fcntl unavailable, interface absent, no
    IPv4 assigned yet). Not every deployment runs Tailscale.
    """
    if get_iface_ipv4(TAILSCALE_IFACE) is None:
        return None
    return TAILSCALE_CGNAT_CIDR


def parse_server_aliases(raw: object) -> list[str]:
    """Split, validate, and de-duplicate a `server_aliases` option value.

    Accepts a single string of space- and/or comma-separated hostnames (this
    add-on's schema convention for scalar options, see `avahi_hostname`)
    rather than a list, since the `ServerAlias` cupsd directive itself takes
    multiple space-separated values on one line.

    Root cause this fixes (found on haos-op3050-1 while preparing for the
    AirPrint physical test, after the LAN-scoping fix above already shipped):
    cupsd's embedded httpd validates the incoming HTTP `Host:` header against
    its own detected hostname/IPs and rejects anything else with `400 Bad
    Request` -- unless `ServerAlias` widens that accepted list. Direct-IP
    access (`http://192.168.178.3:631/`) already worked (the LAN-scoping fix
    above), but the Tailscale MagicDNS hostname
    (`haos-op3050-1.<magicdns-suffix>:631`) did not, because its Host header
    never matched cupsd's auto-detected name.

    Invalid tokens are skipped and logged rather than aborting the whole
    add-on -- one bad hostname should not also lose the good ones.
    """
    tokens = re.split(r"[,\s]+", str(raw).strip())
    valid: list[str] = []
    for token in tokens:
        if not token:
            continue
        if SERVER_ALIAS_TOKEN_RE.match(token):
            if token not in valid:
                valid.append(token)
        else:
            print(
                f"WARNING: skipping invalid server_aliases token {token!r} -- must match "
                f"{SERVER_ALIAS_TOKEN_RE.pattern}",
                flush=True,
            )
    return valid


def build_cupsd_conf(iface: str | None, options: dict) -> str | None:
    """Render a patched cupsd.conf scoping cupsd to the host's LAN interface.

    Root cause (found on haos-op3050-1 while preparing for the AirPrint
    physical test, D-12): this add-on ships the stock Alpine `cups` package's
    cupsd.conf completely unmodified. Its `Listen localhost:631` line binds
    BOTH the admin web UI and the actual IPP printing port to loopback --
    and because this add-on runs `host_network: true`, that loopback is the
    HOST's own loopback, not a container-private one. mDNS correctly
    advertises the printer (D-11's fix), but any client outside the host --
    every AirPrint client on the LAN -- gets connection-refused/unreachable
    on port 631, so print jobs (and the web UI) never actually reach cupsd.

    Patches exactly two things, read from the pristine stock backup (see
    CUPSD_STOCK_CONF_PATH) so this is idempotent across restarts of the same
    long-lived container:
      - the top-level `Listen localhost:631` line becomes
        `Listen <lan-ip>:631` (bound to the specific detected interface IP,
        not an unrestricted `0.0.0.0`, since the goal is LAN-only exposure)
      - the top-level `<Location />` block (whole-server access control)
        gains `Allow from <lan-subnet-cidr>` underneath the stock's
        `Order allow,deny` -- printing/web-UI works from the detected LAN
        subnet, not from arbitrary addresses
      - the `<Location /admin>` block (the CUPS web admin UI) gains the same
        `Allow from <lan-subnet-cidr>` (+ Tailscale, when detected) lines --
        see the `/admin` paragraph below for why this is also needed, not
        just the root block
    Also inserts a `ServerAlias` directive (from the `server_aliases` add-on
    option, default `"*"`) directly after the patched `Listen` line -- see
    `parse_server_aliases` for why this is needed (cupsd's Host-header
    validation, a separate concern from the `Listen`/`Allow` network-
    reachability fix above) and why `"*"` is a safe out-of-the-box default
    (the real access boundary is already the detected LAN subnet's `Allow
    from`, not the Host header check).

    If a `tailscale0` interface is present on the host, a SECOND `Allow from
    100.64.0.0/10` line is added to both the `<Location />` AND `<Location
    /admin>` blocks (CUPS's `Order allow,deny` evaluates multiple `Allow
    from` lines independently -- standard syntax, not an error) -- see
    `detect_tailscale_subnet` for why Tailscale-routed clients need this in
    addition to the LAN subnet's `Allow from` line. If no `tailscale0`
    interface is found, this is skipped with a log note, not a hard failure
    -- not every deployment runs Tailscale.

    `/admin` (the CUPS web admin UI) gains the SAME `Allow from` line(s) as
    the top-level `<Location />` above -- root cause: the stock `<Location
    /admin>` block ships with NO `Allow from` directive at all (only
    `AuthType Default` / `Require user @SYSTEM` / `Order allow,deny`), so it
    was rejecting every client at the network layer before any auth
    challenge was even offered, independent of whether a valid account
    existed. `/admin/conf`, `/admin/log`, and every `<Policy>` block are
    never touched by this function -- only `Listen`, `<Location />`, and
    `<Location /admin>` are patched, everything else in the stock file
    survives byte-for-byte.

    Returns None -- leaving CUPSD_CONF_PATH at its current (stock, loopback-
    only) content -- when no interface was detected, no IPv4 address could be
    read for it, no subnet could be computed, or the stock template does not
    look like what this function expects to patch. Every one of those is
    logged as a WARNING; none of them crashes the add-on.
    """
    stock_path = Path(CUPSD_STOCK_CONF_PATH)
    if not stock_path.exists():
        # Defensive fallback for an image built before this fix's Dockerfile
        # step existed: back up whatever is live right now, so this and every
        # later restart of this same container patches from the ORIGINAL
        # stock content, not from an already-patched file.
        current_path = Path(CUPSD_CONF_PATH)
        if not current_path.exists():
            print(
                f"WARNING: neither {CUPSD_STOCK_CONF_PATH} nor {CUPSD_CONF_PATH} exist -- "
                "cannot patch cupsd's network scope",
                flush=True,
            )
            return None
        try:
            stock_path.write_text(current_path.read_text())
        except OSError as exc:
            print(f"WARNING: could not create cupsd.conf stock backup: {exc}", flush=True)
            return None

    try:
        template = stock_path.read_text()
    except OSError as exc:
        print(f"WARNING: could not read {CUPSD_STOCK_CONF_PATH}: {exc}", flush=True)
        return None

    if iface is None:
        print(
            "WARNING: no primary network interface detected -- cupsd will keep listening on "
            "localhost only; AirPrint clients and the web UI will be unreachable from the LAN",
            flush=True,
        )
        return None

    if not IFACE_RE.match(iface):
        print(
            f"WARNING: detected primary interface {iface!r} failed validation against "
            f"{IFACE_RE.pattern} -- cupsd will keep listening on localhost only",
            flush=True,
        )
        return None

    addr = get_iface_ipv4(iface)
    if addr is None:
        print(
            f"WARNING: could not determine an IPv4 address/netmask for interface {iface!r} -- "
            "cupsd will keep listening on localhost only",
            flush=True,
        )
        return None

    ip, netmask = addr
    subnet = compute_subnet_cidr(ip, netmask)
    if subnet is None:
        print(
            f"WARNING: could not compute a subnet CIDR from {ip}/{netmask} -- cupsd will keep "
            "listening on localhost only",
            flush=True,
        )
        return None

    if not LISTEN_LOCALHOST_RE.search(template):
        print(
            "WARNING: stock cupsd.conf does not contain the expected 'Listen localhost:631' "
            "line -- refusing to patch an unrecognized template; cupsd will keep listening on "
            "localhost only",
            flush=True,
        )
        return None

    patched = LISTEN_LOCALHOST_RE.sub(f"Listen {ip}:631", template, count=1)

    aliases = parse_server_aliases(options.get("server_aliases", "*"))
    if aliases:
        patched = patched.replace(
            f"Listen {ip}:631",
            f"Listen {ip}:631\nServerAlias {' '.join(aliases)}",
            1,
        )
    else:
        print(
            "WARNING: no valid server_aliases tokens -- ServerAlias not written; cupsd may "
            "reject Host headers that do not match its auto-detected hostname/IPs (400 Bad "
            "Request)",
            flush=True,
        )

    tailscale_subnet = detect_tailscale_subnet()
    if tailscale_subnet:
        print(
            f"INFO: tailscale0 interface detected -- also allowing {tailscale_subnet} in the "
            "top-level <Location /> and <Location /admin> blocks",
            flush=True,
        )
    else:
        print(
            "INFO: no tailscale0 interface detected -- skipping the Tailscale Allow rule "
            "(not every deployment runs Tailscale)",
            flush=True,
        )

    def _widen_location(text: str, location_re: re.Pattern, label: str) -> tuple[str, bool]:
        """Append `Allow from <subnet>` (+ Tailscale, if detected) to one Location
        block's body. Returns (patched-or-unchanged text, whether a match was found).
        Shared by both `<Location />` and `<Location /admin>` below so they always
        agree on which networks may reach them -- one detection, two call sites.
        """
        match = location_re.search(text)
        if match is None:
            print(
                f"WARNING: stock cupsd.conf does not contain the expected '{label}' block -- "
                "its access control was not widened",
                flush=True,
            )
            return text, False
        body = match.group(2)
        allow_lines = f"{body}\n  Allow from {subnet}"
        if tailscale_subnet:
            allow_lines += f"\n  Allow from {tailscale_subnet}"
        return text[: match.start(2)] + allow_lines + text[match.end(2) :], True

    patched, root_patched = _widen_location(patched, LOCATION_ROOT_RE, "<Location />")
    if not root_patched:
        print(
            "WARNING: Listen was patched but the top-level <Location /> access control was "
            "not; cupsd is reachable on the LAN with NO subnet restriction until this is fixed",
            flush=True,
        )
        return patched

    patched, _ = _widen_location(patched, LOCATION_ADMIN_RE, "<Location /admin>")
    return patched


def load_options() -> dict:
    path = Path(OPTIONS_PATH)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def build_avahi_conf(options: dict) -> str:
    """Render avahi-daemon.conf carrying the D-07/D-10/D-11 fixes.

    Exits the process non-zero on an invalid avahi_hostname -- a raw newline in
    that value could otherwise inject arbitrary directives into the generated
    file (T-21-01), so refusing to start is safer than writing an unsafe string.
    """
    hostname = str(options.get("avahi_hostname", "cups"))
    if not NAME_RE.match(hostname):
        print(
            f"ERROR: avahi_hostname '{hostname}' is invalid -- must match "
            f"{NAME_RE.pattern} (letters, digits, hyphens, 1-63 chars). Refusing to start.",
            flush=True,
        )
        sys.exit(1)

    reflector = bool(options.get("avahi_reflector", False))
    use_ipv6 = bool(options.get("avahi_use_ipv6", False))

    lines = [
        "[server]",
        f"host-name={hostname}",
        f"use-ipv6={'yes' if use_ipv6 else 'no'}",
    ]

    allow_iface = detect_primary_interface()
    if allow_iface is None:
        print(
            "WARNING: could not detect a primary network interface (no default route in "
            f"{PROC_NET_ROUTE}) -- avahi will listen on all interfaces, re-exposing the "
            "hostname-rename-loop risk this fix addresses",
            flush=True,
        )
    elif not IFACE_RE.match(allow_iface):
        print(
            f"WARNING: detected primary interface {allow_iface!r} failed validation against "
            f"{IFACE_RE.pattern} -- avahi will listen on all interfaces (pre-fix behavior)",
            flush=True,
        )
    else:
        lines.append(f"allow-interfaces={allow_iface}")

    lines += [
        "",
        "[reflector]",
        f"enable-reflector={'yes' if reflector else 'no'}",
        "",
    ]
    return "\n".join(lines)


def build_brlaser_registration_snippet(name: str, uri: str, driver_model: str, location: str) -> str:
    """Emit sh that resolves the exact brlaser PPD via `lpinfo -m` at
    registration time, then registers the printer with it.

    Root cause this fixes (a real physical AirPrint test on haos-op3050-1,
    D-14): a Brother MFC-7460DN is connected via raw `socket://` (JetDirect,
    port 9100) -- unlike IPP, a raw socket has no format-negotiation step, so
    whatever bytes CUPS sends are what the printer gets. Registered with
    `drv:///sample.drv/generic.ppd` (generic PostScript), a printer with no
    real PostScript support cannot parse the PS byte stream and cycles
    form-feeds -- a 1-page PDF prints as endless blank pages. brlaser
    (github.com/pdewacht/brlaser, packaged for Alpine as `brlaser`) ships a
    real PPD generator for Brother monochrome laser/LED printers, including
    the MFC-7460DN.

    Why this resolution happens HERE (in the generated shell script) and not
    in generate_config.py's own Python code: `lpinfo -m` requires a LIVE
    cupsd scheduler to answer -- confirmed empirically via a local `docker
    run` against this add-on's own base image (brlaser installed, cupsd not
    yet started: `lpinfo -m` fails with "Bad file descriptor"; cupsd started:
    it lists every driver, e.g. `drv:///brlaser.drv/br7460d.ppd Brother
    MFC-7460DN, using Owl-Maintain/brlaser v6.2.8`). generate_config.py itself
    runs BEFORE cupsd starts (run.sh step 1), so this lookup cannot happen at
    Python build time -- it is deferred into the generated
    /tmp/register-printers.sh, which run.sh only executes after cupsd is
    confirmed ready (step 6).

    brlaser's own model-id strings (`br7460d`, `br7365d`, `br7360` with no
    `d`, ...) are not a predictable function of the model name, so this never
    hardcodes a guessed identifier: `driver_model` is a free-text search term
    (e.g. "MFC-7460DN") the operator supplies in the add-on options, matched
    with a literal (non-regex) case-insensitive substring search (`grep -iF`)
    against the live `lpinfo -m` listing. Zero matches (after the retry loop
    below) or more than one match is a hard skip with a clear log message --
    never a silent guess at which PPD is "close enough".

    Retries `lpinfo -m` itself (up to 5 attempts, 1s apart) while it returns
    no match at all -- found on a real deployment (haos-op3050-1): even after
    run.sh's own `lpstat -r`-based readiness wait reports cupsd accepting
    connections, `lpinfo -m`'s driver enumeration can still transiently come
    back empty for the first second or so cupsd is up. Because an empty
    match is NOT a script failure (it is caught and logged, not raised),
    run.sh's outer retry-the-whole-script loop never re-attempts it -- so
    without this inner retry, that transient race would permanently skip a
    correctly-configured printer's registration until the add-on's next
    restart. A `driver_model` that never matches (a real misconfiguration,
    not a timing race) still exhausts these retries and is skipped with a
    WARNING exactly as before.
    """
    quoted_model = shlex.quote(driver_model)
    quoted_name = shlex.quote(name)
    quoted_uri = shlex.quote(uri)
    location_arg = f" -L {shlex.quote(location)}" if location else ""
    return (
        f'PPD_MATCH=""\n'
        f'PPD_ATTEMPT=0\n'
        f'while [ "$PPD_ATTEMPT" -lt 5 ]; do\n'
        f'  PPD_MATCH=$(lpinfo -m 2>/dev/null | grep -iF -- {quoted_model} || true)\n'
        f'  [ -n "$PPD_MATCH" ] && break\n'
        f'  PPD_ATTEMPT=$((PPD_ATTEMPT + 1))\n'
        f'  sleep 1\n'
        f'done\n'
        f'PPD_MATCH_COUNT=$(printf \'%s\\n\' "$PPD_MATCH" | grep -c . || true)\n'
        f'if [ -z "$PPD_MATCH" ]; then\n'
        f'  echo "WARNING: no brlaser PPD matched {quoted_model} for printer {quoted_name} after '
        f'5 attempts -- skipping registration (is brlaser installed? try a shorter driver_model '
        f'search term)" >&2\n'
        f'elif [ "$PPD_MATCH_COUNT" -gt 1 ]; then\n'
        f'  echo "WARNING: {quoted_model} matched more than one brlaser PPD for printer '
        f'{quoted_name} -- refusing to guess, skipping registration. Matches:" >&2\n'
        f'  printf \'%s\\n\' "$PPD_MATCH" >&2\n'
        f'else\n'
        f'  PPD_URI="${{PPD_MATCH%% *}}"\n'
        f'  lpadmin -p {quoted_name} -v {quoted_uri} -E -m "$PPD_URI"{location_arg}\n'
        f'  echo "registered printer: {name} (brlaser: $PPD_URI)"\n'
        f'fi'
    )


def build_cups_pdf_conf(options: dict) -> str | None:
    """Render /etc/cups/cups-pdf.conf for the optional paperless_upload feature.

    Returns None -- writing nothing -- when `paperless_upload.enabled` is
    false (the shipped default) or `queue_name` fails validation (D-07):
    generate_config.py never registers the queue, no cups-pdf.conf is
    generated, no outbox directories are created. Mirrors
    `build_admin_provisioning`'s fail-safe-None-return pattern.

    When valid, reads the stock template from
    PAPERLESS_UPLOAD_CUPS_PDF_CONF_STOCK_PATH (falling back to an empty
    string if the stock file is missing -- same defensive posture as
    `build_cupsd_conf`'s stock-backup fallback) and APPENDS four active
    directive lines at the end, never regex-patching the stock file's own
    commented example lines:
      - `Out <outbox>/incoming` / `AnonDirName <outbox>/incoming` -- both
        point at the SAME fixed absolute path (D-05): every job lands flat
        in one directory regardless of username, whether cups-pdf resolves
        a real system user or falls back to its AnonUser="nobody" default
        (left untouched here).
      - `Label 2` -- fixed, not configurable: guarantees filename
        uniqueness via a `-job_<id>` suffix even for identical titles
        landing in the same shared directory (also required by the
        upload-worker's/PostProcess hook's title-recovery mechanism, see
        `build_paperless_postprocess_hook`).
      - `PostProcessing <hook path>` -- the best-effort title-sidecar
        writer (cups-pdf's own directive name is `PostProcessing`, verified
        against the stock template's own documented `### Key:
        PostProcessing (config, lptoptions)` stanza -- NOT `PostProcess`).
    """
    upload = options.get("paperless_upload") or {}
    enabled = bool(upload.get("enabled", False))
    if not enabled:
        return None

    queue_name = str(upload.get("queue_name", "PDF-to-DMS") or "PDF-to-DMS")
    if not NAME_RE.match(queue_name):
        print(
            f"WARNING: paperless_upload.queue_name {queue_name!r} failed validation -- must "
            f"match {NAME_RE.pattern}, cups-pdf queue not registered",
            flush=True,
        )
        return None

    stock_path = Path(PAPERLESS_UPLOAD_CUPS_PDF_CONF_STOCK_PATH)
    try:
        template = stock_path.read_text() if stock_path.exists() else ""
    except OSError as exc:
        print(
            f"WARNING: could not read {PAPERLESS_UPLOAD_CUPS_PDF_CONF_STOCK_PATH}: {exc} -- "
            "using an empty template",
            flush=True,
        )
        template = ""

    lines = [template.rstrip("\n")] if template.strip() else []
    lines += [
        f"Out {PAPERLESS_UPLOAD_OUTBOX_ROOT}/incoming",
        f"AnonDirName {PAPERLESS_UPLOAD_OUTBOX_ROOT}/incoming",
        "Label 2",
        f"PostProcessing {PAPERLESS_UPLOAD_POSTPROCESS_HOOK_PATH}",
    ]
    return "\n".join(lines) + "\n"


def build_paperless_postprocess_hook() -> str:
    """Render the PostProcess hook script cups-pdf invokes for every job.

    cups-pdf's `PostProcessing` directive invokes the configured script via a
    plain `system()` call with exactly three positional arguments: `$1` the
    final absolute path of the generated PDF, `$2` the resolved username
    cups-pdf wrote the file as, `$3` the original job-submitting username --
    NOT a title-carrying environment variable (see this plan's
    `<researched_correction>` -- verified against cups-pdf's own upstream C
    source). cups-pdf's own `preparetitle()` logic already derives the
    final PDF's filename directly from the print job's title (sanitized,
    extension-stripped), with `Label 2` (set in build_cups_pdf_conf) adding
    a `-job_<id>` disambiguating SUFFIX for collision-safety in this
    add-on's single shared output directory (D-05). So the title is fully
    recoverable from `$1`'s basename, after stripping that suffix -- zero
    need for an env var that does not exist.

    Static (no options needed): a short POSIX `sh` script that embeds a
    `python3 - "$1" <<'PYEOF' ... PYEOF` block (mirrors the exact
    heredoc-embedding idiom already used by
    `build_printer_uuid_fixup_script`'s `_PRINTER_UUID_FIXUP_PYTHON_TEMPLATE`)
    which strips the `-job_<N>` suffix, trims + caps the result at 128 chars
    (D-14 -- paperless-ngx's Document.title field length; trim+cap only, no
    filesystem sanitization, since this becomes an API string, never a
    filename), and writes `{"title": "<derived-title>"}` to a same-basename
    `.json` sidecar next to the PDF via a temp-file + `os.replace()` (atomic,
    mirrors `save_last_seen_job_id`'s idiom in print-history-poller.py).

    The whole hook ALWAYS exits 0 regardless of any internal failure (D-13:
    PostProcess is best-effort only and must never affect the
    already-completed print job -- cups-pdf's own `system()` call return
    value is only used for logging on the C side, so this `|| true` +
    trailing `exit 0` is defense-in-depth, not the only guarantee).
    """
    python_block = (
        "import json\n"
        "import os\n"
        "import re\n"
        "import sys\n"
        "\n"
        "pdf_path = sys.argv[1]\n"
        "basename = os.path.basename(pdf_path)\n"
        'if basename.lower().endswith(".pdf"):\n'
        "    basename = basename[:-4]\n"
        r'title = re.sub(r"-job_\d+$", "", basename).strip()[:128]' "\n"
        "\n"
        'sidecar_path = os.path.splitext(pdf_path)[0] + ".json"\n'
        'tmp_path = sidecar_path + ".tmp"\n'
        'with open(tmp_path, "w") as f:\n'
        '    json.dump({"title": title}, f)\n'
        "os.replace(tmp_path, sidecar_path)\n"
    )
    return (
        "#!/bin/sh\n"
        "# PostProcess hook -- see build_paperless_postprocess_hook() docstring.\n"
        "# $1=final PDF path, $2=resolved job user, $3=original job-submitting user.\n"
        "# Best-effort only (D-13): never blocks or fails the already-completed print job.\n"
        "(\n"
        '  python3 - "$1" <<\'PYEOF\'\n'
        f"{python_block}"
        "PYEOF\n"
        ") || true\n"
        "exit 0\n"
    )


def build_cups_pdf_registration_snippet(options: dict) -> tuple[str | None, str | None]:
    """Render the cups-pdf queue's `lpadmin` registration snippet.

    Mirrors `build_brlaser_registration_snippet`'s exact shape (retry loop
    up to 5 attempts x 1s against `lpinfo -m`, matched via `grep -iF --`
    against PAPERLESS_UPLOAD_PPD_SEARCH_TERM instead of a user-supplied
    `driver_model`, same zero-match/multi-match WARNING-and-skip safety
    net) -- this reuses the exact same printer-registration/Avahi code path
    as the physical printer queue, so the cups-pdf queue is Avahi/AirPrint-
    advertised identically and appears in iOS/macOS Print sheets without
    extra client setup (D-02).

    Validates `queue_name` against NAME_RE and optional `location` against
    LOCATION_RE (reusing both constants directly, not new regexes).
    Registers via `lpadmin -p <queue_name> -v cups-pdf:/ -E -m "$PPD_URI"
    [-L <location>]`, argv-quoted exactly like the existing printer-
    registration code (T-21-01 mitigation extended to this phase's new
    values).

    Returns (None, None) when `paperless_upload.enabled` is false or
    `queue_name` fails validation. Returns (snippet_text, queue_name)
    otherwise -- the caller appends `queue_name` into the same
    `registered_names` list build_printer_uuid_fixup_script() consumes, so
    D-08's UUID-stability fixup covers the new queue automatically.
    """
    upload = options.get("paperless_upload") or {}
    enabled = bool(upload.get("enabled", False))
    if not enabled:
        return None, None

    queue_name = str(upload.get("queue_name", "PDF-to-DMS") or "PDF-to-DMS")
    if not NAME_RE.match(queue_name):
        print(
            f"WARNING: paperless_upload.queue_name {queue_name!r} failed validation -- must "
            f"match {NAME_RE.pattern}, cups-pdf queue not registered",
            flush=True,
        )
        return None, None

    location = str(upload.get("location", "") or "").strip()
    if location and not LOCATION_RE.match(location):
        print(
            f"WARNING: paperless_upload.location invalid value {location!r} -- must match "
            f"{LOCATION_RE.pattern}, registering cups-pdf queue without a location",
            flush=True,
        )
        location = ""

    quoted_term = shlex.quote(PAPERLESS_UPLOAD_PPD_SEARCH_TERM)
    quoted_name = shlex.quote(queue_name)
    quoted_uri = shlex.quote(CUPS_PDF_DEVICE_URI)
    location_arg = f" -L {shlex.quote(location)}" if location else ""
    snippet = (
        f'PPD_MATCH=""\n'
        f"PPD_ATTEMPT=0\n"
        f'while [ "$PPD_ATTEMPT" -lt 5 ]; do\n'
        f"  PPD_MATCH=$(lpinfo -m 2>/dev/null | grep -iF -- {quoted_term} || true)\n"
        f'  [ -n "$PPD_MATCH" ] && break\n'
        f"  PPD_ATTEMPT=$((PPD_ATTEMPT + 1))\n"
        f"  sleep 1\n"
        f"done\n"
        f"PPD_MATCH_COUNT=$(printf '%s\\n' \"$PPD_MATCH\" | grep -c . || true)\n"
        f'if [ -z "$PPD_MATCH" ]; then\n'
        f'  echo "WARNING: no cups-pdf PPD matched {quoted_term} for queue {quoted_name} after '
        f'5 attempts -- skipping registration (is cups-pdf installed?)" >&2\n'
        f'elif [ "$PPD_MATCH_COUNT" -gt 1 ]; then\n'
        f'  echo "WARNING: {quoted_term} matched more than one cups-pdf PPD for queue '
        f'{quoted_name} -- refusing to guess, skipping registration. Matches:" >&2\n'
        f"  printf '%s\\n' \"$PPD_MATCH\" >&2\n"
        f"else\n"
        f'  PPD_URI="${{PPD_MATCH%% *}}"\n'
        f'  lpadmin -p {quoted_name} -v {quoted_uri} -E -m "$PPD_URI"{location_arg}\n'
        f'  echo "registered printer: {queue_name} (cups-pdf: $PPD_URI)"\n'
        f"fi"
    )
    return snippet, queue_name


def build_printer_registration(options: dict) -> tuple[str, list[str]]:
    """Render /tmp/register-printers.sh: one validated, quoted lpadmin call per entry.

    Invalid entries (bad name, unsupported uri scheme) are skipped and logged
    rather than crashing lpadmin or the whole add-on. `enabled` defaults to
    true when absent (D-04's discretion default). An optional `location`
    field (e.g. "Office") is passed through as `lpadmin -L <location>` when
    present and non-empty -- omitted entirely when absent, since an empty
    `-L ""` would just clear any location a user might set later via the web
    UI. An invalid `location` value is skipped (with a WARNING) but does not
    abort registration of the rest of that printer's fields.

    `driver` selects the PPD model used at registration (D-14): omitted or
    `"generic"` (the default) preserves this add-on's original behavior
    byte-for-byte -- `drv:///sample.drv/generic.ppd`. `"brlaser"` defers PPD
    resolution into the generated script itself, see
    `build_brlaser_registration_snippet`.

    The second return value, `registered_names`, is the exact list of `name`
    values that passed every validation gate above (`enabled`, `NAME_RE`,
    uri-scheme, `driver`) -- the same list `build_printer_uuid_fixup_script()`
    consumes, so there is no drift between what gets registered and what gets
    UUID-fixed-up.
    """
    printers = options.get("printers") or []
    lines = ["#!/bin/sh", "set -e", ""]
    registered_names: list[str] = []

    for entry in printers:
        if not isinstance(entry, dict):
            print(f"WARNING: skipping non-object printers[] entry: {entry!r}", flush=True)
            continue

        name = str(entry.get("name", ""))
        uri = str(entry.get("uri", ""))
        enabled = entry.get("enabled", True)

        if not enabled:
            print(f"INFO: printer '{name}' has enabled=false, skipping registration", flush=True)
            continue

        if not NAME_RE.match(name):
            print(
                f"WARNING: skipping printer with invalid name {name!r} -- must match {NAME_RE.pattern}",
                flush=True,
            )
            continue

        scheme = urlsplit(uri).scheme.lower()
        if scheme not in ALLOWED_URI_SCHEMES:
            print(
                f"WARNING: skipping printer '{name}' -- uri scheme '{scheme}' not in allowlist "
                f"{sorted(ALLOWED_URI_SCHEMES)}",
                flush=True,
            )
            continue

        location = str(entry.get("location", "") or "").strip()
        if location and not LOCATION_RE.match(location):
            print(
                f"WARNING: skipping location for printer '{name}' -- invalid value "
                f"{location!r}, must match {LOCATION_RE.pattern}",
                flush=True,
            )
            location = ""

        driver = str(entry.get("driver", "generic") or "generic").strip().lower()
        if driver not in ALLOWED_DRIVERS:
            print(
                f"WARNING: skipping printer '{name}' -- unknown driver {driver!r}, must be one "
                f"of {sorted(ALLOWED_DRIVERS)}",
                flush=True,
            )
            continue

        if driver == "brlaser":
            driver_model = str(entry.get("driver_model", "") or "").strip()
            if not driver_model:
                print(
                    f"WARNING: skipping printer '{name}' -- driver=brlaser requires "
                    "driver_model (a search term matched against lpinfo -m output, e.g. "
                    "'MFC-7460DN')",
                    flush=True,
                )
                continue
            if not DRIVER_MODEL_RE.match(driver_model):
                print(
                    f"WARNING: skipping printer '{name}' -- invalid driver_model "
                    f"{driver_model!r}, must match {DRIVER_MODEL_RE.pattern}",
                    flush=True,
                )
                continue
            lines.append(build_brlaser_registration_snippet(name, uri, driver_model, location))
            registered_names.append(name)
            continue

        # driver == "generic": argv-array construction, never an interpolated
        # shell string (T-21-01 mitigation). `-m everywhere` was tried first
        # (CUPS's driverless IPP-Everywhere model) but proved unavailable
        # during the Task 2 smoke test: it performs a live IPP capability
        # query against the device AT REGISTRATION TIME, so any printer that
        # happens to be powered off/unreachable when the add-on (re)starts
        # fails to register at all -- defeating the point of a persistent
        # print queue. `-m drv:///sample.drv/generic.ppd` (a static generic
        # PostScript driver, CUPS's documented fallback model) registers the
        # queue unconditionally; CUPS only contacts the device when a job is
        # actually printed. (This is also the exact behavior D-14's
        # `driver: brlaser` option exists to opt out of, for printers with no
        # real PostScript support.)
        argv = ["lpadmin", "-p", name, "-v", uri, "-E", "-m", GENERIC_PPD]
        if location:
            argv += ["-L", location]

        lines.append(" ".join(shlex.quote(a) for a in argv))
        lines.append(f'echo "registered printer: {name}"')
        registered_names.append(name)

    lines.append("")
    return "\n".join(lines), registered_names


def compute_stable_printer_uuid(name: str) -> str:
    """Return a deterministic UUID derived from a printer's own `name`.

    Root cause this fixes (found live on haos-op3050-1, three consecutive
    add-on restarts confirmed assigning three DIFFERENT random UUIDs to
    the SAME printer: a12d7b3a-... -> 01087e95-... -> 740a4011-...): this
    add-on's /etc/cups/ is not persisted outside /data, so cupsd starts
    every single boot with a completely empty printers.conf, and
    `lpadmin -m` always creates the printer "fresh" from cupsd's own
    point of view -- including a brand-new random printer-uuid every
    time. iOS/AirPrint caches discovered printers keyed by UUID, so after
    enough restarts the user sees multiple "ghost" duplicate entries for
    the same printer name in iOS's print sheet.

    `uuid.uuid5(PRINTER_UUID_NAMESPACE, name)` is deterministic: the SAME
    `name` always produces the SAME UUID, on this host or any other host
    running this add-on, forever -- exactly the stability AirPrint
    discovery needs. A renamed printer queue gets a NEW uuid5 output,
    which is semantically correct: a rename IS a new identity as far as
    AirPrint discovery is concerned.

    `lpadmin -p <name> -o printer-uuid=urn:uuid:<value>` was tried FIRST
    and confirmed REJECTED (tested live against this add-on's own running
    CUPS v2.4.19: lpadmin exited 0, but the on-disk UUID in
    printers.conf was completely unchanged afterward -- `printer-uuid` is
    not a documented lpadmin -o attribute). This function's output is
    instead patched directly into printers.conf by
    `build_printer_uuid_fixup_script()`, while cupsd is fully stopped --
    see that function's docstring for why a live edit + SIGHUP reload is
    deliberately NOT used instead.
    """
    return str(uuid.uuid5(PRINTER_UUID_NAMESPACE, name))


_PRINTER_UUID_FIXUP_PYTHON_TEMPLATE = '''\
import re
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

fixups = %(fixups)s

# Non-nested <Printer NAME>...</Printer> stanza -- printers.conf never
# nests these, so a non-greedy DOTALL scan always isolates exactly one
# printer's own block before the next <Printer ...> starts.
block_re = re.compile(r"<Printer ([^>]+)>.*?</Printer>", re.DOTALL)
uuid_line_re = re.compile(r"UUID urn:uuid:[0-9a-fA-F-]+")


def _patch(match):
    block, printer_name = match.group(0), match.group(1)
    new_uuid = fixups.get(printer_name)
    if new_uuid is None:
        return block
    patched, count = uuid_line_re.subn("UUID urn:uuid:" + new_uuid, block, count=1)
    if count == 1:
        print("INFO: fixed up UUID for printer " + repr(printer_name) + " -> " + new_uuid)
        return patched
    print("INFO: printer " + repr(printer_name) + " stanza has no UUID line -- skipping fixup")
    return block


new_content = block_re.sub(_patch, content)
found_names = set(re.findall(r"<Printer ([^>]+)>", content))
for fixup_name in fixups:
    if fixup_name not in found_names:
        print(
            "INFO: printer " + repr(fixup_name) + " stanza not found in printers.conf -- "
            "registration likely failed/was skipped, skipping UUID fixup"
        )

with open(path, "w") as f:
    f.write(new_content)
'''


def build_printer_uuid_fixup_script(names: list[str]) -> str | None:
    """Render /tmp/fixup-printer-uuids.sh: patches printers.conf UUID lines.

    Only accepts `names` already validated by build_printer_registration()'s
    own enabled/NAME_RE/uri-scheme/driver gates -- reusing that exact list
    (rather than re-validating printers[] independently here) avoids any
    drift between which printers get registered and which get their UUID
    fixed up.

    printers.conf must never be edited while cupsd is running: the file's
    own generated header says so verbatim ("DO NOT EDIT THIS FILE WHEN
    CUPSD IS RUNNING"), and a real GitHub issue (apple/cups#2590)
    documents the corruption/crash risk of a live edit + SIGHUP reload.
    So this returns a script run.sh is expected to run ONLY while cupsd
    is fully stopped (see run.sh's new boot phase) -- this function does
    not stop/start cupsd itself, it only renders the patch.

    The returned script guards on printers.conf existing at all, then
    feeds a small embedded Python program (not shell text-processing --
    more robust for a scoped, provably-correct multi-line stanza edit)
    the file path via argv. That program:
      - finds every non-nested `<Printer NAME>...</Printer>` block via a
        non-greedy DOTALL regex (CUPS's own stanzas never nest, so this
        always isolates exactly one printer's block before the next
        `<Printer ...>` starts)
      - for each block whose captured NAME is a key in the `fixups` dict
        (the name -> compute_stable_printer_uuid(name) mapping computed
        HERE, at generate time, and embedded as a literal dict), replaces
        ONLY that block's own first `UUID urn:uuid:...` line's value --
        the substitution happens against the ISOLATED block substring,
        never the whole file, so it is provably scoped to that one
        stanza and can never touch a different printer's UUID line
      - every other block (a name not in `fixups`, e.g. one this add-on
        does not manage) is returned completely unchanged
      - a name in `fixups` whose stanza is not found in printers.conf at
        all (registration failed/was skipped at runtime, e.g. brlaser's
        `driver_model` matched zero or more than one PPD) logs one INFO
        line and is otherwise a no-op for that name -- never a hard
        failure

    Returns None -- writing nothing -- when `names` is empty (no printer
    passed build_printer_registration()'s validation gates, so there is
    nothing to fix up).
    """
    if not names:
        return None

    fixups_literal = "{\n" + ",\n".join(
        f"    {name!r}: {compute_stable_printer_uuid(name)!r}" for name in names
    ) + ",\n}"
    patch_program = _PRINTER_UUID_FIXUP_PYTHON_TEMPLATE % {"fixups": fixups_literal}

    return (
        "#!/bin/sh\n"
        "set -e\n"
        f'PRINTERS_CONF="{PRINTERS_CONF_PATH}"\n'
        'if [ ! -f "$PRINTERS_CONF" ]; then\n'
        '  echo "WARNING: $PRINTERS_CONF not found -- skipping printer UUID fixup" >&2\n'
        "else\n"
        "  python3 - \"$PRINTERS_CONF\" <<'PYEOF'\n"
        f"{patch_program}"
        "PYEOF\n"
        "fi\n"
    )


def build_log_level_env(options: dict) -> str:
    """Render /tmp/cups-log-level.env: LOG_LEVEL + CUPS_LOG_LEVEL shell vars.

    Root cause this fixes: `bashio::config 'log_level'` (the mechanism used
    before this fix) calls `bashio::addon.config`, which ALWAYS queries the
    Supervisor API over HTTP -- there is no local-file fallback anywhere in
    bashio's own implementation. In a bare `docker run` test harness with no
    real Supervisor to answer that call (see internal/verify-cups-scaffold.sh),
    the call fails silently and returns an empty string, which the old
    run.sh case-statement's `*)` branch then defaulted to "info" -- meaning
    ANY configured log_level value was silently ignored in that harness, and
    only "worked" for the pre-existing test fixture because "info" also
    happened to be that same fallback default. This add-on already reads
    every other option directly from /data/options.json in this exact
    script (see `load_options`); log_level is resolved the same way here.

    An unrecognized/invalid value (should not happen given config.yaml's own
    schema enum, but defensive) falls back to "info" -- the same fallback
    behavior as before.
    """
    raw = str(options.get("log_level", "warning") or "warning").strip().lower()
    if raw not in ALLOWED_LOG_LEVELS:
        print(
            f"WARNING: log_level {raw!r} is not one of {sorted(ALLOWED_LOG_LEVELS)} -- "
            "falling back to 'info'",
            flush=True,
        )
        raw = "info"
    cups_level = _LOG_LEVEL_TO_CUPSCTL[raw]
    return f'LOG_LEVEL="{raw}"\nCUPS_LOG_LEVEL="{cups_level}"\n'


def build_admin_provisioning(options: dict) -> str | None:
    """Render /tmp/provision-admin.sh: idempotent CUPS web-admin account setup.

    Root cause this fixes (D-12 follow-up): `/admin` returned 403 for everyone,
    with no way to authenticate at all even once network access is granted (see
    `build_cupsd_conf`'s `<Location /admin>` widening above) -- this image's
    only account (`root`) has a shadow entry of `*` (password disabled, can
    never authenticate), and there is no PAM config, so cupsd authenticates
    directly against `/etc/shadow` via `crypt()`.

    When BOTH `admin_username` and `admin_password` are set (non-empty),
    returns a script that -- at every container start, since this container's
    filesystem is not persisted outside `/data` and `/etc/passwd`/`/etc/shadow`
    reset to the stock image on every restart/update -- creates the account if
    absent (or just resets its password if present), adds it to the `lpadmin`
    group (the `SystemGroup` `@SYSTEM` checks), and sets its password via
    `chpasswd`. Returns None -- writing nothing -- when either option is
    empty/unset (the shipped default), preserving the exact pre-fix fail-safe
    behavior: `/admin` stays unauthenticatable, not an open admin panel by
    default.

    Validates both values BEFORE embedding them into the generated script
    (`shlex.quote`'d, never an interpolated shell string -- T-21-01's
    mitigation, same as `build_printer_registration`): an invalid
    `admin_username` (must match `ADMIN_USERNAME_RE`), a mismatched pair (one
    set, the other empty -- a misconfiguration, not a silent partial no-op),
    or an `admin_password` containing a newline or colon (would corrupt the
    `user:password` line fed to `chpasswd`'s stdin -- a newline in particular
    could inject an entirely separate line, silently overwriting a DIFFERENT
    account's password) all return None with a WARNING logged here, at
    generate time. The password itself is never printed to the logs.

    A run-time-only failure -- `adduser`/`addgroup`/`chpasswd` itself failing,
    or the requested username colliding with an existing system account below
    uid 1000 (`root`, `lp`, `avahi`, ... -- a typo must never silently reset a
    system account's password) -- cannot be known at generate time, so those
    checks are written INTO the generated script and logged when `run.sh`
    actually executes it, not here.
    """
    username = str(options.get("admin_username", "") or "")
    password = str(options.get("admin_password", "") or "")

    if not username and not password:
        return None

    if username and not password:
        print(
            "WARNING: admin_username is set but admin_password is empty -- both are required "
            "together, admin account not provisioned",
            flush=True,
        )
        return None
    if password and not username:
        print(
            "WARNING: admin_password is set but admin_username is empty -- both are required "
            "together, admin account not provisioned",
            flush=True,
        )
        return None

    if not ADMIN_USERNAME_RE.match(username):
        print(
            f"WARNING: admin_username {username!r} failed validation -- must match "
            f"{ADMIN_USERNAME_RE.pattern}, admin account not provisioned",
            flush=True,
        )
        return None

    if "\n" in password or ":" in password:
        print(
            "WARNING: admin_password contains a newline or colon -- refusing to use it (would "
            "corrupt the generated chpasswd input), admin account not provisioned",
            flush=True,
        )
        return None

    quoted_user = shlex.quote(username)
    quoted_pass = shlex.quote(password)

    # `username` itself is already ADMIN_USERNAME_RE-validated (letters,
    # digits, underscore, hyphen only -- no shell metacharacters), so it is
    # also safe to interpolate directly into the echo/log text below, exactly
    # like `build_brlaser_registration_snippet` does for its own validated
    # `name`. `quoted_user`/`quoted_pass` are used for every actual command
    # argument/stdin value.
    return (
        "#!/bin/sh\n"
        f"if getent passwd {quoted_user} >/dev/null 2>&1; then\n"
        f"  EXISTING_UID=$(getent passwd {quoted_user} | cut -d: -f3)\n"
        '  if [ "$EXISTING_UID" -lt 1000 ] 2>/dev/null; then\n'
        f'    echo "WARNING: admin_username {username} collides with an existing system '
        'account (uid=$EXISTING_UID) -- refusing to touch it, admin account not provisioned. '
        'Choose a different admin_username." >&2\n'
        "    exit 0\n"
        "  fi\n"
        f'  echo "admin account {username} already exists (uid=$EXISTING_UID) -- updating its '
        'password"\n'
        "else\n"
        f"  if ! adduser -D -H -s /sbin/nologin {quoted_user}; then\n"
        f'    echo "WARNING: adduser failed for {username} -- admin account not provisioned" '
        ">&2\n"
        "    exit 0\n"
        "  fi\n"
        f'  echo "created admin account {username}"\n'
        "fi\n"
        f"if id -Gn {quoted_user} 2>/dev/null | grep -qw lpadmin; then\n"
        "  :\n"
        f"elif addgroup {quoted_user} lpadmin; then\n"
        f'  echo "added {username} to the lpadmin group (required for @SYSTEM auth)"\n'
        "else\n"
        f'  echo "WARNING: could not add {username} to lpadmin -- @SYSTEM auth would reject '
        'this account" >&2\n'
        "fi\n"
        f"if printf '%s:%s\\n' {quoted_user} {quoted_pass} | chpasswd; then\n"
        f'  echo "admin account {username} password set -- CUPS /admin login is now usable"\n'
        "else\n"
        f'  echo "WARNING: chpasswd failed for {username} -- password not set, login will not '
        'work" >&2\n'
        "fi\n"
    )


def main() -> None:
    options = load_options()

    avahi_conf = build_avahi_conf(options)
    Path(AVAHI_CONF_PATH).write_text(avahi_conf)
    print(f"Config written to {AVAHI_CONF_PATH}", flush=True)

    cupsd_conf = build_cupsd_conf(detect_primary_interface(), options)
    if cupsd_conf is not None:
        Path(CUPSD_CONF_PATH).write_text(cupsd_conf)
        print(f"Config written to {CUPSD_CONF_PATH}", flush=True)
    else:
        print(
            f"{CUPSD_CONF_PATH} left unpatched (see WARNING above) -- likely still "
            "localhost-only",
            flush=True,
        )

    register_script, registered_printer_names = build_printer_registration(options)

    cups_pdf_snippet, cups_pdf_queue_name = build_cups_pdf_registration_snippet(options)
    if cups_pdf_snippet is not None:
        register_script += "\n" + cups_pdf_snippet + "\n"
        registered_printer_names.append(cups_pdf_queue_name)

    script_path = Path(REGISTER_SCRIPT_PATH)
    script_path.write_text(register_script)
    script_path.chmod(0o755)
    print(f"Config written to {REGISTER_SCRIPT_PATH}", flush=True)

    uuid_fixup_script = build_printer_uuid_fixup_script(registered_printer_names)
    if uuid_fixup_script is not None:
        uuid_fixup_path = Path(PRINTER_UUID_FIXUP_SCRIPT_PATH)
        uuid_fixup_path.write_text(uuid_fixup_script)
        uuid_fixup_path.chmod(0o755)
        print(f"Config written to {PRINTER_UUID_FIXUP_SCRIPT_PATH}", flush=True)

    admin_script = build_admin_provisioning(options)
    if admin_script is not None:
        admin_script_path = Path(ADMIN_PROVISION_SCRIPT_PATH)
        admin_script_path.write_text(admin_script)
        admin_script_path.chmod(0o755)
        print(f"Config written to {ADMIN_PROVISION_SCRIPT_PATH}", flush=True)

    log_level_env = build_log_level_env(options)
    Path(LOG_LEVEL_ENV_PATH).write_text(log_level_env)
    print(f"Config written to {LOG_LEVEL_ENV_PATH}", flush=True)

    # paperless_upload (D-07): cups-pdf.conf + outbox stage dirs + PostProcess
    # hook, independent of the registration snippet above -- writes nothing
    # at all under /data or /etc/cups when paperless_upload.enabled is false,
    # so existing installations see zero change.
    cups_pdf_conf = build_cups_pdf_conf(options)
    if cups_pdf_conf is not None:
        Path(PAPERLESS_UPLOAD_CUPS_PDF_CONF_PATH).write_text(cups_pdf_conf)
        print(f"Config written to {PAPERLESS_UPLOAD_CUPS_PDF_CONF_PATH}", flush=True)

        outbox_root = Path(PAPERLESS_UPLOAD_OUTBOX_ROOT)
        for stage in ("incoming", "processing", "sent", "failed"):
            stage_dir = outbox_root / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            stage_dir.chmod(0o777)
        print(f"Outbox directories created under {PAPERLESS_UPLOAD_OUTBOX_ROOT}", flush=True)

        hook_path = Path(PAPERLESS_UPLOAD_POSTPROCESS_HOOK_PATH)
        hook_path.write_text(build_paperless_postprocess_hook())
        hook_path.chmod(0o755)
        print(f"Config written to {PAPERLESS_UPLOAD_POSTPROCESS_HOOK_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
