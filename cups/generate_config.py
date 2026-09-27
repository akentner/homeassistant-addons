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
    Each entry's optional `presets` field injects Apple's AirPrint PPD
    extension `*APPrinterPreset <slug>/<display-name>: "..." *End` stanzas
    (see cups.org/doc/spec-ppd.html) into that printer's live PPD after its
    own registration line above -- bundling one or more of that printer's
    OWN already-existing PPD option/choice pairs (e.g. Duplex + Resolution)
    into a single named entry iOS's print sheet shows as a "Preset"/
    "Vorlage" list, instead of separate Duplex/Resolution controls nested
    under "Optionen". `presets` is a flattened `<name>|<Key=Value> ...;...`
    string, not a nested options-schema list -- HA's add-on options schema
    micro-language caps list/dict nesting at depth two
    (developers.home-assistant.io/docs/add-ons/configuration), and
    `printers[]` is already a depth-two list-of-objects, so a `presets[]`
    list-of-objects nested inside it would be a third level and cannot be
    expressed in `schema:` (see `build_preset_injection_snippet` for the
    parser). Injection always operates on a TEMP copy of the printer's
    CURRENT on-disk PPD (`cp` then `cat >>` then `lpadmin -P`, never
    editing `/etc/cups/ppd/<name>.ppd` in place), so this is idempotent
    across restarts exactly like the brlaser PPD resolution above: every
    start first (re)generates a fresh, preset-free PPD for that printer,
    and only then does this step append presets to that fresh copy --
    never compounding duplicate stanzas across restarts.
  - /tmp/provision-admin.sh: one idempotent account-setup script, present ONLY
    when both `admin_username` and `admin_password` validate (see
    `build_admin_provisioning`) -- creates/updates a real system login for
    CUPS's web admin UI (`/admin`), added to the `lpadmin` group so it
    satisfies `Require user @SYSTEM`. Executed by run.sh before cupsd starts,
    every single start, because this container's filesystem is not persisted
    outside /data and /etc/passwd/shadow reset on every restart/update.
