#!/bin/bash
# Staged verification for quick task 261102-swd (haos-monitor GUI on the admin-ui blueprint stack, two ports).
# Usage: 261102-swd-verify.sh [static] [server] [frontend] [ci] [docker]   (no argument = all stages)
# Every comparison uses one fixed base (BASE, default 40fab86), never the moving origin/main.
# Never contains the literal PEM private-key marker: it is assembled from fragments, test keys are generated at
# runtime (ssh-keygen) and the damaged key is derived with head/tail.
set -u

ROOT=$(git rev-parse --show-toplevel) || exit 2
ADDON="$ROOT/haos-monitor"
BASE=${BASE:-40fab86}
TMP=$(mktemp -d) || exit 2
PID=$$
IMG_NEW="haos-monitor-swd-new-$PID"
IMG_OLD="haos-monitor-swd-old-$PID"
C_NEW="haos-monitor-swd-new-$PID"
C_OLD="haos-monitor-swd-old-$PID"
FAILS=0
RAN=()
SECRET_COMMENT='secret-comment@example'
INGRESS_HEADER='X-Ingress-Path: /api/hassio_ingress/verify'
# assembled from fragments, so this file never contains the marker as one string
PEM_RE='-----BEGIN [A-Z ]*PRIVATE'' KEY-----'
HADOLINT_IGNORES=(--ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016)
LEGACY_FILES=(status.sh status.cgi metrics.cgi hosts.cgi incidents.cgi httpd.conf monitor.sh mqtt.sh)

cleanup() {
  docker rm -f "$C_NEW" "$C_OLD" >/dev/null 2>&1
  docker rmi "$IMG_NEW" "$IMG_OLD" >/dev/null 2>&1
  rm -rf -- "${TMP:?}"
}
trap cleanup EXIT

ok() { echo "ok $1"; }
fail() { echo "FAIL $1"; FAILS=$((FAILS + 1)); }
check() { # $1 = label, rest = condition command
  local label=$1
  shift
  if "$@" >/dev/null 2>&1; then ok "$label"; else fail "$label"; fi
}
eq() { # $1 = label, $2 = got, $3 = expected
  if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (got '$2', expected '$3')"; fi
}
stage_end() { # $1 = stage name, $2 = fails before the stage
  RAN+=("$1")
  if [ "$FAILS" -eq "$2" ]; then echo "STAGE $1 OK"; else echo "STAGE $1 FAILED"; fi
}

# --- helpers --------------------------------------------------------------------------------------------------
gen_key() { # $1 = name, $2 = type, $3 = passphrase, $4 = comment
  ssh-keygen -q -t "$2" -N "$3" -C "$4" -f "$TMP/$1" >/dev/null 2>&1
}
exp_fp() { ssh-keygen -l -E sha256 -f "$1" | awk '{print $2}'; }
exp_type() { ssh-keygen -l -E sha256 -f "$1" | sed -n 's/.*(\([^()]*\))$/\1/p'; }
body_slice() { sed '1d;$d' "$1" | tr -d '\n' | cut -c100-129; }

# One raw HTTP/1.0 request from inside a container (busybox nc): prints the whole response, header line optional.
raw() { # $1 = container, $2 = port, $3 = path, $4 = header line (may be empty)
  docker exec "$1" sh -c 'printf "GET %s HTTP/1.0\r\nHost: x\r\n%s\r\n\r\n" "$1" "$2" | nc -w 5 127.0.0.1 "$3"' _ "$3" "$4" "$2" 2>/dev/null |
    tr -d '\000'
}
resp_code() { head -n 1 | awk '{print $2}'; }
resp_body() { sed '1,/^\r$/d'; }
resp_head() { sed -n '1,/^\r$/p'; }
collect() { printf '%s\n' "$1" >> "$TMP/everything"; }

wait_until() { # $1 = tries, rest = command; retries once per second
  local n=0 tries=$1
  shift
  while [ "$n" -lt "$tries" ]; do
    if "$@" >/dev/null 2>&1; then return 0; fi
    n=$((n + 1))
    sleep 1
  done
  return 1
}

