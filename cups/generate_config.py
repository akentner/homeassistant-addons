#!/usr/bin/env python3
"""Render /etc/avahi/avahi-daemon.conf, /etc/cups/cupsd.conf, and
/tmp/register-printers.sh from HA add-on options.

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
    but never actually connect to port 631 to print. `/admin`, `/admin/conf`,
    `/admin/log`, and every Policy block are left byte-for-byte untouched --
    only network reachability changes, not the admin-auth boundary. Also
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
    a malformed name or uri cannot inject extra shell commands (T-21-01).
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
    Also inserts a `ServerAlias` directive (from the `server_aliases` add-on
    option, default `"*"`) directly after the patched `Listen` line -- see
    `parse_server_aliases` for why this is needed (cupsd's Host-header
    validation, a separate concern from the `Listen`/`Allow` network-
    reachability fix above) and why `"*"` is a safe out-of-the-box default
    (the real access boundary is already the detected LAN subnet's `Allow
    from`, not the Host header check).

    If a `tailscale0` interface is present on the host, a SECOND `Allow from
    100.64.0.0/10` line is added to the same `<Location />` block (CUPS's
    `Order allow,deny` evaluates multiple `Allow from` lines independently --
    standard syntax, not an error) -- see `detect_tailscale_subnet` for why
    Tailscale-routed clients need this in addition to the LAN subnet's
    `Allow from` line. If no `tailscale0` interface is found, this is skipped
    with a log note, not a hard failure -- not every deployment runs
    Tailscale.

    `/admin`, `/admin/conf`, `/admin/log`, and every `<Policy>` block are
    never touched by this function -- only the lines above are patched,
    everything else in the stock file survives byte-for-byte.

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

    location_match = LOCATION_ROOT_RE.search(patched)
    if location_match is None:
        print(
            "WARNING: stock cupsd.conf does not contain the expected top-level '<Location />' "
            "block -- Listen was patched but access control was not; cupsd is reachable on the "
            "LAN with NO subnet restriction until this is fixed",
            flush=True,
        )
        return patched

    tailscale_subnet = detect_tailscale_subnet()
    if tailscale_subnet:
        print(
            f"INFO: tailscale0 interface detected -- also allowing {tailscale_subnet} in the "
            "top-level <Location /> block",
            flush=True,
        )
    else:
        print(
            "INFO: no tailscale0 interface detected -- skipping the Tailscale Allow rule "
            "(not every deployment runs Tailscale)",
            flush=True,
        )

    body = location_match.group(2)
    allow_lines = f"{body}\n  Allow from {subnet}"
    if tailscale_subnet:
        allow_lines += f"\n  Allow from {tailscale_subnet}"
    patched = (
        patched[: location_match.start(2)] + allow_lines + patched[location_match.end(2) :]
    )
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


def build_printer_registration(options: dict) -> str:
    """Render /tmp/register-printers.sh: one validated, quoted lpadmin call per entry.

    Invalid entries (bad name, unsupported uri scheme) are skipped and logged
    rather than crashing lpadmin or the whole add-on. `enabled` defaults to
    true when absent (D-04's discretion default).
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

        # argv-array construction, never an interpolated shell string (T-21-01
        # mitigation). `-m everywhere` was tried first (CUPS's driverless
        # IPP-Everywhere model) but proved unavailable during the Task 2
        # smoke test: it performs a live IPP capability query against the
        # device AT REGISTRATION TIME, so any printer that happens to be
        # powered off/unreachable when the add-on (re)starts fails to
        # register at all -- defeating the point of a persistent print
        # queue. `-m drv:///sample.drv/generic.ppd` (a static generic
        # PostScript driver, CUPS's documented fallback model) registers the
        # queue unconditionally; CUPS only contacts the device when a job is
        # actually printed.
        argv = ["lpadmin", "-p", name, "-v", uri, "-E", "-m", "drv:///sample.drv/generic.ppd"]
        lines.append(" ".join(shlex.quote(a) for a in argv))
        lines.append(f'echo "registered printer: {name}"')

    lines.append("")
    return "\n".join(lines)


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


if __name__ == "__main__":
    sys.exit(main())
