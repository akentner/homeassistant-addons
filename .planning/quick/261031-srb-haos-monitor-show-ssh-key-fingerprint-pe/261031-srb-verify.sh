#!/bin/bash
# Staged verification for quick task 261031-srb (haos-monitor: show the SSH key fingerprint per host).
# Usage: 261031-srb-verify.sh [fingerprint] [status] [mqtt] [ui] [docker]   (no argument = all stages)
# Never contains a literal PEM header/footer: bad-key variants are derived from fresh keys with head/tail.
set -u

ROOT=$(git rev-parse --show-toplevel) || exit 2
ADDON="$ROOT/haos-monitor"
TMP=$(mktemp -d) || exit 2
PID=$$
IMAGE="haos-monitor-keyfp-$PID"
CONTAINER="haos-monitor-keyfp-$PID"
FAILS=0
SECRET_COMMENT='secret-comment@example'

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1
  docker rmi "$IMAGE" >/dev/null 2>&1
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
  if [ "$FAILS" -eq "$2" ]; then echo "STAGE $1 OK"; else echo "STAGE $1 FAILED"; fi
}

# --- helpers --------------------------------------------------------------------------------------------------
gen_key() { # $1 = name, $2 = type, $3 = passphrase, $4 = comment, extra args after: bits
  local name=$1 type=$2 pass=$3 comment=$4
  shift 4
  ssh-keygen -q -t "$type" "$@" -N "$pass" -C "$comment" -f "$TMP/$name" >/dev/null 2>&1
}
exp_fp() { ssh-keygen -l -E sha256 -f "$1" | awk '{print $2}'; }
exp_type() { ssh-keygen -l -E sha256 -f "$1" | sed -n 's/.*(\([^()]*\))$/\1/p'; }
body_slice() { sed '1d;$d' "$1" | tr -d '\n' | cut -c100-129; }

make_variants() {
  gen_key k_ed ed25519 '' "$SECRET_COMMENT"
  gen_key k_rsa rsa '' 'rsa-comment' -b 2048
  gen_key k_pass ed25519 'pw-123' 'pass-comment'
  tr '\n' ' ' < "$TMP/k_ed" > "$TMP/v_ed_spaces"
  awk '{printf "%s\\n", $0}' "$TMP/k_ed" > "$TMP/v_ed_bsn"
  sed 's/$/\r/' "$TMP/k_ed" > "$TMP/v_ed_crlf"
  tr '\n' ' ' < "$TMP/k_rsa" > "$TMP/v_rsa_spaces"
  { head -n 1 "$TMP/k_ed"; sed -n 2p "$TMP/k_ed"; tail -n 1 "$TMP/k_ed"; } > "$TMP/v_trunc"
  { head -n 1 "$TMP/k_ed"; head -c 70 /dev/zero | tr '\0' 'A'; echo; tail -n 1 "$TMP/k_ed"; } > "$TMP/v_badbody"
}

# --- stage fingerprint ----------------------------------------------------------------------------------------
stage_fingerprint() {
  local f0=$FAILS funcs="$TMP/funcs.sh"
  echo "== stage fingerprint"
  sed -n '/^write_key() {/,/^}/p' "$ADDON/run.sh" > "$funcs"
  if ! grep -q '^key_fingerprint() {' "$ADDON/run.sh"; then
    fail "key_fingerprint() present in run.sh"
    stage_end fingerprint "$f0"
    return
  fi
  sed -n '/^key_fingerprint() {/,/^}/p' "$ADDON/run.sh" >> "$funcs"
  make_variants

  run_case() { # $1 = raw key file; prints "KEY_FP|KEY_TYPE"; rc of the child is propagated
    sh -e -c '. "$1"; write_key "$(cat "$2")" "$3"; key_fingerprint "$3"; printf "%s|%s\n" "$KEY_FP" "$KEY_TYPE"' \
      _ "$funcs" "$1" "$TMP/written_key" 2>/dev/null
  }
  must_equal() { # $1 = label, $2 = raw file, $3 = .pub file
    local out
    out=$(run_case "$2")
    eq "$1" "$out" "$(exp_fp "$3")|$(exp_type "$3")"
  }
  must_equal "ed25519 intact" "$TMP/k_ed" "$TMP/k_ed.pub"
  must_equal "rsa intact" "$TMP/k_rsa" "$TMP/k_rsa.pub"
  must_equal "ed25519 flattened to spaces" "$TMP/v_ed_spaces" "$TMP/k_ed.pub"
  must_equal "ed25519 flattened to literal backslash-n" "$TMP/v_ed_bsn" "$TMP/k_ed.pub"
  must_equal "ed25519 with CRLF" "$TMP/v_ed_crlf" "$TMP/k_ed.pub"
  must_equal "rsa flattened to spaces" "$TMP/v_rsa_spaces" "$TMP/k_rsa.pub"

  local out rc
  for v in k_pass v_trunc v_badbody; do
    out=$(run_case "$TMP/$v")
    rc=$?
    eq "$v -> invalid| (exit 0 under sh -e)" "$out|$rc" "invalid||0"
  done

  # Leakage on the intact ed25519 case
  out=$(run_case "$TMP/k_ed")
  eq "output is exactly one line" "$(printf '%s\n' "$out" | wc -l)" "1"
  check "KEY_FP format" grep -Eq '^SHA256:[A-Za-z0-9+/]{43}[|]' <<< "$out"
  check "KEY_TYPE format" grep -Eq '[|][A-Z0-9-]+$' <<< "$out"
  if printf '%s' "$out" | grep -q "secret-comment"; then fail "no key comment in output"; else ok "no key comment in output"; fi
  if printf '%s' "$out" | grep -qF -- "$(body_slice "$TMP/k_ed")"; then fail "no key body in output"; else ok "no key body in output"; fi
  stage_end fingerprint "$f0"
}

