#!/usr/bin/env bash
# verify-cups-hardening.sh -- fast host-side (no docker, no network) assertions on cups/generate_config.py.
# Phase 21 Plan 05: input validation (WR-04 trailing-newline hole) and generated avahi configuration.
#
# Imports generate_config.py directly and calls its builders with crafted options. Set CUPS_ADDON_DIR to
# point the checks at a modified copy of the add-on directory (used to prove the checks can fail).
#
# Plan 21-08 section: the local-test-container isolation rule (D-11). Exercises internal/cups-test-isolation.sh
# with a stub `docker` (the real docker is never invoked) and statically scans internal/verify-cups-*.sh for
# raw `docker run` calls. Set CUPS_VERIFIER_DIR to scan a modified copy of internal/ (used to prove the scan can
# fail, e.g. against the pre-change paperless verifier).
#
# Usage: bash internal/verify-cups-hardening.sh
# Exit: 0 all checks passed, 1 a check failed, 2 environment error.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CUPS_ADDON_DIR="${CUPS_ADDON_DIR:-${REPO_ROOT}/cups}"
CUPS_VERIFIER_DIR="${CUPS_VERIFIER_DIR:-${SCRIPT_DIR}}"
export CUPS_ADDON_DIR REPO_ROOT CUPS_VERIFIER_DIR

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

print("Section: local test containers cannot claim the live host name (isolation, Plan 21-08)")

ISOLATION_LIB = os.path.join(os.environ["REPO_ROOT"], "internal", "cups-test-isolation.sh")
DOCKER_STUB = """#!/bin/sh
# Stub docker: records its argv (one line per call) and succeeds; the real docker is never reached.
echo "$*" >> "$DOCKER_STUB_LOG"
exit 0
"""


def run_isolation_helper(shell_body: str, data_dir_json):
    """Run shell_body (with $DATA, $LIB set) under a stub docker; return (rc, stdout, stderr, docker_calls).

    data_dir_json: None -> DATA is an empty directory (no options.json); otherwise the raw options.json text.
    """
    with tempfile.TemporaryDirectory() as tmp:
        stub = os.path.join(tmp, "docker")
        log = os.path.join(tmp, "docker-calls.log")
        with open(stub, "w") as handle:
            handle.write(DOCKER_STUB)
        os.chmod(stub, 0o755)
        data = os.path.join(tmp, "data")
        os.mkdir(data)
        if data_dir_json is not None:
            with open(os.path.join(data, "options.json"), "w") as handle:
                handle.write(data_dir_json)
        env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], DOCKER_STUB_LOG=log, DATA=data, LIB=ISOLATION_LIB)
        proc = subprocess.run(
            ["bash", "-c", '. "$LIB"; ' + shell_body], capture_output=True, text=True, env=env, timeout=30
        )
        calls = open(log).read().splitlines() if os.path.exists(log) else []
    return proc.returncode, proc.stdout, proc.stderr, calls


RUN_WITH_MOUNT = 'cups_isolated_run img:test --rm -d --name n -v "$DATA:/data"'
FIXTURES = [
    ("a data dir without options.json", None),
    ("an options.json without avahi_hostname", '{"avahi_reflector": false}'),
    ("an options.json with the default avahi_hostname 'cups'", '{"avahi_hostname": "cups"}'),
    ("an options.json with an empty avahi_hostname", '{"avahi_hostname": ""}'),
]

# Test 1: refusals -- exit 2, docker never called.
for description, options in FIXTURES:
    rc, _, err, calls = run_isolation_helper(RUN_WITH_MOUNT, options)
    report(
        rc == 2 and calls == [] and "refusing to start a cups test container" in err,
        f"cups_isolated_run refuses {description} (exit 2, docker not called)",
    )
rc, _, err, calls = run_isolation_helper("cups_isolated_run img:test --rm -d --name n", '{"avahi_hostname": "cups-vf-x"}')
report(rc == 2 and calls == [], "cups_isolated_run refuses a call without any /data mount (exit 2, docker not called)")
for entry in ('cups_isolated_bash img:test "true" -v "$DATA:/data"', 'cups_lan_run img:test -v "$DATA:/data"'):
    rc, _, _, calls = run_isolation_helper(entry, '{"avahi_hostname": "cups"}')
    report(rc == 2 and calls == [], f"{entry.split()[0]} refuses the default host name 'cups' (exit 2, docker not called)")

