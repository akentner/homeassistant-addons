#!/usr/bin/env python3
"""Scenario driver of the ntfy add-on Docker E2E (called by internal/verify-ntfy-e2e.sh).

Talks to the GUI API (port 8099, ingress header, peer 127.0.0.1) and to ntfy (port 8000) through `docker exec curl`
inside the container. Only sentinel passwords are used; neither passwords nor token values are ever printed.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

INGRESS_HEADER = "X-Ingress-Path: /api/hassio_ingress/e2e"
ADMIN_PW = "sentinel-admin-pw"
HA_PW = "sentinel-ha-pw"
AK_PW = "sentinel-ak-pw"
BOB_PW = "sentinel-bob-pw"
CAROL_PW = "sentinel-carol-pw"
CHANGED_ROOT_PW = "sentinel-root-changed-pw"
CHANGED_HA_PW = "sentinel-ha-changed-pw"
CAROL2_PW = "sentinel-carol2-pw"
SENTINELS = [ADMIN_PW, HA_PW, AK_PW, BOB_PW, CAROL_PW, CHANGED_ROOT_PW, CHANGED_HA_PW, CAROL2_PW]

args: argparse.Namespace
failures: list[str] = []
checks = 0
_xff = itertools.count(1)


def check(name: str, condition: bool, detail: str = "") -> bool:
    global checks
    checks += 1
    if condition:
        print(f"  ✓ {name}", flush=True)
    else:
        failures.append(name)
        print(f"  ✗ {name} {detail}".rstrip(), flush=True)
    return condition


def heading(text: str) -> None:
    print(f"\n== {text}", flush=True)


def _curl(argv: list[str], stdin: bytes | None = None) -> tuple[int, bytes]:
    """Run curl inside the container; returns (http status, body)."""
    cmd = ["docker", "exec", "-i", args.container, "curl", "-s", "-w", "\n%{http_code}", *argv]
    proc = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60, check=False)
    out = proc.stdout
    body, _, code = out.rpartition(b"\n")
    try:
        return int(code), body
    except ValueError:
        return 0, out


def gui(method: str, path: str, body: Any = None, ingress: bool = True) -> tuple[int, Any]:
    """Call the GUI API; returns (status, parsed JSON | text | bytes)."""
    argv = ["-X", method, f"http://127.0.0.1:8099{path}"]
    if ingress:
        argv[2:2] = ["-H", INGRESS_HEADER]
    stdin = None
    if body is not None:
        argv[2:2] = ["-H", "Content-Type: application/json", "--data-binary", "@-"]
        stdin = json.dumps(body).encode()
    status, raw = _curl(argv, stdin)
    try:
        return status, json.loads(raw) if raw.strip() else None
    except ValueError:
        try:
            return status, raw.decode()
        except UnicodeDecodeError:
            return status, raw


def ntfy_req(
    method: str,
    path: str,
    user: str | None = None,
    password: str | None = None,
    token: str | None = None,
    data: str | None = None,
) -> tuple[int, str]:
    """Call ntfy on port 8000 with its own X-Forwarded-For (behind-proxy rate limit bucket per request)."""
    n = next(_xff)
    argv = ["-X", method, "-H", f"X-Forwarded-For: 10.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"]
    if user is not None:
        argv += ["-u", f"{user}:{password}"]
    if token is not None:
        argv += ["-H", f"Authorization: Bearer {token}"]
    stdin = None
    if data is not None:
        argv += ["--data-binary", "@-"]
        stdin = data.encode()
    argv.append(f"http://127.0.0.1:8000{path}")
    status, raw = _curl(argv, stdin)
    return status, raw.decode(errors="replace")


def docker_text(*cmd: str) -> str:
    proc = subprocess.run(["docker", *cmd], capture_output=True, timeout=60, check=False)
    return (proc.stdout + proc.stderr).decode(errors="replace")


def exec_text(*cmd: str) -> str:
    return docker_text("exec", args.container, *cmd)


def bootstrap_runs() -> int:
    return docker_text("logs", args.container).count("[bootstrap] done")


def wait_ready(previous_runs: int, timeout: int = 90) -> bool:
    """Wait for ntfy, the GUI and a finished bootstrap run (the bootstrap runs a moment after ntfy starts)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, body = gui("GET", "/api/health")
            if status == 200 and isinstance(body, dict) and body["ntfy"]["healthy"] and bootstrap_runs() > previous_runs:
                return True
        except Exception:  # noqa: BLE001 - container still starting
            pass
        time.sleep(1)
    return False


