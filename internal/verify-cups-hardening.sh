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
export CUPS_ADDON_DIR REPO_ROOT

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
import re
import subprocess
import sys
import tempfile

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
lpadmin_lines = [line for line in script.splitlines() if line.startswith("if lpadmin ")]
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

print("Section: failure-tolerant registration and queue-name charset (WR-09, WR-05)")

long127 = "A" * 127
long128 = "A" * 128

# Test 1: queue-name charset accepts underscores and 127 chars; rejects space, slash, 128 chars.
options = {
    "printers": [
        {"name": "Brother_MFC_7460DN", "uri": uri},
        {"name": "has space", "uri": uri},
        {"name": "has/slash", "uri": uri},
        {"name": long127, "uri": uri},
        {"name": long128, "uri": uri},
    ]
}
result, exit_code, output = call_quietly(gc.build_printer_registration, options)
script, names = result if result else ("", [])
report(
    exit_code is None and names == ["Brother_MFC_7460DN", long127],
    "queue names: Brother_MFC_7460DN and a 127-char name register; space, slash and 128-char names are skipped",
)
report(output.count("WARNING") == 3, "queue names: exactly three WARNING lines for the three invalid names")


def run_registration(script_text: str, failing_name):
    """Run the generated script with sh and a stub lpadmin; return (rc, stdout, stderr, argv_log_lines)."""
    with tempfile.TemporaryDirectory() as tmp:
        stub = os.path.join(tmp, "lpadmin")
        log = os.path.join(tmp, "calls.log")
        with open(stub, "w") as handle:
            handle.write("#!/bin/sh\n")
            handle.write('echo "$*" >> "%s"\n' % log)
            if failing_name:
                handle.write('case "$*" in *"-p %s "*) exit 1;; esac\n' % failing_name)
            handle.write("exit 0\n")
        os.chmod(stub, 0o755)
        script_path = os.path.join(tmp, "register.sh")
        with open(script_path, "w") as handle:
            handle.write(script_text)
        env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"])
        proc = subprocess.run(["sh", script_path], capture_output=True, text=True, env=env, timeout=30)
        calls = open(log).read().splitlines() if os.path.exists(log) else []
    return proc.returncode, proc.stdout, proc.stderr, calls


three = {"printers": [{"name": n, "uri": uri} for n in ("first_printer", "second_printer", "third_printer")]}
result, _, _ = call_quietly(gc.build_printer_registration, three)
script3, names3 = result

# Test 2: no set -e; a failing middle entry does not stop the third; exit status is non-zero.
report(not re.search(r"^set -e", script3, re.MULTILINE), "registration script does not start with set -e")
rc, out, err, calls = run_registration(script3, "second_printer")
report(
    len(calls) == 3 and "-p third_printer " in calls[-1],
    "failing entry: lpadmin is still called for the entry AFTER it",
)
report(
    out.count("registered printer:") == 2
    and "registered printer: first_printer" in out
    and "registered printer: third_printer" in out
    and "registered printer: second_printer" not in out,
    "failing entry: 'registered printer:' printed only for the two successful entries",
)
report("WARNING: registration of second_printer failed" in err, "failing entry: WARNING names the failing printer")
report(rc != 0, "failing entry: script exits non-zero")

# Test 3: a stub that never fails gives exit 0.
rc, out, err, calls = run_registration(script3, None)
report(
    rc == 0 and len(calls) == 3 and out.count("registered printer:") == 3,
    "no failures: script exits 0 after three registrations",
)