# --- stage static ---------------------------------------------------------------------------------------------
stage_static() {
  local f0=$FAILS out
  echo "== stage static (base $BASE)"
  if git merge-base --is-ancestor "$BASE" HEAD; then ok "base $BASE is an ancestor of HEAD"; else fail "base $BASE is an ancestor of HEAD"; fi

  check "no change under admin-ui and secrets-sync versus the base (lib, skeleton, lock, docs, consumer)" \
    git diff --quiet "$BASE" -- admin-ui secrets-sync
  for f in "${LEGACY_FILES[@]}"; do
    check "legacy file $f is byte-identical to the base" git diff --quiet "$BASE" -- "haos-monitor/$f"
  done
  if [ -e "$ADDON/index.html" ]; then fail "haos-monitor/index.html is gone"; else ok "haos-monitor/index.html is gone"; fi

  check "make check-admin-ui-rules" make -C "$ROOT" check-admin-ui-rules
  out=$(make -C "$ROOT" check-admin-ui-sync 2>&1)
  eq "check-admin-ui-sync exit status" "$?" "0"
  eq "check-admin-ui-sync prints exactly five OK lines" "$(printf '%s\n' "$out" | grep -c '^OK ')" "5"
  for want in "OK admin-ui lock: 0.5.0" "OK haos-monitor lib: 0.5.0" "OK haos-monitor skeleton: 0.5.0" \
    "OK secrets-sync lib: 0.5.0" "OK secrets-sync skeleton: 0.5.0"; do
    check "sync output has '$want'" grep -qxF -- "$want" <<< "$out"
  done
  local libver
  libver=$(tr -d '[:space:]' < "$ROOT/admin-ui/app/web/static/lib/VERSION")
  for stamp in "$ADDON/app/web/static/vendor/admin-ui/LIB.stamp" "$ADDON/app/web/admin_ui/LIB.stamp"; do
    eq "$(basename "$(dirname "$stamp")") stamp version" "$(awk '$1 == "version" {print $2}' "$stamp" 2>/dev/null)" "$libver"
  done

  git show "$BASE:haos-monitor/config.yaml" > "$TMP/config.base.yaml"
  out=$(uv run --with pyyaml python3 - "$ADDON/config.yaml" "$TMP/config.base.yaml" <<'EOF'
import sys
import yaml

new = yaml.safe_load(open(sys.argv[1]))
old = yaml.safe_load(open(sys.argv[2]))
print(new["ingress_port"], sorted(new["ports"]), new["ports_description"] == old["ports_description"], new["version"])
EOF
  )
  eq "config.yaml: ingress_port, ports keys, ports_description unchanged, version" "$out" "8100 ['8099/tcp'] True 0.7.0-0"
  check "make validate-versions" make -C "$ROOT" validate-versions

  # the guard itself must work: a seeded marker (fragments again) has to be found
  printf '%s\n' "-----BEGIN ""OPENSSH PRIVATE"" KEY-----" > "$TMP/seed.txt"
  check "marker scanner detects a seeded marker" grep -qE -- "$PEM_RE" "$TMP/seed.txt"
  if grep -rIlE -- "$PEM_RE" "$ADDON" "$ROOT/.planning/quick/261102-swd-haos-monitor-admin-ui" >/dev/null 2>&1; then
    fail "no PEM private-key marker below haos-monitor/ or the quick directory"
  else ok "no PEM private-key marker below haos-monitor/ or the quick directory"; fi
  local messages
  messages=$(git log "$BASE..HEAD" --format=%B)
  if grep -qiE 'co-authored-by|generated with' <<< "$messages"; then fail "no Co-Authored-By or attribution line in any commit"; else
    ok "no Co-Authored-By or attribution line in any commit"; fi

  git show "$BASE:.github/workflows/lint.yml" > "$TMP/lint.base.yml"
  local lines
  lines=$(wc -l < "$TMP/lint.base.yml")
  head -n "$lines" "$ROOT/.github/workflows/lint.yml" > "$TMP/lint.head.yml"
  check "lint.yml is a pure append: first $lines lines equal the base" cmp -s "$TMP/lint.base.yml" "$TMP/lint.head.yml"
  stage_end static "$f0"
}