"""

import ipaddress
import json
import re
import shlex
import socket
import struct
import sys
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

# Linux/BusyBox username convention (adduser enforces a similar check itself,
# but this is validated BEFORE being embedded into the generated shell script
# below -- defense in depth, same posture as NAME_RE/IFACE_RE/LOCATION_RE):
# lowercase letters/digits/underscore/hyphen, must start with a letter or
# underscore, max 32 chars total.
ADMIN_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

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

# Matches a preset's display-name text (the part after the slash in an
# *APPrinterPreset <slug>/<display-name>: line). Same conservative
# printable-ASCII-minus-quotes allowlist as LOCATION_RE, but PPD
# "keyword/text:" line syntax reserves "/" and ":" as delimiters -- a
# display name containing either would corrupt the stanza's own syntax,
# so both are excluded here (on top of LOCATION_RE's existing exclusion
# of quotes/control characters). Same 127-char cap as LOCATION_RE.
PRESET_NAME_RE = re.compile(r"^[A-Za-z0-9 ,.\-_()]{1,127}$")

# Matches one "Key=Value" token inside a printers[].presets options
# string. Key: a PPD option keyword -- starts with a letter, then
# letters/digits (PPD keyword-length convention, capped at 40 chars).
# Value: a PPD choice keyword -- starts alphanumeric, then
# alnum/dot/underscore/hyphen (covers DuplexNoTumble, 1200x600dpi,
# 600dpi, Auto), capped at 64 chars. This add-on does NOT verify these
# against the printer's actual live PPD option list (that would require
# a runtime lpoptions query per printer, out of scope) -- operators
# discover valid Key/Value pairs themselves via `lpoptions -p <printer>
# -l` (see cups/DOCS.md), the same command this add-on's DOCS.md already
# points operators at for the duplex option.
PRESET_OPTION_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,39}=[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Matches the run of characters slugify_preset_id() collapses to a
# single underscore when deriving a PPD keyword identifier from a
# preset's display name.
_PRESET_SLUG_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]+")

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


def slugify_preset_id(name: str, used_slugs: set[str]) -> str:
    """Derive a PPD keyword identifier from a preset's display `name`.

    PPD keyword syntax (the slug half of `*APPrinterPreset <slug>/<name>:`)
    is stricter than PRESET_NAME_RE's display-text allowlist, so this is
    NEVER operator-authored directly: sanitizes to ASCII letters/digits/
    underscore only (any run of other characters -- spaces, commas,
    periods, hyphens, parentheses -- collapses to a single underscore),
    lowercased for consistency, capped at 40 chars (matching
    PRESET_OPTION_TOKEN_RE's own keyword-length convention). A result that
    doesn't start with a letter (all characters stripped, or a leading
    digit) is prefixed with `preset_` -- PPD keywords conventionally start
    with a letter. Collisions against `used_slugs` (already-seen slugs for
    THIS printer -- callers create a fresh set per printer, since PPD
    keyword uniqueness only matters within one printer's own PPD file) are
    de-duplicated by appending `_2`, `_3`, ... -- this is why this function
    takes and mutates a shared `used_slugs` set across every preset on one
    printer, not just a single name in isolation.
    """
    base = _PRESET_SLUG_SANITIZE_RE.sub("_", name.strip().lower()).strip("_")
    if not base or not base[0].isalpha():
        base = f"preset_{base}" if base else "preset"
    base = base[:40]
    slug = base
    suffix = 2
    while slug in used_slugs:
        slug = f"{base}_{suffix}"[:40]
        suffix += 1
    used_slugs.add(slug)
    return slug


def _parse_presets_field(raw: str) -> list[tuple[str, str]]:
    """Split a printers[].presets flattened string into (name, options) pairs.

    Format: semicolon-separated preset entries, each `<name>|<options>` --
    see PRESET_NAME_RE/PRESET_OPTION_TOKEN_RE's docstrings above for why
    `|` and `;` are safe delimiters (neither character is in either
    regex's allowed charset, so a VALID name/options value can never
    itself contain one). This flattened shape is a deliberate fallback:
    HA's add-on options schema micro-language caps nested list/dict depth
    at two (developers.home-assistant.io/docs/add-ons/configuration/) --
    printers[] is already a depth-two list-of-objects, so a nested
    presets[] list-of-objects would be a third level and cannot be
    expressed in `schema:`. Returns raw, UNVALIDATED pairs -- callers
    validate each half with PRESET_NAME_RE/PRESET_OPTION_TOKEN_RE. An
    entry with no `|` (no options half at all) is skipped here directly
    with a WARNING, since there is no options string left to validate.
    """
    pairs: list[tuple[str, str]] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "|" not in chunk:
            print(
                f"WARNING: skipping malformed presets entry {chunk!r} -- expected "
                "'<name>|<Key=Value ...>'",
                flush=True,
            )
            continue
        preset_name, _, preset_options = chunk.partition("|")
        pairs.append((preset_name.strip(), preset_options.strip()))
    return pairs


def build_preset_injection_snippet(name: str, presets_raw: str) -> str | None:
    """Render sh that injects validated *APPrinterPreset stanzas into a
    printer's live PPD and reloads it into cupsd.

    Root cause this fixes: Apple's AirPrint PPD extension *APPrinterPreset
    (https://www.cups.org/doc/spec-ppd.html) lets a PPD declare named
    presets bundling several of that printer's OWN existing PPD
    option/choice pairs (e.g. Duplex + Resolution) into one entry iOS's
    print sheet shows as a "Preset"/"Vorlage" list -- without it, iOS only
    shows individual Duplex/Resolution controls nested under "Optionen".
    brlaser's own driver-generated PPDs (and the generic sample.drv PPD)
    ship with no such stanzas.

    Each preset in `presets_raw` (see _parse_presets_field for the
    flattened format) is validated independently: an invalid `name`
    (PRESET_NAME_RE) or any invalid options token (PRESET_OPTION_TOKEN_RE)
    skips THAT preset alone (WARNING, never a partial stanza) --
    validation failure on one preset never affects its siblings or the
    printer's own registration. Surviving presets get a de-duplicated slug
    via slugify_preset_id() (fresh `used_slugs` set per call -- PPD
    keyword uniqueness only matters within one printer's own PPD file)
    and are rendered into `*APPrinterPreset <slug>/<name>: "..." *End`
    stanzas per the extension's documented syntax.

    If at least one preset survives, returns a shell fragment that: guards
    on `[ -f "$PPD_FILE" ]` first -- the brlaser branch's own PPD
    registration is itself conditional on a runtime `lpinfo -m` match, so
    the PPD may legitimately not exist yet; copies the LIVE PPD to a TEMP
    file (never edits /etc/cups/ppd/<name>.ppd in place -- avoids a
    same-file read/write race and guarantees every run starts from the
    CURRENT on-disk PPD, so restarts never compound duplicate stanzas);
    appends the stanzas via a `cat >> "$TMP" <<'PPD_PRESETS_EOF' ...
    PPD_PRESETS_EOF` heredoc (quoted delimiter suppresses $/backtick
    expansion -- defense in depth on top of the regex validation above,
    which already excludes those characters by construction); reloads via
    `lpadmin -p <name> -P "$TMP"` wrapped in an if/else (this script runs
    under `set -e`, so a bare failing lpadmin would abort every
    subsequent printer's registration -- the if/else keeps a reload
    failure non-fatal and logged, matching this file's existing fail-open
    posture); removes the temp file; logs one INFO line naming the
    registered slugs, or WARNINGs for skipped presets.

    Returns None -- writing nothing -- when `presets_raw` is empty/absent,
    or when every preset in it failed validation.
    """
    presets_raw = str(presets_raw or "").strip()
    if not presets_raw:
        return None

    quoted_name = shlex.quote(name)
    used_slugs: set[str] = set()
    stanza_blocks: list[str] = []
    registered_slugs: list[str] = []

    for preset_name, preset_options in _parse_presets_field(presets_raw):
        if not PRESET_NAME_RE.match(preset_name):
            print(
                f"WARNING: skipping preset for printer '{name}' -- invalid name "
                f"{preset_name!r}, must match {PRESET_NAME_RE.pattern}",
                flush=True,
            )
            continue

        tokens = preset_options.split()
        if not tokens or not all(PRESET_OPTION_TOKEN_RE.match(t) for t in tokens):
            print(
                f"WARNING: skipping preset {preset_name!r} for printer '{name}' -- "
                f"invalid or empty options {preset_options!r}, every token must match "
                f"{PRESET_OPTION_TOKEN_RE.pattern}",
                flush=True,
            )
            continue

        slug = slugify_preset_id(preset_name, used_slugs)
        option_lines = "\n".join(f"*{key} {value}" for key, value in (t.split("=", 1) for t in tokens))
        stanza_blocks.append(f'*APPrinterPreset {slug}/{preset_name}: "\n{option_lines}\n"\n*End')
        registered_slugs.append(slug)

    if not stanza_blocks:
        print(f"INFO: no valid presets for printer '{name}' -- skipping PPD preset injection", flush=True)
        return None

    stanza_text = "\n".join(stanza_blocks)
    slugs_joined = ", ".join(registered_slugs)
    return (
        f'PPD_FILE="/etc/cups/ppd/{name}.ppd"\n'
        f'if [ -f "$PPD_FILE" ]; then\n'
        f'  TMP_PPD="/tmp/{name}-presets.ppd"\n'
        f'  cp "$PPD_FILE" "$TMP_PPD"\n'
        f"  cat >> \"$TMP_PPD\" <<'PPD_PRESETS_EOF'\n"
        f"{stanza_text}\n"
        f"PPD_PRESETS_EOF\n"
        f'  if lpadmin -p {quoted_name} -P "$TMP_PPD"; then\n'
        f'    echo "registered presets for printer {name}: {slugs_joined}"\n'
        f"  else\n"
        f'    echo "WARNING: lpadmin -P failed while registering presets for printer {name}" >&2\n'
        f"  fi\n"
        f'  rm -f "$TMP_PPD"\n'
        f"else\n"
        f'  echo "WARNING: PPD file $PPD_FILE not found -- skipping preset registration for printer '
        f'{name}" >&2\n'
        f"fi"
    )


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


def build_printer_registration(options: dict) -> str:
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
    """
    printers = options.get("printers") or []
    lines = ["#!/bin/sh", "set -e", ""]

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
            preset_snippet = build_preset_injection_snippet(name, str(entry.get("presets", "") or ""))
            if preset_snippet is not None:
                lines.append(preset_snippet)
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
        preset_snippet = build_preset_injection_snippet(name, str(entry.get("presets", "") or ""))
        if preset_snippet is not None:
            lines.append(preset_snippet)

    lines.append("")
    return "\n".join(lines)


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

    register_script = build_printer_registration(options)
    script_path = Path(REGISTER_SCRIPT_PATH)
    script_path.write_text(register_script)
    script_path.chmod(0o755)
    print(f"Config written to {REGISTER_SCRIPT_PATH}", flush=True)

    admin_script = build_admin_provisioning(options)
    if admin_script is not None:
        admin_script_path = Path(ADMIN_PROVISION_SCRIPT_PATH)
        admin_script_path.write_text(admin_script)
        admin_script_path.chmod(0o755)
        print(f"Config written to {ADMIN_PROVISION_SCRIPT_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