# Test 4: paperless_upload.queue_name charset (underscores accepted, trailing newline rejected).
pdf_ok = {"paperless_upload": {"enabled": True, "queue_name": "PDF_to_DMS"}}
pdf_nl = {"paperless_upload": {"enabled": True, "queue_name": "PDF_to_DMS\n"}}
result, _, _ = call_quietly(gc.build_cups_pdf_registration_snippet, pdf_ok)
cups_snippet, queue = result
report(cups_snippet is not None and queue == "PDF_to_DMS", "cups-pdf snippet is generated for queue_name 'PDF_to_DMS'")
result, _, _ = call_quietly(gc.build_cups_pdf_registration_snippet, pdf_nl)
report(result == (None, None), "cups-pdf snippet is NOT generated for queue_name with a trailing newline")
conf, _, _ = call_quietly(gc.build_cups_pdf_conf, pdf_ok)
report(conf is not None, "cups-pdf.conf is generated for queue_name 'PDF_to_DMS'")
conf, _, _ = call_quietly(gc.build_cups_pdf_conf, pdf_nl)
report(conf is None, "cups-pdf.conf is NOT generated for queue_name with a trailing newline")

# The cups-pdf queue sits before the final exit, so it is attempted even when a printer entry failed.
if cups_snippet is not None:
    result, _, _ = call_quietly(gc.build_printer_registration, three, [cups_snippet])
    script_with_pdf = result[0]
    report(
        script_with_pdf.rstrip().endswith(gc.REGISTER_SCRIPT_TRAILER)
        and script_with_pdf.index("PDF_to_DMS") < script_with_pdf.rindex("exit "),
        "cups-pdf snippet is placed before the final exit of the registration script",
    )

print("Section: migration helper output safety (IN-06, WR-05)")

HELPER = os.path.join(os.environ["REPO_ROOT"], "internal", "cups-migration-suggestion.sh")

# Canned `lpstat -v` data: a socket uri, an ipp uri containing a double quote, and a dotted (invalid) name.
LPSTAT_LINES = (
    "device for Brother_MFC_7460DN: socket://192.0.2.20:9100\n"
    'device for HP_LaserJet: ipp://192.0.2.21/ipp/print?x="y"\n'
    "device for bad.name: ipp://192.0.2.22/ipp/print\n"
)
SSH_STUB = """#!/bin/sh
# Stub ssh: ignores the host argument and answers by the remote command words (read-only canned data).
case "$*" in
  *"ha apps info"*) exit 0 ;;
  *"docker ps"*) printf 'app_f1c878cb_cups\\napp_f1c878cb_cups_extra\\n'; exit 0 ;;
  *"app_f1c878cb_cups lpstat -v"*) printf '%s' "$CANNED_LPSTAT"; exit 0 ;;
esac
exit 1
"""


def run_helper():
    with tempfile.TemporaryDirectory() as tmp:
        stub = os.path.join(tmp, "ssh")
        with open(stub, "w") as handle:
            handle.write(SSH_STUB)
        os.chmod(stub, 0o755)
        env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], CANNED_LPSTAT=LPSTAT_LINES)
        return subprocess.run(["bash", HELPER], capture_output=True, text=True, env=env, timeout=60)


proc = run_helper()
out = proc.stdout

# Test 2: two matching containers -- the first one is used, the exit status is 0.
report(proc.returncode == 0, "two matching containers: helper exits 0")
report(
    "Brother_MFC_7460DN" in out and "HP_LaserJet" in out,
    "two matching containers: printers of the FIRST container are emitted",
)

# Test 1: output content and YAML validity.
report(
    "bad.name" in out and out.index("WARNING") < out.index("bad.name") and out.count("WARNING") == 1,
    "helper keeps 'bad.name' and puts exactly one WARNING comment before it",
)
report('ipp://192.0.2.21/ipp/print?x=\\"y\\"' in out, "helper escapes the double quote inside the uri")
last_comment = [line for line in out.splitlines() if line.startswith("#")]
report(
    any("driver" in line and "driver_model" in line for line in last_comment),
    "helper ends with a comment mentioning driver and driver_model for socket:// printers",
)
try:
    import yaml
except ImportError:
    print("   SKIP: PyYAML not importable, YAML parse check skipped")
else:
    parsed = yaml.safe_load(out)
    entries = (parsed or {}).get("printers") or []
    report(
        [entry["name"] for entry in entries] == ["Brother_MFC_7460DN", "HP_LaserJet", "bad.name"]
        and entries[1]["uri"] == 'ipp://192.0.2.21/ipp/print?x="y"',
        "helper output parses as YAML with three entries and the quote preserved",
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