# --- stage server ---------------------------------------------------------------------------------------------
stage_server() {
  local f0=$FAILS
  echo "== stage server"
  if uv run --with pytest --with pyyaml python3 -m pytest "$ADDON/tests" -q -p no:cacheprovider; then ok "pytest haos-monitor/tests"; else
    fail "pytest haos-monitor/tests"; fi

  # Informational: the real-status.sh contract on mawk and dash (the default of an ubuntu container), not only on gawk
  if docker info >/dev/null 2>&1; then
    if timeout 300 docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT:/repo:ro" ubuntu:24.04 sh -c \
      'apt-get update -qq && apt-get install -y -qq python3 python3-pytest python3-yaml >/dev/null && cd /repo/haos-monitor && python3 -m pytest -q -p no:cacheprovider tests/test_status.py' \
      > "$TMP/ubuntu.out" 2>&1; then
      echo "info ubuntu (mawk, dash) status contract: pass"
    elif grep -qE 'passed|failed' "$TMP/ubuntu.out"; then
      echo "info ubuntu (mawk, dash) status contract: FAILED"
      tail -n 15 "$TMP/ubuntu.out"
    else
      echo "info ubuntu (mawk, dash) status contract: skipped (no network)"
    fi
  fi
  stage_end server "$f0"
}

