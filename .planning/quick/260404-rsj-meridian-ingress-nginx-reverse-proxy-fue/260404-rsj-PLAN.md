---
phase: quick
plan: 260404-rsj
type: execute
wave: 1
depends_on: []
files_modified:
  - meridian/Dockerfile
  - meridian/run.sh
  - meridian/config.yaml
  - meridian/nginx.conf
autonomous: true
requirements: []
must_haves:
  truths:
    - "HA Ingress panel loads Meridian UI without 404 on /telemetry/summary or /health"
    - "nginx on port 8099 forwards requests to meridian on localhost:3456"
    - "Sub-filter rewrites absolute path references in HTML responses to include X-Ingress-Path prefix"
    - "Direct LAN access on port 3456 continues to work unchanged"
  artifacts:
    - path: "meridian/nginx.conf"
      provides: "nginx reverse proxy config with sub_filter rewriting"
    - path: "meridian/Dockerfile"
      provides: "nginx installed via apk, nginx.conf copied into image"
    - path: "meridian/run.sh"
      provides: "nginx started in background before meridian"
    - path: "meridian/config.yaml"
      provides: "ingress_port changed to 8099"
  key_links:
    - from: "HA Ingress"
      to: "nginx:8099"
      via: "ingress_port in config.yaml"
    - from: "nginx:8099"
      to: "meridian:3456"
      via: "proxy_pass in nginx.conf"
    - from: "nginx sub_filter"
      to: "X-Ingress-Path header"
      via: "sub_filter_once off + multiple sub_filter rules"
---

