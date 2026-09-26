# CUPS Add-on Configuration

## Add-on Options

| Option            | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `avahi_reflector` | `false` | Disabled by default. Avahi's legacy-unicast reflector keeps a fixed-size in-memory slot table that fills up under sustained legacy-unicast mDNS traffic (e.g. from a mesh Wi-Fi repeater) and silently drops all further mDNS queries once full, including resolves of this add-on's own advertised printers — the exact bug this add-on exists to fix. Only re-enable this if the add-on is run WITHOUT `host_network: true`, where reflection across network namespaces would actually be needed. |
| `avahi_hostname`  | `cups`  | Fixed Avahi host-name, independent of the container's transient hostname. Prevents the auto-rename-on-conflict behavior (`<hostname>-2`) that made the printer's advertised mDNS name diverge from its actual resolvable address.                                                                                                                                                                                                                                                                   |
| `avahi_use_ipv6`  | `false` | Disabled by default. Avahi may resolve the add-on's mDNS hostname to an IPv6 ULA address that is unreachable/unrouted for some client devices, independent of the reflector bug.                                                                                                                                                                                                                                                                                                                    |
| `printers`        | `[]`    | List of printers to register with CUPS at startup. See [Printers](#printers) below for the object shape.                                                                                                                                                                                                                                                                                                                                                                                            |
| `log_level`       | `info`  | Log verbosity: `debug`, `info`, `warning`, `error`                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

## Printers

Each entry in the `printers` list is an object with three fields:

| Field     | Type    | Default | Description                                                                                          |
| --------- | ------- | ------- | ---------------------------------------------------------------------------------------------------- |
| `name`    | `str`   | —       | Printer queue name registered with CUPS (`lpadmin -p <name>`)                                        |
| `uri`     | `str`   | —       | Device URI CUPS uses to reach the printer. See [Supported URI schemes](#supported-uri-schemes) below |
| `enabled` | `bool?` | `true`  | Whether this printer entry is registered at startup                                                  |

### Supported URI schemes

`printers[].uri` is typed `str` (not HA's built-in `url` schema type) with an explicit runtime scheme-allowlist
validated in `generate_config.py`: `ipp`, `ipps`, `socket`, `usb`, `dnssd`, `lpd`. This was a deliberate choice — HA's
`url` type's acceptance of non-`http` CUPS URI schemes was unverified, and getting it wrong would be a costly options
schema migration for every installed user. Example values:

```yaml
printers:
  - name: "office-ipp"
    uri: "ipp://192.168.1.50:631/ipp/print"
    enabled: true
  - name: "jetdirect-printer"
    uri: "socket://192.168.1.51:9100"
    enabled: true
  - name: "usb-printer"
    uri: "usb://Acme/ModelX?serial=ABC123"
    enabled: false
```

## Design notes

**No slot-exhaustion watchdog (D-08).** There is no watchdog or log-monitoring for the
`No slot available for legacy unicast reflection` message anywhere in this add-on. With `avahi_reflector: false` as the
shipped default, this failure class cannot occur at all, so a watchdog for it would be dead code. If you re-enable
`avahi_reflector`, you re-inherit the original bug and are responsible for monitoring it yourself.

**Generic driver, not driverless auto-detection.** Printer registration uses `lpadmin -m drv:///sample.drv/generic.ppd`
(a static generic PostScript driver) rather than `-m everywhere` (CUPS driverless IPP-Everywhere). `-m everywhere`
performs a live IPP capability query against the device at registration time — a printer that is powered off or
unreachable when the add-on (re)starts would fail to register at all, which defeats the point of a persistent print
queue for a home printer that isn't always on. The generic driver registers the queue unconditionally; CUPS only
contacts the device when a job is actually printed.

## Migrating from f1c878cb_cups

See the rollout runbook — filled in by a later plan.