# --- stage frontend -------------------------------------------------------------------------------------------
stage_frontend() {
  local f0=$FAILS
  echo "== stage frontend"
  if node --test "$ADDON"/tests/js/*.test.mjs > "$TMP/node.out" 2>&1; then ok "node --test haos-monitor/tests/js"; else
    fail "node --test haos-monitor/tests/js"
    tail -n 30 "$TMP/node.out"
  fi
  check "make check-admin-ui-rules" make -C "$ROOT" check-admin-ui-rules
  # haos-monitor is now a consumer of the same lib: the admin-ui suites (baseline 295 node, 354 pytest) must still pass
  if make -C "$ROOT" test-admin-ui > "$TMP/admin-ui.out" 2>&1; then ok "make test-admin-ui"; else
    fail "make test-admin-ui"
    tail -n 30 "$TMP/admin-ui.out"
  fi
  stage_end frontend "$f0"
}

# --- stage ci -------------------------------------------------------------------------------------------------
stage_ci() {
  local f0=$FAILS out
  echo "== stage ci"
  out=$(uv run --with pyyaml python3 - "$ROOT/.github/workflows/lint.yml" <<'EOF'
import sys
import yaml

doc = yaml.safe_load(open(sys.argv[1]))
jobs = doc["jobs"]
job = jobs["haos-monitor"]
steps = job["steps"]
runs = [s.get("run", "") for s in steps]
checks = {
    "last job": list(jobs)[-1] == "haos-monitor" and list(jobs)[-2] == "secrets-sync",
    "permissions": job["permissions"] == {"contents": "read"},
    "checkout": any(
        "actions/checkout" in s.get("uses", "") and s.get("with", {}).get("persist-credentials") is False for s in steps
    ),
    "node glob": "node --test haos-monitor/tests/js/*.test.mjs" in runs,
    "pytest": any(
        s.get("run") == "python -m pytest -q" and s.get("working-directory") == "haos-monitor" for s in steps
    ),
    "sync and rules": "make check-admin-ui-sync check-admin-ui-rules" in runs,
    "lint-results needs": jobs["lint-results"]["needs"] == ["lint", "admin-ui"],
}
for name, good in checks.items():
    print(("ok " if good else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)
EOF
  )
  local rc=$?
  echo "$out"
  if [ "$rc" -eq 0 ]; then ok "lint.yml job haos-monitor shape"; else fail "lint.yml job haos-monitor shape"; fi
  stage_end ci "$f0"
}

# --- stage docker ---------------------------------------------------------------------------------------------
run_hadolint() { # $1 = Dockerfile
  if command -v hadolint >/dev/null 2>&1; then hadolint "${HADOLINT_IGNORES[@]}" "$1"; else
    docker run --rm -i hadolint/hadolint hadolint "${HADOLINT_IGNORES[@]}" - < "$1"; fi
}

start_container() { # $1 = name, $2 = image, $3 = shell prefix run before /run.sh
  docker run -d --name "$1" --entrypoint sh -v "$TMP/options.json:/data/options.json:ro" "$2" \
    -c "$3 exec /run.sh" > /dev/null
}

gui_pid() { # prints the pid of the GUI python process
  docker exec "$1" sh -c "ps -o pid,args | grep '[p]ython3 -m app.main' | awk '{print \$1}' | head -n 1" 2>/dev/null
}

stage_docker() {
  local f0=$FAILS
  echo "== stage docker"
  if ! docker info >/dev/null 2>&1; then
    fail "docker available"
    stage_end docker "$f0"
    return
  fi

  # new image and, from the fixed base, the baseline image (written to a tar file first, then extracted)
  if docker build -q -t "$IMG_NEW" "$ADDON" > /dev/null 2> "$TMP/build.err"; then ok "docker build (new)"; else
    fail "docker build (new)"
    tail -n 20 "$TMP/build.err"
    stage_end docker "$f0"
    return
  fi
  mkdir -p "$TMP/base"
  git -C "$ROOT" archive "$BASE" haos-monitor -o "$TMP/base.tar"
  tar -xf "$TMP/base.tar" -C "$TMP/base"
  if docker build -q -t "$IMG_OLD" "$TMP/base/haos-monitor" > /dev/null 2> "$TMP/build-old.err"; then ok "docker build (baseline $BASE)"; else
    fail "docker build (baseline $BASE)"
    tail -n 20 "$TMP/build-old.err"
    stage_end docker "$f0"
    return
  fi
  check "hadolint on the Dockerfile" run_hadolint "$ADDON/Dockerfile"
  check "python3 and ssh-keygen in the image" docker run --rm --entrypoint sh "$IMG_NEW" -c 'command -v python3 && command -v ssh-keygen'

  gen_key k_ed ed25519 '' "$SECRET_COMMENT"
  { head -n 1 "$TMP/k_ed"; head -c 70 /dev/zero | tr '\0' 'A'; echo; tail -n 1 "$TMP/k_ed"; } > "$TMP/k_bad"
  jq -n --rawfile good "$TMP/k_ed" --rawfile bad "$TMP/k_bad" '{
    interval: 10, problem_age: 60, problem_io_full10: 30, problem_sda_inflight: 8, problem_dstate: 1, problem_kmsg: 1,
    mqtt_host: "127.0.0.1", mqtt_port: 1883, mqtt_user: "", mqtt_password: "",
    mqtt_discovery_prefix: "homeassistant", mqtt_clear_discovery: false,
    hosts: [
      {name: "Good Host", host: "127.0.0.1", port: 1, ssh_private_key: $good},
      {name: "Bad Host", host: "127.0.0.1", port: 1, ssh_private_key: $bad}
    ]}' > "$TMP/options.json"
  chmod 644 "$TMP/options.json"
  : > "$TMP/everything"

  # No -p flags. The HA base image's s6 init does not hand `docker run -e` to a plain /bin/sh CMD, so the test peer
  # override is exported by the entrypoint shell (new image only); the baseline starts the same way without it.
  start_container "$C_NEW" "$IMG_NEW" 'export HAOS_MONITOR_INGRESS_REMOTE=127.0.0.1;'
  start_container "$C_OLD" "$IMG_OLD" ''
  # shellcheck disable=SC2317,SC2329 # called indirectly through wait_until
  gui_ready() { raw "$C_NEW" 8100 / "$INGRESS_HEADER" | resp_code | grep -qx 200; }
  # shellcheck disable=SC2317,SC2329 # called indirectly through wait_until
  api_ready() { docker exec "$1" wget -qO- http://127.0.0.1:8099/api/hosts.json 2>/dev/null | jq -e 'length == 2' >/dev/null; }
  if wait_until 40 api_ready "$C_NEW" && wait_until 40 api_ready "$C_OLD" && wait_until 40 gui_ready; then ok "both containers and the GUI are up"; else
    fail "both containers and the GUI are up"
    docker logs "$C_NEW" 2>&1 | tail -n 20
  fi

  # ---- legacy parity on 8099 (no header), new container versus baseline ----
  local slug=good_host ep n o
  for ep in "/api/status.json?host=$slug" "/cgi-bin/status?host=$slug" "/api/status.json?host=bad_host"; do
    n=$(docker exec "$C_NEW" wget -qO- "http://127.0.0.1:8099$ep" 2>/dev/null)
    o=$(docker exec "$C_OLD" wget -qO- "http://127.0.0.1:8099$ep" 2>/dev/null)
    collect "$n"
    check "8099 $ep answers" jq -e 'type == "object"' <<< "$n"
    eq "8099 $ep: same key set and value types as the baseline" "$(jq -S 'map_values(type)' <<< "$n")" "$(jq -S 'map_values(type)' <<< "$o")"
  done
  n=$(docker exec "$C_NEW" wget -qO- http://127.0.0.1:8099/api/hosts.json 2>/dev/null)
  o=$(docker exec "$C_OLD" wget -qO- http://127.0.0.1:8099/api/hosts.json 2>/dev/null)
  collect "$n"
  eq "8099 /api/hosts.json identical to the baseline" "$n" "$o"
  eq "8099 /api/hosts.json lists the two hosts" "$(jq -r 'map(.slug) | join(",")' <<< "$n")" "good_host,bad_host"

  # incidents: wait for the first INCIDENT start line in both (the monitor writes it after one interval)
  # shellcheck disable=SC2317,SC2329 # called indirectly through wait_until
  has_incident() { docker exec "$1" wget -qO- "http://127.0.0.1:8099/api/incidents.json?host=$slug" 2>/dev/null | jq -e 'length > 0' >/dev/null; }
  if wait_until 60 has_incident "$C_NEW" && wait_until 60 has_incident "$C_OLD"; then ok "incident lines appear in both containers"; else
    fail "incident lines appear in both containers"; fi
  n=$(docker exec "$C_NEW" wget -qO- "http://127.0.0.1:8099/api/incidents.json?host=$slug" 2>/dev/null)
  o=$(docker exec "$C_OLD" wget -qO- "http://127.0.0.1:8099/api/incidents.json?host=$slug" 2>/dev/null)
  collect "$n"
  # the log timestamps differ per container: compare the first line without it
  eq "8099 /api/incidents.json: same first INCIDENT line as the baseline (timestamp aside)" \
    "$(jq -r '.[0]' <<< "$n" | sed 's/^[^ ]* //')" "$(jq -r '.[0]' <<< "$o" | sed 's/^[^ ]* //')"
  check "8099 /api/incidents.json is a JSON array of strings" jq -e 'type == "array" and all(type == "string")' <<< "$n"

  n=$(docker exec "$C_NEW" wget -qO- http://127.0.0.1:8099/api/metrics.txt 2>/dev/null)
  o=$(docker exec "$C_OLD" wget -qO- http://127.0.0.1:8099/api/metrics.txt 2>/dev/null)
  collect "$n"
  eq "8099 /api/metrics.txt has the same metric names as the baseline" \
    "$(grep -o '^haos_monitor_[a-z0-9_]*' <<< "$n" | sort -u | tr '\n' ' ')" "$(grep -o '^haos_monitor_[a-z0-9_]*' <<< "$o" | sort -u | tr '\n' ' ')"
  check "8099 /api/metrics.txt has the problem series" grep -q 'haos_monitor_problem{host="good_host"}' <<< "$n"
  n=$(docker exec "$C_NEW" wget -qO- http://127.0.0.1:8099/cgi-bin/metrics 2>/dev/null)
  o=$(docker exec "$C_OLD" wget -qO- http://127.0.0.1:8099/cgi-bin/metrics 2>/dev/null)
  eq "8099 /cgi-bin/metrics has the same metric names as the baseline" \
    "$(grep -o '^haos_monitor_[a-z0-9_]*' <<< "$n" | sort -u | tr '\n' ' ')" "$(grep -o '^haos_monitor_[a-z0-9_]*' <<< "$o" | sort -u | tr '\n' ' ')"

  n=$(raw "$C_NEW" 8099 "/api/status.json?host=nope" "")
  o=$(raw "$C_OLD" 8099 "/api/status.json?host=nope" "")
  eq "8099 unknown host: same 404 status line" "$(resp_code <<< "$n")" "$(resp_code <<< "$o")"
  eq "8099 unknown host: 404" "$(resp_code <<< "$n")" "404"
  eq "8099 unknown host: same JSON body" "$(resp_body <<< "$n" | tr -d '\r')" "$(resp_body <<< "$o" | tr -d '\r')"

  # ---- the page is gone from 8099 ----
  n=$(raw "$C_NEW" 8099 / "")
  o=$(raw "$C_OLD" 8099 / "")
  check "baseline served the old page on 8099 /" grep -q 'id="hosts"' <<< "$o"
  if grep -qE 'id="(hosts|app)"|<title>' <<< "$n"; then fail "8099 / no longer serves a page"; else ok "8099 / no longer serves a page"; fi
  eq "8099 / answers 404" "$(resp_code <<< "$n")" "404"

  # ---- GUI behind the gate on 8100 ----
  local path
  for path in / /api/overview /static/app.mjs; do
    n=$(raw "$C_NEW" 8100 "$path" "")
    eq "8100 $path without X-Ingress-Path: 403" "$(resp_code <<< "$n")" "403"
    eq "8100 $path without X-Ingress-Path: ingress_only" "$(resp_body <<< "$n" | jq -r '.error' 2>/dev/null)" "ingress_only"
  done
  n=$(raw "$C_NEW" 8100 / "$INGRESS_HEADER")
  eq "8100 / with header: 200" "$(resp_code <<< "$n")" "200"
  check "8100 / mentions static/app.mjs" grep -q 'static/app.mjs' <<< "$n"
  collect "$n"
  n=$(raw "$C_NEW" 8100 /static/vendor/admin-ui/base.css "$INGRESS_HEADER")
  eq "8100 base.css: 200" "$(resp_code <<< "$n")" "200"
  check "8100 base.css: text/css" grep -qi '^content-type: text/css' <<< "$n"
  n=$(raw "$C_NEW" 8100 /static/app.mjs "$INGRESS_HEADER")
  eq "8100 app.mjs: 200" "$(resp_code <<< "$n")" "200"
  check "8100 app.mjs carries a Content-Security-Policy" grep -qi '^content-security-policy:' <<< "$(resp_head <<< "$n")"
  collect "$n"
  n=$(raw "$C_NEW" 8100 / "$INGRESS_HEADER")
  check "8100 / carries a Content-Security-Policy" grep -qi '^content-security-policy:' <<< "$(resp_head <<< "$n")"
  n=$(raw "$C_NEW" 8100 /icon "$INGRESS_HEADER" | head -c 600)
  check "8100 /icon: 200 image/png" grep -qiE '^content-type: image/png' <<< "$n"
  eq "8100 /icon: 200" "$(resp_code <<< "$n")" "200"
  n=$(raw "$C_NEW" 8100 /static/vendor/admin-ui/LIB.stamp "$INGRESS_HEADER")
  eq "8100 LIB.stamp: 404" "$(resp_code <<< "$n")" "404"
  n=$(raw "$C_NEW" 8100 /api/overview "$INGRESS_HEADER")
  if grep -qi '^content-security-policy:' <<< "$(resp_head <<< "$n")"; then fail "8100 /api/overview carries no CSP"; else ok "8100 /api/overview carries no CSP"; fi
  eq "docker port prints nothing (nothing published)" "$(docker port "$C_NEW" 2>&1)" ""

  # ---- overview content ----
  local ov
  ov=$(resp_body <<< "$n" | tr -d '\r')
  collect "$ov"
  eq "overview lists exactly the two configured slugs" "$(jq -r '.hosts | map(.slug) | join(",")' <<< "$ov")" "good_host,bad_host"
  eq "overview host entries have exactly the documented keys" \
    "$(jq -r '[.hosts[] | keys | join(",")] | unique | join(";")' <<< "$ov")" "error,host,incidents,name,slug,status"
  eq "good host key_fp equals ssh-keygen -l" "$(jq -r '.hosts[0].status.key_fp' <<< "$ov")" "$(exp_fp "$TMP/k_ed.pub")"
  eq "good host key_type equals ssh-keygen -l" "$(jq -r '.hosts[0].status.key_type' <<< "$ov")" "$(exp_type "$TMP/k_ed.pub")"
  eq "damaged host shows invalid" "$(jq -r '.hosts[1].status.key_fp' <<< "$ov")" "invalid"
  eq "both hosts have problem 1" "$(jq -r '[.hosts[].status.problem] | join(",")' <<< "$ov")" "1,1"
  eq "both hosts list stale among the reasons" "$(jq -r '[.hosts[].status.reasons | contains("stale")] | join(",")' <<< "$ov")" "true,true"
  eq "overview carries an integer now_ms" "$(jq -r '.now_ms | type' <<< "$ov")" "number"
  n=$(raw "$C_NEW" 8100 "/api/overview?host=../../etc/passwd" "$INGRESS_HEADER" | resp_body | tr -d '\r')
  eq "a ?host= query changes nothing (no parameter is read)" "$(jq -c '[.hosts[].slug]' <<< "$n")" "$(jq -c '[.hosts[].slug]' <<< "$ov")"

  # ---- leak guard ----
  local logs everything s
  logs=$(docker logs "$C_NEW" 2>&1; docker logs "$C_OLD" 2>&1)
  everything=$(cat "$TMP/everything"; printf '%s\n' "$logs")
  if grep -qE -- "$PEM_RE" <<< "$everything"; then fail "no private key marker in logs and responses"; else ok "no private key marker in logs and responses"; fi
  if grep -q 'secret-comment' <<< "$everything"; then fail "no key comment in logs and responses"; else ok "no key comment in logs and responses"; fi
  s=$(body_slice "$TMP/k_ed")
  eq "key body slice has 30 characters" "${#s}" "30"
  if grep -qF -- "$s" <<< "$everything"; then fail "no key body slice in logs and responses"; else ok "no key body slice in logs and responses"; fi
  if docker logs "$C_OLD" 2>&1 | grep -q 'Bad file descriptor'; then echo "info 'Bad file descriptor' line is already in the baseline logs"; fi
  if docker logs "$C_NEW" 2>&1 | grep -q 'Traceback'; then fail "no Python traceback in the GUI logs"; else ok "no Python traceback in the GUI logs"; fi

  # ---- supervision ----
  local old new
  old=$(gui_pid "$C_NEW")
  if [ -n "$old" ] && docker exec "$C_NEW" kill "$old" 2>/dev/null; then ok "GUI process $old killed"; else fail "GUI process killed (pid '$old')"; fi
  if wait_until 10 gui_ready; then ok "GUI answers again within 10 s"; else fail "GUI answers again within 10 s"; fi
  new=$(gui_pid "$C_NEW")
  if [ -n "$new" ] && [ "$new" != "$old" ]; then ok "GUI runs under a new pid ($old -> $new)"; else fail "GUI runs under a new pid ($old -> $new)"; fi
  stage_end docker "$f0"
}

# --- main -----------------------------------------------------------------------------------------------------
ALL=(static server frontend ci docker)
STAGES=("$@")
[ "${#STAGES[@]}" -gt 0 ] || STAGES=("${ALL[@]}")
echo "base: $BASE"
for st in "${STAGES[@]}"; do
  case "$st" in
    static | server | frontend | ci | docker) "stage_$st" ;;
    *) echo "unknown stage: $st" >&2; FAILS=$((FAILS + 1)) ;;
  esac
done
if [ "$FAILS" -eq 0 ] && [ "${#RAN[@]}" -eq "${#ALL[@]}" ]; then
  complete=1
  for st in "${ALL[@]}"; do
    case " ${RAN[*]} " in *" $st "*) ;; *) complete=0 ;; esac
  done
  [ "$complete" -eq 1 ] && echo "ALL STAGES OK"
fi
[ "$FAILS" -eq 0 ]