<objective>
Add nginx as an Ingress-facing reverse proxy in the meridian add-on so that the Meridian UI's
absolute path references (/telemetry/summary, /health, /api/*, etc.) are rewritten to include
the HA Ingress path prefix.

Purpose: HA Ingress proxies requests through a sub-path (e.g., /api/hassio_ingress/<token>/). Meridian's frontend makes
absolute API calls that bypass this prefix, causing 404s. nginx intercepts at port 8099, rewrites HTML response bodies
using X-Ingress-Path, and forwards upstream to meridian.

Output: nginx.conf, updated Dockerfile (nginx install + copy), updated run.sh (nginx background start), updated
config.yaml (ingress_port: 8099). </objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@meridian/Dockerfile
@meridian/run.sh
@meridian/config.yaml
@meridian/build.yaml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create nginx.conf with X-Ingress-Path sub_filter rewriting</name>
  <files>meridian/nginx.conf</files>
  <action>
Create `meridian/nginx.conf` with the following configuration:

- `daemon off;` at top level so nginx runs in foreground when called with `nginx -g 'daemon off;'` but can also be
  forked via `nginx` (we will use background start in run.sh).
- `worker_processes 1;`
- `error_log /dev/stderr warn;`
- `pid /tmp/nginx.pid;` (writable in container without root)
- events block: `worker_connections 512;`
- http block:
  - `access_log /dev/stdout combined;`
  - `client_max_body_size 32m;` (API payloads can be large)
  - `proxy_read_timeout 300s;` (streaming completions)
  - `proxy_send_timeout 300s;`
  - server block listening on port 8099:
    - `server_name localhost;`
    - Single `location /` block:
      - `proxy_pass http://127.0.0.1:3456;`
      - `proxy_set_header Host $host;`
      - `proxy_set_header X-Real-IP $remote_addr;`
      - `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
      - Pass through the ingress header: `proxy_set_header X-Ingress-Path $http_x_ingress_path;`
      - Disable buffering for streaming: `proxy_buffering off;`
      - sub_filter rewrites — replace absolute path prefixes in HTML/JS responses with the ingress path. Use the
        variable `$http_x_ingress_path` so the substitution is dynamic. Add all of these sub_filter lines:
        ```
        sub_filter 'href="/'        'href="$http_x_ingress_path/';
        sub_filter 'src="/'         'src="$http_x_ingress_path/';
        sub_filter "href='/"        "href='$http_x_ingress_path/";
        sub_filter "src='/"         "src='$http_x_ingress_path/";
        sub_filter 'fetch("/'       'fetch("$http_x_ingress_path/';
        sub_filter "fetch('/"       "fetch('$http_x_ingress_path/";
        sub_filter '"/api/'         '"$http_x_ingress_path/api/';
        sub_filter '"/telemetry/'   '"$http_x_ingress_path/telemetry/';
        sub_filter '"/health'       '"$http_x_ingress_path/health';
        sub_filter "action='/"      "action='$http_x_ingress_path/";
        ```
        - `sub_filter_once off;` (replace all occurrences per response, not just first)
        - `sub_filter_types text/html text/javascript application/javascript;`
  - Close server and http blocks.

Note: sub_filter with variables requires `ngx_http_sub_module` which is included in nginx from Alpine's package — no
extra modules needed. </action> <verify> <automated>grep -q 'sub_filter.\*http_x_ingress_path' meridian/nginx.conf &&
grep -q 'proxy_pass http://127.0.0.1:3456' meridian/nginx.conf && grep -q 'listen 8099' meridian/nginx.conf && echo
"nginx.conf OK"</automated> </verify> <done>nginx.conf exists with listen 8099, proxy_pass to 3456, and all 10
sub_filter rules using $http_x_ingress_path.</done> </task>

<task type="auto">
  <name>Task 2: Update Dockerfile, run.sh, and config.yaml for nginx integration</name>
  <files>meridian/Dockerfile, meridian/run.sh, meridian/config.yaml</files>
  <action>
**meridian/Dockerfile** — add nginx install and copy nginx.conf, immediately after the existing
`RUN apk add --no-cache nodejs npm` line:

```dockerfile
RUN apk add --no-cache nodejs npm nginx
```

Then after `COPY run.sh /run.sh` add:

```dockerfile
COPY nginx.conf /etc/nginx/nginx.conf
```

(Replace the existing `apk add` line; keep all other lines unchanged.)

**meridian/run.sh** — after the `bashio::log.info "Starting Meridian proxy..."` line and before `exec meridian`, insert
nginx background start:

```bash
# Start nginx as ingress frontend (port 8099 -> meridian 3456)
nginx
bashio::log.info "nginx ingress proxy started on port 8099"
```

Keep `exec meridian` as the last line so S6/HA restart policy still applies to the meridian process. nginx runs as a
background daemon (default nginx behavior without `daemon off`).

**meridian/config.yaml** — change `ingress_port` from `3456` to `8099`:

```yaml
ingress_port: 8099
```

Leave `ports: 3456/tcp: 3456` unchanged — direct LAN access on 3456 continues to work. </action> <verify>
<automated>grep -q 'nginx' meridian/Dockerfile && grep -q 'nginx.conf /etc/nginx/nginx.conf' meridian/Dockerfile && grep
-q '^nginx$' meridian/run.sh && grep -q 'ingress_port: 8099' meridian/config.yaml && echo "All changes
applied"</automated> </verify> <done>

- Dockerfile installs nginx and copies nginx.conf.
- run.sh starts nginx before exec meridian.
- config.yaml has ingress_port: 8099.
- make lint passes (yamllint, shellcheck). </done> </task>

</tasks>

<verification>
After both tasks:

```bash
# Lint all changed files
make lint

# Verify file contents
grep -n 'ingress_port' meridian/config.yaml
grep -n 'nginx' meridian/Dockerfile
grep -n 'nginx' meridian/run.sh
grep -c 'sub_filter' meridian/nginx.conf
```

Expected: ingress_port: 8099, nginx in Dockerfile twice (apk + COPY), nginx in run.sh, 10 sub_filter lines.
</verification>

<success_criteria>

- nginx.conf exists with listen 8099, proxy_pass localhost:3456, sub_filter_once off, 10 sub_filter rules
- Dockerfile installs nginx via apk and copies nginx.conf to /etc/nginx/nginx.conf
- run.sh starts nginx before exec meridian
- config.yaml ingress_port is 8099 (not 3456)
- make lint passes without errors </success_criteria>

<output>
After completion, create `.planning/quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue/260404-rsj-SUMMARY.md`
with what was built, files changed, and any decisions made.
</output>