# --- stage status ---------------------------------------------------------------------------------------------
write_fixture() { # $1 = path
  {
    printf 'good_host\tGood Host\t10.0.0.1\t22222\tSHA256:abcDEF123+/=\tED25519\n'
    printf 'bad_host\tBad Host\t10.0.0.2\t22222\tinvalid\t\n'
    printf 'old_host\tOld Host\t10.0.0.3\t22222\n'
    printf 'evil_host\tEvil Host\t10.0.0.4\t22222\tSHA256:abc"},"x":"y\tED"25519\n'
  } > "$1"
}
run_status() { # $1 = fixture, $2 = slug
  HOSTS_FILE="$1" LOGDIR="$TMP/emptylogs" ENV_FILE=/nonexistent sh "$ADDON/status.sh" "$2"
}

stage_status() {
  local f0=$FAILS fx="$TMP/fixture.hosts" out
  echo "== stage status"
  mkdir -p "$TMP/emptylogs"
  write_fixture "$fx"
  for s in good_host bad_host old_host evil_host; do
    out=$(run_status "$fx" "$s")
    check "$s: valid JSON" jq -e . <<< "$out"
    case "$s" in
      good_host)
        eq "good key_fp" "$(printf '%s' "$out" | jq -r '.key_fp')" "SHA256:abcDEF123+/="
        eq "good key_type" "$(printf '%s' "$out" | jq -r '.key_type')" "ED25519" ;;
      bad_host)
        eq "bad key_fp" "$(printf '%s' "$out" | jq -r '.key_fp')" "invalid"
        eq "bad key_type" "$(printf '%s' "$out" | jq -r '.key_type')" "" ;;
      old_host)
        eq "old key_fp (type, empty)" "$(printf '%s' "$out" | jq -r '.key_fp | type')" "string"
        eq "old key_fp" "$(printf '%s' "$out" | jq -r '.key_fp')" ""
        eq "old key_type" "$(printf '%s' "$out" | jq -r '.key_type')" "" ;;
      evil_host)
        eq "evil: no injected field" "$(printf '%s' "$out" | jq -r 'has("x")')" "false"
        check "evil key_fp filtered" jq -e '.key_fp | type == "string" and test("^[A-Za-z0-9+/:=_-]*$")' <<< "$out"
        check "evil key_type filtered" jq -e '.key_type | type == "string" and test("^[A-Za-z0-9+/:=_-]*$")' <<< "$out" ;;
    esac
    for fld in age problem reasons kmsg_last; do
      eq "$s: field $fld kept" "$(printf '%s' "$out" | jq -r "has(\"$fld\")")" "true"
    done
  done

  # Consumer regression on the same fixture
  eq "hosts.cgi lists 4 slugs" "$(HOSTS_FILE="$fx" sh "$ADDON/hosts.cgi" | tail -n +3 | jq 'length')" "4"
  out=$(HOSTS_FILE="$fx" STATUS_SH="$ADDON/status.sh" LOGDIR="$TMP/emptylogs" ENV_FILE=/nonexistent sh "$ADDON/metrics.cgi")
  check "metrics.cgi still emits haos_monitor_problem{host=good_host}" grep -q 'haos_monitor_problem{host="good_host"}' <<< "$out"
  stage_end status "$f0"
}

