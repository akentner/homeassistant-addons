#!/usr/bin/env python3
"""Render /etc/avahi/avahi-daemon.conf and /tmp/register-printers.sh from HA add-on options.

Reads /data/options.json and generates:
  - /etc/avahi/avahi-daemon.conf: a minimal avahi-daemon.conf carrying the three
    permanent AirPrint/mDNS fixes (D-07 reflector off, D-10 IPv6 off, D-11 fixed
    host-name) -- everything else is left to Avahi's compiled-in defaults.
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
