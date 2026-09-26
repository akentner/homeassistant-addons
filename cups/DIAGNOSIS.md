# CUPS AirPrint Diagnosis — "Printer unreachable" on iOS

Date: 2026-09-26

## Symptom

Printer `192.168.178.44` (Brother MFC-7460DN), shared via the CUPS Home Assistant add-on running on `192.168.178.3`,
shows up as unreachable / disappears on iOS devices, even though the printer and the CUPS host are both online and
reachable on the LAN.

## Environment

- CUPS add-on: `MaxWinterstein/homeassistant-addons` → "CUPS Print Server" (slug `f1c878cb_cups`, version `4.2.3.4`),
  installed on HAOS host `haos-op3050-1` (`192.168.178.3`).
- Add-on runs with `host_network: true`, container hostname `f1c878cb-cups`.
- Add-on advertises AirPrint via its own **Avahi reflector mode** (per the add-on's long description).
- Printer: Brother MFC-7460DN at `192.168.178.44`, itself also advertises via mDNS as `PRN-MFC-7460DN.local`.

## Findings

1. **Network/transport layer is fine.** Both hosts respond to ping; `nmap -Pn -p 631,9100,515,161` shows CUPS's IPP port
   (631) open on `.3`, and IPP/LPD/JetDirect (631/515/9100) open on the printer `.44` directly.

2. **mDNS browse works, mDNS resolve does not.** `avahi-browse` sees the PTR records for the shared printer
   (`Brother MFC-7460DN @ f1c878cb-cups`, types `_ipp._tcp`, `_ipps._tcp`, `_printer._tcp`), but every attempt to
   _resolve_ that service (`avahi-browse -r`, `avahi-resolve`) times out ("Auszeit erreicht"). This is exactly the
   pattern that produces "printer visible in Bonjour, but unreachable" on iOS/macOS: the client can enumerate the
   service name but can't get the SRV/TXT/address records needed to actually connect.

3. **Hostname mismatch (symptom, not root cause).** `avahi-resolve -a 192.168.178.3` currently returns
   `f1c878cb-cups-2.local` (note the `-2` suffix — the sign of an Avahi hostname conflict that got auto-renamed), while
   the CUPS-published printer share advertises the host as `f1c878cb-cups` (no suffix). Even if resolution worked, this
   name wouldn't currently resolve to the live host.

4. **Root cause: Avahi's legacy-unicast reflector slot table is exhausted.** The add-on logs
   (`ha apps logs f1c878cb_cups`) are flooded with:

   ```text
   No slot available for legacy unicast reflection, dropping query packet.
   ```

   Avahi's reflector keeps a fixed-size in-memory table of slots for answering legacy (non-multicast-capable) unicast
   mDNS queries. Once that table fills up, avahi-daemon silently drops _all_ further queries that need a slot —
   including the resolve requests for the printer's own advertised services. The table is never cleaned up at runtime;
   it only clears on daemon restart. This explains both observations above: browse (pure multicast, no slot needed)
   keeps working, resolve (needs a reflector slot under this add-on's network setup) stops working once the table is
   full, and stays broken until the add-on is restarted.

5. **Likely flood source.** A device on the LAN is generating a steady stream of legacy-unicast mDNS queries.
   `fritz-rep-terrace22` (a FritzBox WLAN repeater/mesh node) is present on the network and is a common culprit — many
   repeaters/mesh APs convert multicast mDNS to per-client unicast to save airtime, which is precisely the traffic
   pattern that exhausts this slot table over time. Not confirmed with packet capture yet.

6. **Unrelated ghost record.** `avahi-browse` also shows a stale/ghost entry `Test Brother @ 2c6aefcc-cupsik` (repo hash
   `2c6aefcc`, not `f1c878cb`). `ha apps list` confirms only `f1c878cb_cups` is currently installed — this ghost is a
   leftover mDNS announcement from an earlier install (different repository/fork) that never got properly withdrawn. It
   also fails to resolve, but it isn't the current CUPS add-on and isn't the cause of the reported symptom.

## Immediate mitigation (not yet applied — pending confirmation)

Restart the add-on to clear Avahi's in-memory reflector slot table:

```bash
ssh haos-op3050-1 "ha apps restart f1c878cb_cups"
```

This is expected to be a temporary fix — if the flood source keeps generating legacy-unicast queries, the table can fill
up again over time.

## Ideas for a permanent fix (basis for adapting this add-on)

- Check whether `host_network: true` actually still needs `enable-reflector=yes` in `avahi-daemon.conf` at all.
  Reflector mode exists to bridge mDNS between two separate network namespaces/ interfaces (e.g. Docker bridge ↔ host).
  With `host_network: true` the container already shares the host's real interfaces directly, so reflection between
  namespaces may be unnecessary here — disabling it would remove this entire class of bug.
- The upstream add-on exposes no user-configurable options (`options: {}`, `schema: []`) for this — our own
  fork/adaptation should expose (or hardcode) `enable-reflector=no`, or otherwise tune/ disable the legacy-unicast
  reflector specifically (`enable-reflector` vs. a possible slot-count knob, depending on the Avahi version bundled).
- Consider whether cupsd's own Avahi/DNS-SD publishing should use a fixed, explicit hostname instead of whatever the
  container's transient hostname happens to be, to avoid the observed `f1c878cb-cups` vs. `f1c878cb-cups-2` mismatch
  independently of the slot-exhaustion issue.
- Add log monitoring/alerting (or a watchdog) for the `No slot available for legacy unicast reflection` message, so a
  stuck reflector gets caught before it silently breaks AirPrint for days.
- Identify and confirm the actual flood source (packet capture on the HAOS host's interface for unicast port 5353
  traffic) rather than assuming it's the FritzBox repeater.

## References

- Add-on repo: <https://github.com/MaxWinterstein/homeassistant-addons>
- Add-on slug: `f1c878cb_cups`, based on <https://github.com/zajac-grzegorz/homeassistant-addon-cups-airprint>

## Access & Tooling (for reproducing/continuing this investigation)

- HAOS host `haos-op3050-1` = `192.168.178.3`, reachable directly (SSH, Tailscale, and plain LAN all work from this
  workstation).
- SSH: `ssh haos-op3050-1` drops into the **Terminal & SSH add-on shell** (BusyBox), not a full host shell. From there,
  `ha <command>` is the Supervisor CLI (note: `ha addons ...` is deprecated in the installed version in favor of
  `ha apps ...`, both currently work).
- Local wrapper `~/.local/bin/ha` on this workstation just forwards `ssh haos-op3050-1 ha "$@"` — usable directly as
  `ha apps info f1c878cb_cups` etc. without an explicit ssh call.
- Useful commands used during this investigation:

  ```bash
  ha apps list                       # find the addon slug
  ha apps info f1c878cb_cups         # full addon manifest (network mode, hostname, etc.)
  ha apps logs f1c878cb_cups         # raw addon stdout/stderr log
  ha apps restart f1c878cb_cups      # full container restart (clears avahi's in-memory state)
  ```

- Local diagnostic tools available on this workstation: `avahi-browse`, `avahi-resolve`, `nmap`, `curl`, `hq` (see home
  `~/CLAUDE.md` for the `hq` HTML-query tool).

### Raw evidence

`nmap -Pn -p 631,9100,515,161 192.168.178.3 192.168.178.44`:

```text
Nmap scan report for f1c878cb-cups-2.local (192.168.178.3)
PORT     STATE  SERVICE
161/tcp  closed snmp
515/tcp  closed printer
631/tcp  open   ipp
9100/tcp closed jetdirect

Nmap scan report for PRN-MFC-7460DN.local (192.168.178.44)
PORT     STATE  SERVICE
161/tcp  closed snmp
515/tcp  open   printer
631/tcp  open   ipp
9100/tcp open   jetdirect
```

`avahi-resolve` hostname checks:

```text
$ avahi-resolve -n f1c878cb-cups.local
Fehler beim Auflösen des Rechnernamens »f1c878cb-cups.local«: Auszeit erreicht

$ avahi-resolve -n f1c878cb-cups-2.local
f1c878cb-cups-2.local   fdd8:7b39:bea1:473b:661c:a35f:91ac:a1a5

$ avahi-resolve -a 192.168.178.3
192.168.178.3   f1c878cb-cups-2.local

$ avahi-resolve -a 192.168.178.44
192.168.178.44  PRN-MFC-7460DN.local
```

`avahi-browse -rp _ipp._tcp` (filtered to the printer), showing the service resolves fine when advertised _directly by
the printer itself_ (`Brother\032MFC-7460DN`, no CUPS involved) but times out for the two CUPS-published variants:

```text
+;wlan0;IPv4;Brother\032MFC-7460DN\032\064\032f1c878cb-cups;Internet Printer;local
+;wlan0;IPv4;Brother\032MFC-7460DN;Internet Printer;local
=;wlan0;IPv4;Brother\032MFC-7460DN;Internet Printer;local;PRN-MFC-7460DN.local;192.168.178.44;631;
  "txtvers=1" "qtotal=1" "pdl=application/vnd.brother-hbp" "rp=duerqxesz5090"
  "ty=Brother MFC-7460DN" "product=(Brother MFC-7460DN)"
  "adminurl=http://PRN-MFC-7460DN.local./" "priority=50" ...
Fehler beim Auflösen des Dienstes »Brother MFC-7460DN @ f1c878cb-cups« des Typs »_ipp._tcp« in Domain »local«: Auszeit erreicht
```

`ha apps info f1c878cb_cups` (key fields only):

```yaml
name: CUPS
description: A CUPS print server with working AirPrint
slug: f1c878cb_cups
repository: f1c878cb
version: 4.2.3.4
url: https://github.com/MaxWinterstein/homeassistant-addons/
hostname: f1c878cb-cups
host_network: true
host_uts: false
ip_address: 172.30.32.1
options: {}
schema: []
network:
  631/tcp: 631
  631/udp: 631
```

`ha apps logs f1c878cb_cups` (tail, representative — repeats hundreds of times):

```text
No slot available for legacy unicast reflection, dropping query packet.
```

## Context for the next session (GSD)

**Goal (as stated by the user):** adapt/fork the CUPS add-on for their own use case, using this diagnosis as the
starting basis. The exact scope of "own use case" beyond fixing the AirPrint reliability bug is **not yet defined** —
worth surfacing as the first discuss-phase question (e.g.: stay a drop-in replacement for the upstream add-on vs. a
redesigned add-on; keep Avahi reflector mode configurable vs. remove it; add HA `options`/schema for avahi/printer
config, which the upstream add-on currently has none of; support more than one USB printer; etc.).

**Repository conventions this new add-on must follow** (`homeassistant-addons/CLAUDE.md`):

- Every add-on needs `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`, `DOCS.md`, `.upstream.yaml`.
- 3-file version sync (`config.yaml` `X.Y.Z-N`, `build.yaml` `args.VERSION` `X.Y.Z`, `README.md` badge `vX.Y.Z`) — never
  edit by hand, use `make update-version ADDON=cups VERSION=X.Y.Z`.
- Base images: `ghcr.io/home-assistant/*` only, no generic Alpine/Python/Node base images.
- GSD workflow is enforced repo-wide: file changes should go through a `/gsd:*` command (`quick`, `debug`,
  `execute-phase`), not raw edits — this is exactly what the next session is for.
- Repo already has an active `.planning/` GSD state (`PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, milestone branch
  `milestone/v1.0`) — a new "cups" add-on is most likely a new milestone or a new phase, not a brand-new GSD project.
  `/gsd:ingest-docs` can bootstrap/merge a plan from this `DIAGNOSIS.md` directly.
- Closest structural analogue among existing add-ons: `gatus/` (own `Dockerfile` + `run.sh` + a config-generation step +
  `nginx.conf`, i.e. a real service with its own config, not just a thin Python wrapper like `phone-logger`) — likely
  the best pattern reference for a CUPS add-on that needs custom `avahi-daemon.conf` handling.

**Not yet done (explicitly deferred, pending user confirmation):**

- The add-on has **not** been restarted — the live AirPrint outage is still present on `192.168.178.3` as of this
  writing.
- No packet capture was taken to confirm the legacy-unicast flood source (FritzBox repeater is a hypothesis, not
  confirmed).
- No changes have been made to `avahi-daemon.conf` or any add-on files — `cups/DIAGNOSIS.md` is the only artifact
  created so far in this repo.