# Test 2: acceptance -- the unique name passes; isolation flags appear for the isolated entry points only.
GOOD = '{"avahi_hostname": "cups-vf-x"}'
for entry in (RUN_WITH_MOUNT, 'cups_isolated_bash img:test "true" --rm -v "$DATA:/data"'):
    rc, _, _, calls = run_isolation_helper(entry, GOOD)
    joined = " ".join(calls)
    report(
        rc == 0
        and len(calls) == 1
        and "--cap-add NET_ADMIN" in joined
        and "img:test" in joined
        and "multicast off" in joined,
        f"{entry.split()[0]} accepts a unique name and runs docker with NET_ADMIN and multicast off",
    )
rc, _, _, calls = run_isolation_helper('cups_lan_run img:test --rm -v "$DATA:/data"', GOOD)
joined = " ".join(calls)
report(
    rc == 0 and len(calls) == 1 and "img:test" in joined and "multicast off" not in joined and "NET_ADMIN" not in joined,
    "cups_lan_run accepts a unique name and runs docker WITHOUT the isolation",
)
for label, form in (("--volume SRC:/data", '--volume "$DATA:/data"'), ("--volume=SRC:/data", '--volume="$DATA:/data"')):
    rc, _, _, calls = run_isolation_helper("cups_isolated_run img:test " + form, GOOD)
    report(rc == 0 and len(calls) == 1, f"the /data mount is recognised in the form {label}")
rc, _, _, calls = run_isolation_helper(RUN_WITH_MOUNT, '{"avahi_hostname": "cups-guard\\n"}')
report(rc == 0 and len(calls) == 1, "an invalid-looking name (trailing newline) is let through to the add-on's own refusal")

# Test 3: cups_test_hostname.
rc, out, _, _ = run_isolation_helper("cups_test_hostname paperless-happy", None)
name = out.strip()
report(
    rc == 0 and re.fullmatch(r"cups-vf-paperless-happy-[0-9]+", name) is not None and len(name) <= 63 and name != "cups",
    "cups_test_hostname paperless-happy matches cups-vf-<tag>-<stamp>, at most 63 chars, never 'cups'",
)
for bad_tag in ("a" * 21, "UPPER", "has_underscore", ""):
    rc, out, _, _ = run_isolation_helper(f'cups_test_hostname "{bad_tag}"', None)
    report(rc != 0 and out.strip() == "", f"cups_test_hostname rejects the tag {bad_tag!r}")

# Test 4: static scan -- every docker-using cups verifier goes through the helper.
VERIFIER_DIR = os.environ["CUPS_VERIFIER_DIR"]
RAW_RUN = re.compile(r"\b(?:docker|podman)\s+(?:run|create)\b")
DOCKER_BUILD = re.compile(r"\bdocker\s+build\b")
scanned = []
for entry in sorted(os.listdir(VERIFIER_DIR)):
    if not re.fullmatch(r"verify-cups-[a-z0-9-]+\.sh", entry) or entry == "verify-cups-hardening.sh":
        continue
    with open(os.path.join(VERIFIER_DIR, entry)) as handle:
        code = [line for line in handle.read().splitlines() if not line.lstrip().startswith("#")]
    if not any(DOCKER_BUILD.search(line) for line in code):
        continue
    scanned.append(entry)
    raw = [line.strip() for line in code if RAW_RUN.search(line)]
    sources_helper = any(re.search(r"(?:^|\s)(?:\.|source)\s+\S*cups-test-isolation\.sh", line) for line in code)
    report(not raw, f"internal/{entry} contains no raw docker run / docker create / podman run" + (f" (found: {raw[0]})" if raw else ""))
    report(sources_helper, f"internal/{entry} sources cups-test-isolation.sh")
report(len(scanned) >= 3, f"static scan covers at least the guard, scaffold and paperless verifiers (scanned {len(scanned)})")

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
