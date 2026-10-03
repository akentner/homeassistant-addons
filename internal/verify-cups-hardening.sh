#!/usr/bin/env bash
# verify-cups-hardening.sh -- fast host-side (no docker, no network) assertions on cups/generate_config.py.
# Phase 21 Plan 05: input validation (WR-04 trailing-newline hole) and generated avahi configuration.
#
# Imports generate_config.py directly and calls its builders with crafted options. Set CUPS_ADDON_DIR to
# point the checks at a modified copy of the add-on directory (used to prove the checks can fail).
#
# Usage: bash internal/verify-cups-hardening.sh
# Exit: 0 all checks passed, 1 a check failed, 2 environment error.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CUPS_ADDON_DIR="${CUPS_ADDON_DIR:-${REPO_ROOT}/cups}"
export CUPS_ADDON_DIR

if [[ ! -f "${CUPS_ADDON_DIR}/generate_config.py" ]]; then
    printf 'generate_config.py not found in %s\n' "${CUPS_ADDON_DIR}" >&2
    exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
    printf 'python3 not found in PATH\n' >&2
    exit 2
fi

python3 - <<'PYTHON'
import contextlib
import io
import os
import sys

sys.path.insert(0, os.environ["CUPS_ADDON_DIR"])
import generate_config as gc  # noqa: E402

failures = 0


def report(ok: bool, description: str) -> None:
    global failures
    if ok:
        print(f"\033[0;32m   PASS: {description}\033[0m")
    else:
        failures += 1
        print(f"\033[0;31m   FAIL: {description}\033[0m")


def call_quietly(func, *args):
    """Return (result, exit_code, stdout); exit_code is None unless the call raised SystemExit."""
    buffer = io.StringIO()
    result = None
    exit_code = None
    with contextlib.redirect_stdout(buffer):
        try:
            result = func(*args)
        except SystemExit as exc:
            exit_code = exc.code if exc.code is not None else 0
    return result, exit_code, buffer.getvalue()


def refuses(func, options) -> bool:
    """True when the builder exits with a non-zero status for these options."""
    _, exit_code, _ = call_quietly(func, options)
    return exit_code not in (None, 0)


print("Section: trailing-newline validation (WR-04)")

# Test 1: build_avahi_conf rejects a trailing-newline hostname and accepts a plain one.
report(
    refuses(gc.build_avahi_conf, {"avahi_hostname": "cups\n"}),
    "build_avahi_conf exits non-zero for avahi_hostname 'cups\\n'",
)
conf, exit_code, _ = call_quietly(gc.build_avahi_conf, {"avahi_hostname": "cups"})
report(exit_code is None and "host-name=cups" in (conf or ""), "build_avahi_conf accepts 'cups' (host-name=cups)")

# Test 2: the guard env obeys the same validation.
report(
    refuses(gc.build_avahi_guard_env, {"avahi_hostname": "cups\n"}),
    "build_avahi_guard_env exits non-zero for avahi_hostname 'cups\\n'",
)
env_text, exit_code, _ = call_quietly(gc.build_avahi_guard_env, {"avahi_hostname": "cups"})
report(
    exit_code is None and "AVAHI_EXPECTED_FQDN=cups.local" in (env_text or ""),
    "build_avahi_guard_env for 'cups' contains AVAHI_EXPECTED_FQDN=cups.local",
)

# Test 3: build_printer_registration skips a trailing-newline printer name and registers the plain one.
uri = "ipp://192.0.2.10:631/ipp/print"
options = {"printers": [{"name": "testprinter\n", "uri": uri}, {"name": "testprinter", "uri": uri}]}
result, exit_code, output = call_quietly(gc.build_printer_registration, options)
script, names = result if result else ("", [])
lpadmin_lines = [line for line in script.splitlines() if line.startswith("lpadmin ")]
report(
    exit_code is None and names == ["testprinter"] and len(lpadmin_lines) == 1,
    "build_printer_registration registers only 'testprinter' (one lpadmin line)",
)
report("WARNING" in output, "build_printer_registration prints a WARNING for 'testprinter\\n'")

print("Section: avahi_use_ipv6 / publish-aaaa-on-ipv4 (D-10)")

# Test 1: default (IPv6 off) carries use-ipv6=no, a [publish] section and publish-aaaa-on-ipv4=no,
# ordered [server] ... [publish] ... [reflector].
conf, exit_code, _ = call_quietly(gc.build_avahi_conf, {})
conf = conf or ""
ordered = (
    "use-ipv6=no" in conf
    and "[publish]" in conf
    and "publish-aaaa-on-ipv4=no" in conf
    and conf.index("use-ipv6=no") < conf.index("[publish]") < conf.index("publish-aaaa-on-ipv4=no")
    and conf.index("publish-aaaa-on-ipv4=no") < conf.index("[reflector]")
)
report(
    exit_code is None and ordered,
    "avahi_use_ipv6 false: use-ipv6=no, then [publish] publish-aaaa-on-ipv4=no, then [reflector]",
)

# Test 2: IPv6 on keeps use-ipv6=yes and emits no publish-aaaa-on-ipv4 line at all.
conf, exit_code, _ = call_quietly(gc.build_avahi_conf, {"avahi_use_ipv6": True})
conf = conf or ""
report(
    exit_code is None and "use-ipv6=yes" in conf and "publish-aaaa-on-ipv4" not in conf,
    "avahi_use_ipv6 true: use-ipv6=yes and no publish-aaaa-on-ipv4 line",
)

# <<hardening sections appended by later plans go above this line>>

sys.exit(1 if failures else 0)
PYTHON
status=$?

if [[ "${status}" == "0" ]]; then
    printf '\033[0;32mRESULT: PASS\033[0m\n'
else
    printf '\033[0;31mRESULT: FAIL\033[0m\n'
fi
exit "${status}"