# --- stage mqtt -----------------------------------------------------------------------------------------------
stage_mqtt() {
  local f0=$FAILS line fx="$TMP/fixture.hosts"
  echo "== stage mqtt"
  line=$(grep '^PROBLEM_ATTRS=' "$ADDON/mqtt.sh")
  eq "exactly one PROBLEM_ATTRS line" "$(printf '%s\n' "$line" | wc -l)" "1"
  for needle in "'key_fingerprint': value_json.key_fp" "'key_type': value_json.key_type" \
    "'reasons': value_json.reasons" "'kmsg_last': value_json.kmsg_last"; do
    if grep -qF -- "$needle" <<< "$line"; then ok "PROBLEM_ATTRS contains $needle"; else fail "PROBLEM_ATTRS contains $needle"; fi
  done

  if ! uv run --with jinja2 python3 -c 'import jinja2' >/dev/null 2>&1; then
    echo "SKIP jinja render"
  else
    mkdir -p "$TMP/emptylogs"
    write_fixture "$fx"
    run_status "$fx" good_host > "$TMP/good.json"
    printf '%s' "$line" | sed 's/^PROBLEM_ATTRS="//; s/"$//' > "$TMP/template.txt"
    local rendered
    rendered=$(uv run --with jinja2 python3 -c '
import json, sys
from jinja2 import Environment
tpl = open(sys.argv[1]).read()
value_json = json.load(open(sys.argv[2]))
out = Environment().from_string(tpl).render(value_json=value_json)
d = json.loads(out)
print(d.get("key_fingerprint"), d.get("key_type"), "reasons" in d)
' "$TMP/template.txt" "$TMP/good.json" 2>&1)
    eq "jinja render carries key_fingerprint, key_type and reasons" "$rendered" "SHA256:abcDEF123+/= ED25519 True"
  fi
  stage_end mqtt "$f0"
}

# --- stage ui -------------------------------------------------------------------------------------------------
stage_ui() {
  local f0=$FAILS html="$ADDON/index.html" out
  echo "== stage ui"
  if [ "$(grep -c 'keyText(' "$html")" -ge 2 ]; then ok "keyText( used and defined"; else fail "keyText( used and defined"; fi
  if [ "$(grep -c 'SSH key' "$html")" -ge 1 ]; then ok "SSH key label present"; else fail "SSH key label present"; fi
  sed -n '/^<script>/,/^<\/script>/p' "$html" | sed '1d;$d' > "$TMP/page.js"
  check "inline script parses (node --check)" node --check "$TMP/page.js"
  sed -n '/^function keyText/,/^}/p' "$html" > "$TMP/keytext.js"
  if [ ! -s "$TMP/keytext.js" ]; then
    fail "function keyText extracted"
  else
    out=$(node -e '
const fs = require("fs");
eval(fs.readFileSync(process.argv[1], "utf8") + "; globalThis.keyText = keyText;");
const cases = [
  [{key_fp: "SHA256:abc", key_type: "ED25519"}, "ED25519 SHA256:abc"],
  [{key_fp: "SHA256:abc", key_type: ""}, "SHA256:abc"],
  [{key_fp: "invalid", key_type: ""}, "invalid"],
  [{key_fp: ""}, "–"],
  [{}, "–"],
];
let bad = 0;
cases.forEach(function (c, i) {
  const got = keyText(c[0]);
  console.log((got === c[1] ? "ok" : "FAIL") + " keyText case " + (i + 1) + " -> " + JSON.stringify(got));
  if (got !== c[1]) bad++;
});
process.exit(bad ? 1 : 0);
' "$TMP/keytext.js" 2>&1)
    local rc=$?
    echo "$out"
    [ "$rc" -eq 0 ] || FAILS=$((FAILS + 1))
  fi
  stage_end ui "$f0"
}

# --- stage docker ---------------------------------------------------------------------------------------------
stage_docker() {
  local f0=$FAILS
  echo "== stage docker"
  if ! docker info >/dev/null 2>&1; then
    fail "docker available"
    stage_end docker "$f0"
    return
  fi
  if docker build -q -t "$IMAGE" "$ADDON" >/dev/null 2>"$TMP/build.err"; then ok "docker build"; else
    fail "docker build"
    tail -n 20 "$TMP/build.err"
    stage_end docker "$f0"
    return
  fi
  check "ssh-keygen available in image" docker run --rm --entrypoint sh "$IMAGE" -c 'command -v ssh-keygen'

  make_variants
  jq -n --rawfile good "$TMP/k_ed" --rawfile flat "$TMP/v_rsa_spaces" --rawfile bad "$TMP/v_badbody" '{
    interval: 10, problem_age: 60, problem_io_full10: 30, problem_sda_inflight: 8, problem_dstate: 1, problem_kmsg: 1,
    mqtt_host: "127.0.0.1", mqtt_port: 1883, mqtt_user: "", mqtt_password: "",
    mqtt_discovery_prefix: "homeassistant", mqtt_clear_discovery: false,
    hosts: [
      {name: "Good Host", host: "127.0.0.1", port: 1, ssh_private_key: $good},
      {name: "Flat Host", host: "127.0.0.1", port: 1, ssh_private_key: $flat},
      {name: "Bad Host", host: "127.0.0.1", port: 1, ssh_private_key: $bad}
    ]}' > "$TMP/options.json"
  chmod 644 "$TMP/options.json"
  docker run -d --name "$CONTAINER" -v "$TMP/options.json:/data/options.json:ro" "$IMAGE" >/dev/null

  local url='http://127.0.0.1:8099/api/status.json?host=' n=0 good=""
  while [ "$n" -lt 30 ]; do
    good=$(docker exec "$CONTAINER" wget -qO- "${url}good_host" 2>/dev/null)
    printf '%s' "$good" | jq -e . >/dev/null 2>&1 && break
    n=$((n + 1))
    sleep 1
  done
  if printf '%s' "$good" | jq -e . >/dev/null 2>&1; then ok "status.json answers"; else
    fail "status.json answers"
    docker logs "$CONTAINER" 2>&1 | tail -n 20
  fi

  local flat bad
  flat=$(docker exec "$CONTAINER" wget -qO- "${url}flat_host" 2>/dev/null)
  bad=$(docker exec "$CONTAINER" wget -qO- "${url}bad_host" 2>/dev/null)
  eq "good_host key_fp" "$(printf '%s' "$good" | jq -r '.key_fp')" "$(exp_fp "$TMP/k_ed.pub")"
  eq "good_host key_type" "$(printf '%s' "$good" | jq -r '.key_type')" "$(exp_type "$TMP/k_ed.pub")"
  eq "flat_host key_fp" "$(printf '%s' "$flat" | jq -r '.key_fp')" "$(exp_fp "$TMP/k_rsa.pub")"
  eq "flat_host key_type" "$(printf '%s' "$flat" | jq -r '.key_type')" "$(exp_type "$TMP/k_rsa.pub")"
  eq "bad_host key_fp" "$(printf '%s' "$bad" | jq -r '.key_fp')" "invalid"
  eq "bad_host key_type" "$(printf '%s' "$bad" | jq -r '.key_type')" ""

  local hostsfile hostsjson metrics logs
  hostsfile=$(docker exec "$CONTAINER" cat /etc/haos-monitor.hosts 2>/dev/null)
  eq "hosts file has 3 lines" "$(printf '%s\n' "$hostsfile" | wc -l)" "3"
  eq "hosts file columns" "$(printf '%s\n' "$hostsfile" | awk -F'\t' '{print NF}' | sort -u)" "6"
  hostsjson=$(docker exec "$CONTAINER" wget -qO- http://127.0.0.1:8099/api/hosts.json 2>/dev/null)
  eq "hosts.json lists 3 hosts" "$(printf '%s' "$hostsjson" | jq 'length')" "3"
  metrics=$(docker exec "$CONTAINER" wget -qO- http://127.0.0.1:8099/api/metrics.txt 2>/dev/null)
  check "metrics has haos_monitor_problem{host=good_host}" grep -q 'haos_monitor_problem{host="good_host"}' <<< "$metrics"

  logs=$(docker logs "$CONTAINER" 2>&1)
  check "log: ssh key ED25519 SHA256:" grep -q "ssh key ED25519 SHA256:" <<< "$logs"
  check "log: ssh key invalid" grep -q "ssh key invalid" <<< "$logs"

  local everything="$logs$good$flat$bad$hostsfile$hostsjson$metrics" s
  # NB: split literal so this file never contains the marker as one string either
  if grep -q "PRIVATE"" KEY" <<< "$everything"; then fail "no private key marker anywhere"; else ok "no private key marker anywhere"; fi
  if grep -q "secret-comment" <<< "$everything"; then fail "no key comment anywhere"; else ok "no key comment anywhere"; fi
  for k in k_ed k_rsa; do
    s=$(body_slice "$TMP/$k")
    if grep -qF -- "$s" <<< "$everything"; then fail "no $k body slice anywhere"; else ok "no $k body slice anywhere"; fi
  done
  stage_end docker "$f0"
}

# --- main -----------------------------------------------------------------------------------------------------
STAGES=("$@")
[ "${#STAGES[@]}" -gt 0 ] || STAGES=(fingerprint status mqtt ui docker)
for st in "${STAGES[@]}"; do
  case "$st" in
    fingerprint | status | mqtt | ui | docker) "stage_$st" ;;
    *) echo "unknown stage: $st" >&2; FAILS=$((FAILS + 1)) ;;
  esac
done
[ "$FAILS" -eq 0 ]
