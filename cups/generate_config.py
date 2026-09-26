#!/usr/bin/env python3
"""Render /etc/avahi/avahi-daemon.conf and /tmp/register-printers.sh from HA add-on options.

Reads /data/options.json and generates:
  - /etc/avahi/avahi-daemon.conf: a minimal avahi-daemon.conf carrying the three
    permanent AirPrint/mDNS fixes (D-07 reflector off, D-10 IPv6 off, D-11 fixed
    host-name) -- everything else is left to Avahi's compiled-in defaults. It
    also carries an auto-detected `allow-interfaces=` restriction (see
    `detect_primary_interface`) that scopes Avahi to the host's real LAN NIC,
    fixing a live hostname-rename loop discovered on haos-op3050-1 after D-11
    shipped.
  - /tmp/register-printers.sh: one `lpadmin` invocation per valid printers[]
    entry, built from a quoted argv list (never an interpolated shell string) so
    a malformed name or uri cannot inject extra shell commands (T-21-01).
"""

import json
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

OPTIONS_PATH = "/data/options.json"
AVAHI_CONF_PATH = "/etc/avahi/avahi-daemon.conf"
REGISTER_SCRIPT_PATH = "/tmp/register-printers.sh"

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

PROC_NET_ROUTE = "/proc/net/route"


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

    register_script = build_printer_registration(options)
    script_path = Path(REGISTER_SCRIPT_PATH)
    script_path.write_text(register_script)
    script_path.chmod(0o755)
    print(f"Config written to {REGISTER_SCRIPT_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