def restart() -> None:
    runs = bootstrap_runs()
    subprocess.run(["docker", "restart", "-t", "5", args.container], capture_output=True, check=True, timeout=60)
    check("container ready after restart", wait_ready(runs))


def set_options(**changes: Any) -> None:
    path = Path(args.data_dir) / "options.json"
    options = json.loads(path.read_text())
    options.update(changes)
    path.write_text(json.dumps(options))


def users() -> dict[str, dict[str, Any]]:
    status, body = gui("GET", "/api/users")
    return {u["name"]: u for u in body["users"]} if status == 200 else {}


def rules(**query: str) -> list[dict[str, Any]]:
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    status, body = gui("GET", "/api/acl" + (f"?{qs}" if qs else ""))
    return body["rules"] if status == 200 else []


def rule_map(user: str | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    return {(r["user"], r["topic"]): r for r in (rules(user=user) if user else rules())}


def backups(reason: str | None = None) -> list[dict[str, Any]]:
    status, body = gui("GET", "/api/backups")
    items = body["backups"] if status == 200 else []
    return [b for b in items if reason is None or b["reason"] == reason]


def can_write(topic: str, **cred: Any) -> bool:
    return ntfy_req("POST", f"/{topic}", data="probe", **cred)[0] == 200


def can_read(topic: str, **cred: Any) -> bool:
    return ntfy_req("GET", f"/{topic}/json?poll=1&since=all", **cred)[0] == 200


def api_user(name: str, password: str, role: str = "user") -> int:
    return gui("POST", "/api/users", {"name": name, "password": password, "role": role})[0]


def put_rule(user: str, topic: str, permission: str) -> int:
    return gui("PUT", "/api/acl", {"user": user, "topic": topic, "permission": permission})[0]


# --- scenarios ------------------------------------------------------------------------------------------------------


def s01_startup() -> None:
    heading("1. Startup and baseline")
    found = users()
    check("root is admin with origin options", found.get("root", {}).get("role") == "admin" and found["root"]["origin"] == "options")
    for name in ("homeassistant", "akentner"):
        check(f"{name} exists with origin options", found.get(name, {}).get("origin") == "options")
    rm = rule_map()
    check("baseline ACL rules from options", all(rm.get((u, "ha_topic"), {}).get("origin") == "options" for u in ("homeassistant", "akentner")))
    check("baseline permissions rw/ro", rm.get(("homeassistant", "ha_topic"), {}).get("permission") == "rw" and rm.get(("akentner", "ha_topic"), {}).get("permission") == "ro")
    status, icon = gui("GET", "/icon")
    check("GUI icon route serves a PNG", status == 200 and isinstance(icon, bytes) and icon.startswith(b"\x89PNG"), str(status))
    status, health = gui("GET", "/api/health")
    check("health ok with schema 10", status == 200 and health["status"] == "ok" and health["db"]["schema_version"] == 10, str(health)[:200])


def s02_effective() -> None:
    heading("2. Effective-rights parity with real ntfy")
    check("create bob", api_user("bob", BOB_PW) == 201)
    check("create carol", api_user("carol", CAROL_PW) == 201)
    for topic, perm in (("*", "ro"), ("a_b*", "rw"), ("pub1", "deny")):
        check(f"bob {topic} {perm}", put_rule("bob", topic, perm) == 200)
    for topic, perm in (("x", "rw"), ("pub*", "ro")):
        check(f"everyone {topic} {perm}", put_rule("everyone", topic, perm) == 200)
    creds: dict[str, dict[str, Any]] = {
        "root": {"user": "root", "password": ADMIN_PW},
        "bob": {"user": "bob", "password": BOB_PW},
        "carol": {"user": "carol", "password": CAROL_PW},
        "homeassistant": {"user": "homeassistant", "password": HA_PW},
        "akentner": {"user": "akentner", "password": AK_PW},
        "everyone": {},
    }
    topics = ["x", "a_bz", "aXbz", "pub1", "pub9", "PUB9", "ha_topic", "other"]
    pairs = 0
    mismatches: list[str] = []
    for name, cred in creds.items():
        for topic in topics:
            status, eff = gui("GET", f"/api/effective?user={name}&topic={topic}")
            real_w, real_r = can_write(topic, **cred), can_read(topic, **cred)
            pairs += 1
            if status != 200 or eff["read"] != real_r or eff["write"] != real_w:
                mismatches.append(f"{name}/{topic} eval={eff.get('read')},{eff.get('write')} real={real_r},{real_w}")
    check(f"effective-rights matches ntfy for {pairs} compared pairs", not mismatches and pairs == 48, "; ".join(mismatches[:8]))
    print(f"  48 compared pairs: {pairs}", flush=True)
    # equal-length tie-break (write DESC): `a*` ro and `*b` rw both match `ab`
    check("create dave", api_user("dave", "sentinel-dave-pw") == 201)
    put_rule("dave", "a*", "ro")
    put_rule("dave", "*b", "rw")
    put_rule("dave", "c*", "rw")
    put_rule("dave", "*c", "ro")
    dave = {"user": "dave", "password": "sentinel-dave-pw"}
    for topic in ("ab", "cc", "ac", "cb"):
        status, eff = gui("GET", f"/api/effective?user=dave&topic={topic}")
        real = (can_read(topic, **dave), can_write(topic, **dave))
        check(f"tie-break pair dave/{topic} evaluator {(eff['read'], eff['write'])} == real {real}", (eff["read"], eff["write"]) == real)
    gui("DELETE", "/api/users/dave", {"confirm": "dave"})


def s03_tokens() -> None:
    heading("3. Tokens")
    status, body = gui("POST", "/api/tokens", {"user": "bob", "label": "ci", "expires": "1h"})
    check("token created (201) with origin gui", status == 201 and body["token"]["origin"] == "gui" and body["token"]["label"] == "ci")
    value = body["token"]["value"] if status == 201 else ""
    tid = body["token"]["id"] if status == 201 else ""
    check("publish with the bearer token works", ntfy_req("POST", "/a_bz", token=value, data="tok")[0] == 200)
    status, listing = gui("GET", "/api/tokens?user=bob")
    check("list carries no token value", status == 200 and value not in json.dumps(listing) and all("value" not in t for t in listing["tokens"]))
    status, rev = gui("POST", "/api/tokens/reveal", {"user": "bob", "id": tid})
    check("reveal returns the same value", status == 200 and rev["value"] == value)
    check("revoke answers 204", gui("DELETE", f"/api/tokens?user=bob&id={tid}")[0] == 204)
    check("revoked token fails", ntfy_req("POST", "/a_bz", token=value, data="tok")[0] in (401, 403))


def s04_role_change() -> None:
    heading("4. Role change stash and restore")
    before = {(k[1], v["permission"]) for k, v in rule_map("bob").items()}
    status, body = gui("PATCH", "/api/users/bob", {"role": "admin"})
    check("promote to admin drops 3 rules", status == 200 and body["dropped_rules"] == 3, str(body)[:200])
    check("role-change backup exists", len(backups("role-change")) >= 1)
    check("bob (admin) publishes anywhere", can_write("other", user="bob", password=BOB_PW))
    check("acl for bob is empty while admin", rules(user="bob") == [])
    status, body = gui("PATCH", "/api/users/bob", {"role": "user"})
    after = {(k[1], v["permission"]) for k, v in rule_map("bob").items()}
    check("demotion restores exactly the three rules", status == 200 and after == before and len(after) == 3, f"{before} vs {after}")


def s05_guardrails() -> None:
    global root_pw
    heading("5. Guardrails")
    status, body = gui("DELETE", "/api/users/root", {"confirm": "root"})
    check("deleting root gives 409 protected", status == 409 and body["error"] == "protected", f"{status} {body}")
    status, body = gui("PATCH", "/api/users/root", {"role": "user"})
    check("demoting root gives 409", status == 409, f"{status} {body}")
    check("changing root's password gives 200", gui("PATCH", "/api/users/root", {"password": CHANGED_ROOT_PW})[0] == 200)
    check("new root password authenticates", can_write("ha_topic", user="root", password=CHANGED_ROOT_PW))
    check("old root password no longer works", not can_write("ha_topic", user="root", password=ADMIN_PW))
    root_pw = CHANGED_ROOT_PW
    check("delete bob with a wrong confirm gives 400", gui("DELETE", "/api/users/bob", {"confirm": "nope"})[0] == 400)
    check("delete bob with the right confirm gives 204", gui("DELETE", "/api/users/bob", {"confirm": "bob"})[0] == 204)
    check("user-delete backup exists", len(backups("user-delete")) >= 1)
    status, _ = gui("DELETE", "/api/users/everyone", {"confirm": "everyone"})
    check("everyone cannot be deleted", status in (400, 404, 409), str(status))


def s06_export() -> None:
    heading("6. Export")
    status, doc = gui("GET", "/api/export")
    text = json.dumps(doc)
    names = {u["name"] for u in doc["users"]} if status == 200 else set()
    check("JSON export schema 1 with the expected users", status == 200 and doc["schema"] == 1 and {"root", "homeassistant", "akentner", "carol"} <= names, str(names))
    check("default export has no hashes or tokens", "$2" not in text and "tk_" not in text)
    status, hashed = gui("GET", "/api/export?include_hashes=1")
    check("include_hashes adds one $2 hash per user", status == 200 and all(u.get("password_hash", "").startswith("$2") for u in hashed["users"]))
    status, yaml_text = gui("GET", "/api/export?format=yaml")
    try:
        import yaml

        parsed = yaml.safe_load(yaml_text)
        a = {k: v for k, v in parsed.items() if k != "generated_at"}
        b = {k: v for k, v in doc.items() if k != "generated_at"}
        check("YAML export equals the JSON document", status == 200 and a == b)
    except ImportError:
        check("YAML export answers 200 (PyYAML missing on host)", status == 200 and isinstance(yaml_text, str))


def s07_backups() -> None:
    heading("7. Backups")
    status, body = gui("POST", "/api/backups", {})
    check("backup created (201)", status == 201)
    name = body["backup"]["name"] if status == 201 else ""
    status, blob = gui("GET", f"/api/backups/{name}")
    check("download is an SQLite file", status == 200 and (blob.startswith(b"SQLite format 3") if isinstance(blob, bytes) else str(blob).startswith("SQLite format 3")))
    for _ in range(6):
        gui("POST", "/api/backups", {})
        time.sleep(1.05)  # names carry second resolution
    check("rotation keeps exactly backup_keep (4)", len(backups()) == 4, str(len(backups())))


def s08_cache() -> None:
    heading("8. Cache")
    check("publish as root", can_write("ha_topic", user="root", password=root_pw))
    check("poll sees the message", '"event":"message"' in ntfy_req("GET", "/ha_topic/json?poll=1&since=all", user="root", password=root_pw)[1])
    status, body = gui("POST", "/api/reset/cache", {"confirm": "wrong"})
    check("wrong phrase gives 400", status == 400)
    check("message stays", '"event":"message"' in ntfy_req("GET", "/ha_topic/json?poll=1&since=all", user="root", password=root_pw)[1])
    status, body = gui("POST", "/api/reset/cache", {"confirm": "clear cache"})
    check("clear cache succeeds and deletes messages", status == 200 and body["messages_deleted"] >= 1, f"{status} {body}")
    check("poll is empty afterwards", '"event":"message"' not in ntfy_req("GET", "/ha_topic/json?poll=1&since=all", user="root", password=root_pw)[1])
    check("a new publish works while ntfy runs", can_write("ha_topic", user="root", password=root_pw))


def s09_reset_acls() -> None:
    heading("9. Reset ACLs")
    check("wrong phrase gives 400", gui("POST", "/api/reset/acls", {"confirm": "x"})[0] == 400)
    status, _ = gui("POST", "/api/reset/acls", {"confirm": "reset acls"})
    check("reset acls succeeds", status == 200)
    check("api/acl is empty", rules() == [])
    check("users stay", {"root", "homeassistant", "akentner", "carol"} <= set(users()))
    check("reset-acls backup exists", len(backups("reset-acls")) >= 1)


def s10_test_publish() -> None:
    heading("10. Test publish")
    status, body = gui("POST", "/api/health/publish", {"topic": "ha_topic"})
    check("test publish ok with status 200", status == 200 and body["ok"] is True and body["status"] == 200, str(body))
    status, listing = gui("GET", "/api/tokens?user=root")
    check("no gui-test token left", status == 200 and all(t["label"] != "gui-test" for t in listing["tokens"]))


def s11_reset_everything() -> None:
    heading("11. Reset everything")
    check("wrong phrase gives 400", gui("POST", "/api/reset/everything", {"confirm": "x"})[0] == 400)
    status, body = gui("POST", "/api/reset/everything", {"confirm": "reset everything"})
    check("reset everything succeeds", status == 200, f"{status} {body}")
    found = users()
    check("carol is gone", "carol" not in found)
    check("root, homeassistant and akentner are back with origin options", all(found.get(n, {}).get("origin") == "options" for n in ("root", "homeassistant", "akentner")), str({k: v["origin"] for k, v in found.items()}))
    rm = rule_map()
    check("two baseline rules are back with origin options", {k for k in rm} == {("homeassistant", "ha_topic"), ("akentner", "ha_topic")} and all(r["origin"] == "options" for r in rm.values()), str(rm.keys()))
    global root_pw
    check("root authenticates with the OPTIONS password", can_write("ha_topic", user="root", password=ADMIN_PW))
    check("the GUI-changed root password no longer works", not can_write("ha_topic", user="root", password=CHANGED_ROOT_PW))
    check("baseline user authenticates with the options password", can_write("ha_topic", user="homeassistant", password=HA_PW))
    check("reset-everything backup exists", len(backups("reset-everything")) >= 1)
    root_pw = ADMIN_PW


def s12_restart_ownership() -> None:
    heading("12. Restart and ownership")
    check("change homeassistant's password in the GUI", gui("PATCH", "/api/users/homeassistant", {"password": CHANGED_HA_PW})[0] == 200)
    check("edit homeassistant's ha_topic rule to ro in the GUI", put_rule("homeassistant", "ha_topic", "ro") == 200)
    count_before = len(users())
    restart()
    check("user count unchanged", len(users()) == count_before)
    check("GUI-changed password still works", can_read("ha_topic", user="homeassistant", password=CHANGED_HA_PW))
    check("options password does not work", not can_read("ha_topic", user="homeassistant", password=HA_PW))
    rule = rule_map().get(("homeassistant", "ha_topic"), {})
    check("rule is still ro with origin gui", rule.get("permission") == "ro" and rule.get("origin") == "gui", str(rule))
    check("exactly one daily backup after the first restart", len(backups("daily")) == 1, str(len(backups("daily"))))
    restart()
    check("still one daily backup after the second restart", len(backups("daily")) == 1, str(len(backups("daily"))))
    # options-owned rule re-syncs
    check("akentner rule is ro (options) before the change", rule_map().get(("akentner", "ha_topic"), {}).get("permission") == "ro")
    options = json.loads((Path(args.data_dir) / "options.json").read_text())
    baseline = [dict(u, write_access=True) if u["username"] == "akentner" else u for u in options["baseline_users"]]
    set_options(baseline_users=baseline)
    restart()
    rule = rule_map().get(("akentner", "ha_topic"), {})
    check("akentner rule becomes rw after the options change", rule.get("permission") == "rw" and rule.get("origin") == "options", str(rule))
    set_options(baseline_users=[u for u in baseline if u["username"] != "akentner"])
    restart()
    found = users()
    rule = rule_map().get(("akentner", "ha_topic"), {})
    check("removed baseline entry: user and rule remain", "akentner" in found and rule.get("permission") == "rw")
    check("removed baseline entry: origin becomes gui", found["akentner"]["origin"] == "gui" and rule.get("origin") == "gui", f"{found['akentner']['origin']} {rule.get('origin')}")


def s12b_password_switch() -> None:
    heading("12b. baseline_overwrite_passwords (D-18)")
    check("create carol2 in the GUI", api_user("carol2", CAROL2_PW) == 201)
    rule_before = rule_map().get(("homeassistant", "ha_topic"), {})
    origin_before = users()["homeassistant"]["origin"]
    set_options(baseline_overwrite_passwords=True)
    restart()
    check("homeassistant authenticates with the OPTIONS password again", can_read("ha_topic", user="homeassistant", password=HA_PW))
    check("the GUI-changed password fails", not can_read("ha_topic", user="homeassistant", password=CHANGED_HA_PW))
    check("origin and rule of homeassistant unchanged", users()["homeassistant"]["origin"] == origin_before and rule_map().get(("homeassistant", "ha_topic")) == rule_before)
    # right password without rights is 403, a wrong password is 401
    check("GUI-created carol2 keeps its password", ntfy_req("GET", "/carol2/json?poll=1", user="carol2", password=CAROL2_PW)[0] == 403)
    logs = docker_text("logs", args.container)
    cmdline = exec_text("cat", "/proc/1/cmdline")
    check("no password sentinel in logs or PID 1 cmdline", not any(s in logs or s in cmdline for s in SENTINELS))
    set_options(baseline_overwrite_passwords=False)


def s13_option_variants() -> None:
    heading("13. Option variants")
    set_options(enable_web_ui=False)
    restart()
    check("web UI disabled: / is 404", ntfy_req("GET", "/")[0] == 404)
    check("web UI disabled: /app is 404", ntfy_req("GET", "/app")[0] == 404)
    set_options(enable_web_ui=True)
    restart()
    check("web UI enabled: / is 200", ntfy_req("GET", "/")[0] == 200)
    check("web UI enabled: /app is 200", ntfy_req("GET", "/app")[0] == 200)
    set_options(auth_default_access="read-only")
    restart()
    check("read-only default: anonymous read of an unknown topic is 200", can_read("unknowntopic"))
    check("read-only default: anonymous write is 403", ntfy_req("POST", "/unknowntopic", data="x")[0] == 403)
    status, eff = gui("GET", "/api/effective?user=everyone&topic=unknowntopic")
    check("effective for everyone agrees", status == 200 and eff["read"] is True and eff["write"] is False and eff["source"]["kind"] == "default", str(eff)[:200])
    set_options(auth_default_access="deny-all")
    restart()


def s14_gate() -> None:
    heading("14. Ingress gate")
    for method, path in (("GET", "/api/health"), ("GET", "/api/users"), ("GET", "/static/app.mjs"), ("GET", "/"), ("GET", "/nope"), ("POST", "/api/users")):
        status, body = gui(method, path, ingress=False)
        check(f"{method} {path} without header is 403 ingress_only", status == 403 and isinstance(body, dict) and body.get("error") == "ingress_only", f"{status} {str(body)[:80]}")


def s15_concurrency() -> None:
    heading("15. Concurrency")
    with ThreadPoolExecutor(max_workers=10) as pool:
        acl = list(pool.map(lambda i: gui("PUT", "/api/acl", {"user": "homeassistant", "topic": f"par{i}", "permission": "rw"}), range(10)))
        tok = list(pool.map(lambda i: gui("POST", "/api/tokens", {"user": "homeassistant", "label": f"par{i}"}), range(10)))
    check("10 parallel PUT api/acl succeed", all(s == 200 for s, _ in acl), str([s for s, _ in acl]))
    check("10 parallel token creations succeed", all(s == 201 for s, _ in tok), str([s for s, _ in tok]))
    check("no lock error reported", not any("lock" in json.dumps(b).lower() for _, b in acl + tok))


def s16_leaks() -> None:
    heading("16. Leak scan")
    surfaces: dict[str, str] = {
        "docker logs": docker_text("logs", args.container),
        "server.yml": exec_text("cat", "/data/server.yml"),
        "origins.json": exec_text("cat", "/data/origins.json"),
        "api/users": json.dumps(gui("GET", "/api/users")[1]),
        "api/acl": json.dumps(gui("GET", "/api/acl")[1]),
        "api/tokens": json.dumps(gui("GET", "/api/tokens")[1]),
        "default export": json.dumps(gui("GET", "/api/export")[1]),
    }
    for name, text in surfaces.items():
        check(f"no sentinel password in {name}", not any(s in text for s in SENTINELS) and len(text) > 2)


def main() -> int:
    global args, root_pw
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    root_pw = ADMIN_PW
    scenarios: list[Callable[[], None]] = [
        s01_startup, s02_effective, s03_tokens, s04_role_change, s05_guardrails, s06_export, s07_backups,
        s08_cache, s09_reset_acls, s10_test_publish, s11_reset_everything, s12_restart_ownership,
        s12b_password_switch, s13_option_variants, s14_gate, s15_concurrency, s16_leaks,
    ]
    for scenario in scenarios:
        try:
            scenario()
        except Exception as exc:  # noqa: BLE001 - collect, do not abort the remaining scenarios
            check(f"{scenario.__name__} ran without exception", False, f"{type(exc).__name__}: {exc}")
    print(f"\n{checks} checks, {len(failures)} failed", flush=True)
    if failures:
        print("FAILED: " + "; ".join(failures), flush=True)
        return 1
    print("All ntfy e2e checks passed", flush=True)
    return 0


root_pw = ADMIN_PW

if __name__ == "__main__":
    sys.exit(main())
