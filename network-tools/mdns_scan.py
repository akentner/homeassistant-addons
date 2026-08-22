#!/usr/bin/env python3
"""Generic mDNS/DNS-SD service monitor for the network-tools add-on.

For each monitor in /data/options.json -> mdns_monitors[]:
    1. Run `avahi-browse -artp -t <timeout> <service_type>` for each configured type
    2. Parse the parsable output (semicolon-separated: event;iface;proto;name;type;domain;host;address;port;txt)
    3. Apply case-insensitive substring filter against name|host|address
    4. Run `avahi-resolve -n <host>` on the first matched host to verify resolution
    5. Classify the result: online (announced + resolved) | announced_unresolved | not_found | error
    6. Publish MQTT state (online|offline|unknown), details (JSON), last_check (ISO timestamp)
    7. Publish HA MQTT Discovery: binary_sensor (connectivity) + sensor (state mirror) + sensor (last_check)

Shares the availability topic with arping_scan.py: network-tools/arping/availability - single LWT for
the container.

Usage:
    python3 /usr/local/bin/mdns_scan.py    # one full pass over all configured monitors
"""
import json
import logging
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

OPTIONS_FILE = Path("/data/options.json")
OUTPUT_FILE = Path("/data/results/mdns_scan.json")
SHARED_AVAIL_TOPIC = "network-tools/arping/availability"

LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

log = logging.getLogger("mdns_scan")


def setup_logging(level: str) -> None:
    """Configure root logging with level from options.json."""
    logging.basicConfig(
        level=LOG_LEVEL_MAP.get(level.lower(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def load_options() -> dict:
    """Read /data/options.json. Returns {} on error."""
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.error(f"Options nicht lesbar: {e}")
        return {}


def slugify(value: str) -> str:
    """URI-safe slug for entity IDs and device identifiers."""
    s = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return s or "monitor"


# avahi-browse -p (parsable) format:
#   EVENT;IFACE;PROTO;NAME;TYPE;DOMAIN;HOST;ADDRESS;PORT;TXT_LIST
# EVENT is one of: = (cached), + (new/probing), - (going away)
LINE_RE = re.compile(
    r"^([=+\-]);([^;]+);([^;]+);([^;]+);([^;]+);([^;]+);([^;]+);([^;]+);(\d+);(.*)$"
)


def parse_avahi_line(line: str) -> Optional[dict]:
    """Parse one line of `avahi-browse -artp` output. Returns None on malformed lines."""
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    txt_part = m.group(10)
    txt = re.findall(r'"([^"]*)"', txt_part)
    return {
        "event": m.group(1),
        "iface": m.group(2),
        "proto": m.group(3),
        "name": m.group(4),
        "type": m.group(5),
        "domain": m.group(6),
        "host": m.group(7),
        "address": m.group(8),
        "port": int(m.group(9)),
        "txt": txt,
    }


def matches_filter(parsed: dict, filter_patterns) -> bool:
    """Case-insensitive substring match against name|host|address. Empty filter -> match always.

    Accepts list[str] (any-pattern OR semantics) or None.
    """
    if not filter_patterns:
        return True
    haystack = " ".join(
        [parsed.get("name", ""), parsed.get("host", ""), parsed.get("address", "")]
    ).lower()
    return any(str(p).lower() in haystack for p in filter_patterns)


def resolve_host(host: str, timeout: int) -> bool:
    """Run avahi-resolve to confirm a service's host is resolvable. Returns True on success."""
    cmd = ["avahi-resolve", "-n", host]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.debug(f"avahi-resolve {host} error: {e}")
        return False
    return result.returncode == 0


def _run_avahi_browse(service_type: str, timeout: int) -> tuple[list[dict], str]:
    """Run avahi-browse for one service_type. Returns (parsed_lines, error_or_empty)."""
    cmd = ["avahi-browse", "-artp", "-t", str(timeout), service_type]
    log.debug(f"avahi-browse: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5, check=False
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error(f"avahi-browse {service_type} Fehler: {e}")
        return [], f"avahi-browse failed: {e}"

    output = (result.stdout or "") + (result.stderr or "")
    parsed: list[dict] = []
    for line in output.splitlines():
        if not line or line.startswith(";"):
            continue
        p = parse_avahi_line(line)
        if p is None:
            continue
        # Skip "going away" events - they are transient state, not a positive announcement
        if p["event"] == "-":
            continue
        parsed.append(p)
    log.debug(
        f"avahi-browse {service_type}: {len(parsed)} parsed lines (rc={result.returncode})"
    )
    if not parsed:
        return parsed, "no output"
    return parsed, ""


def classify(parsed_results: list[dict], filter_patterns: list, resolve_timeout: int) -> dict:
    """Classify parsed avahi-browse lines into one of online|announced_unresolved|not_found|error.

    Returns a dict with 'state' and optionally 'matched' (the first parsed entry that matched the filter).
    """
    matched = [p for p in parsed_results if matches_filter(p, filter_patterns)]
    if not matched:
        return {"state": "not_found", "matched": None}
    chosen = matched[0]
    if resolve_host(chosen["host"], resolve_timeout):
        return {"state": "online", "matched": chosen}
    return {"state": "announced_unresolved", "matched": chosen}


def run_monitor(monitor: dict) -> dict:
    """Run one monitor end-to-end. Returns a result dict for publish_mqtt + write_output."""
    name = monitor.get("name", "monitor")
    types = monitor.get("service_types", [])
    filter_patterns = monitor.get("filter", [])
    timeout = int(monitor.get("timeout", 10))
    started = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    all_parsed: list[dict] = []
    error: Optional[str] = None
    for service_type in types:
        parsed, err = _run_avahi_browse(service_type, timeout)
        if err:
            error = err
            break
        all_parsed.extend(parsed)

    duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    classification = classify(all_parsed, filter_patterns, timeout)
    state = "error" if error else classification["state"]
    matched = classification.get("matched")

    result = {
        "name": name,
        "state": state,
        "timestamp": started.isoformat(),
        "service_type": matched["type"] if matched else (types[0] if types else None),
        "service_name": matched["name"] if matched else None,
        "hostname": matched["host"] if matched else None,
        "address": matched["address"] if matched else None,
        "port": matched["port"] if matched else None,
        "txt_records": matched["txt"] if matched else [],
        "error": error,
        "duration_ms": duration_ms,
        "filter": filter_patterns,
        "service_types_scanned": types,
    }
    log.info(
        f"monitor {name}: state={state} matched={bool(matched)} error={error}"
    )
    return result


def _state_topic_for(prefix: str) -> str:
    return f"{prefix.rstrip('/')}/state"


def _details_topic_for(prefix: str) -> str:
    return f"{prefix.rstrip('/')}/details"


def _last_check_topic_for(prefix: str) -> str:
    return f"{prefix.rstrip('/')}/last_check"


def _build_device_block(monitor: dict, slug: str) -> dict:
    """Build the HA device block for one monitor."""
    name = monitor.get("device_name") or monitor.get("name") or slug
    return {
        "identifiers": [f"networktools_mdns_{slug}"],
        "name": name,
        "model": "mDNS Monitor",
        "manufacturer": "Network Tools",
    }


def _build_discovery_payloads(monitor: dict, discovery_prefix: str, slug: str) -> dict:
    """Build the 3 HA Discovery payloads for one monitor.

    Returns dict with keys 'binary_sensor', 'sensor_state', 'sensor_last_check' plus '_topic_prefix'.
    """
    topic_prefix = (
        monitor.get("topic_prefix")
        or f"homeassistant/monitor/networktools_mdns_{slug}"
    )
    state_topic = _state_topic_for(topic_prefix)
    details_topic = _details_topic_for(topic_prefix)
    last_check_topic = _last_check_topic_for(topic_prefix)
    interval = int(monitor.get("interval", 60))
    expire_after = max(60, interval * 2)
    device = _build_device_block(monitor, slug)
    friendly = monitor.get("device_name") or monitor.get("name") or slug

    binary_sensor = {
        "name": f"{friendly} verfuegbar",
        "unique_id": f"networktools_mdns_{slug}_available",
        "default_entity_id": f"binary_sensor.networktools_mdns_{slug}_available",
        "state_topic": state_topic,
        "json_attributes_topic": details_topic,
        "device_class": "connectivity",
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability_topic": SHARED_AVAIL_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "expire_after": expire_after,
        "device": device,
    }
    sensor_state = {
        "name": f"{friendly} Status",
        "unique_id": f"networktools_mdns_{slug}_state",
        "default_entity_id": f"sensor.networktools_mdns_{slug}_state",
        "state_topic": state_topic,
        "json_attributes_topic": details_topic,
        "availability_topic": SHARED_AVAIL_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "expire_after": expire_after,
        "device": device,
    }
    sensor_last_check = {
        "name": f"{friendly} letzter Check",
        "unique_id": f"networktools_mdns_{slug}_last_check",
        "default_entity_id": f"sensor.networktools_mdns_{slug}_last_check",
        "state_topic": last_check_topic,
        "json_attributes_topic": details_topic,
        "device_class": "timestamp",
        "availability_topic": SHARED_AVAIL_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "expire_after": expire_after,
        "device": device,
    }
    return {
        "binary_sensor": binary_sensor,
        "sensor_state": sensor_state,
        "sensor_last_check": sensor_last_check,
        "_topic_prefix": topic_prefix,
    }


def _state_to_binary(state: str) -> str:
    """Map internal state to Binary Sensor payload.

    - online -> ON
    - announced_unresolved / not_found -> OFF
    - error -> OFF (HA will show 'unknown' via the state sensor instead)
    """
    return "ON" if state == "online" else "OFF"


def _state_text_for_sensor(state: str) -> str:
    """Plain text payload for the state sensor: online|offline|unknown."""
    if state == "online":
        return "online"
    if state == "error":
        return "unknown"
    return "offline"


def publish_mqtt(monitor: dict, result: dict, options: dict, slug: str) -> None:
    """Publish discovery + state + details + last_check + birth for one monitor."""
    if not options.get("mqtt_enabled"):
        return
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt nicht verfuegbar - MQTT-Publishing uebersprungen")
        return

    host = options.get("mqtt_host") or "core-mosquitto"
    port = int(options.get("mqtt_port") or 1883)
    username = options.get("mqtt_username") or None
    password = options.get("mqtt_password") or None
    discovery_prefix = (
        options.get("mqtt_discovery_prefix") or "homeassistant"
    ).rstrip("/")

    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1, client_id="network-tools-mdns"
        )
    else:
        client = mqtt.Client(client_id="network-tools-mdns")
    if username:
        client.username_pw_set(username, password)

    try:
        client.connect(host, port, keepalive=10)
    except OSError as e:
        log.error(f"MQTT connect {host}:{port} fehlgeschlagen: {e}")
        return

    # Re-publish the shared birth message - single LWT covers both arping and mdns loops
    client.publish(SHARED_AVAIL_TOPIC, "online", retain=True)

    payloads = _build_discovery_payloads(monitor, discovery_prefix, slug)
    topic_prefix = payloads.pop("_topic_prefix")
    state_topic = _state_topic_for(topic_prefix)
    details_topic = _details_topic_for(topic_prefix)
    last_check_topic = _last_check_topic_for(topic_prefix)

    discovery_topics = {
        "binary_sensor": (
            f"{discovery_prefix}/binary_sensor/networktools_mdns_"
            f"{slug}_available/config"
        ),
        "sensor_state": (
            f"{discovery_prefix}/sensor/networktools_mdns_{slug}_state/config"
        ),
        "sensor_last_check": (
            f"{discovery_prefix}/sensor/networktools_mdns_{slug}_last_check/config"
        ),
    }

    try:
        for kind, topic in discovery_topics.items():
            client.publish(topic, json.dumps(payloads[kind]), retain=True)
        state_payload = _state_text_for_sensor(result["state"])
        client.publish(state_topic, state_payload, retain=True, qos=1)
        client.publish(details_topic, json.dumps(result, default=str), retain=True)
        client.publish(last_check_topic, result["timestamp"], retain=True)
        log.debug(
            f"MQTT published: {slug} -> state={state_payload} matched={bool(result.get('service_name'))}"
        )
    except OSError as e:
        log.error(f"MQTT publish failed for {slug}: {e}")
    finally:
        try:
            client.disconnect()
        except OSError:
            pass


def write_output(results: list[dict]) -> None:
    """Write aggregated scan results to /data/results/mdns_scan.json."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "monitors_total": len(results),
        "monitors_online": sum(1 for r in results if r["state"] == "online"),
        "monitors_offline": sum(
            1 for r in results if r["state"] in ("not_found", "announced_unresolved")
        ),
        "monitors_error": sum(1 for r in results if r["state"] == "error"),
        "results": results,
    }
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    tmp.rename(OUTPUT_FILE)
    log.info(
        f"mDNS scan: {payload['monitors_online']}/{payload['monitors_total']} online -> {OUTPUT_FILE}"
    )


def main() -> None:
    """Read options, iterate monitors, publish MQTT, write output JSON."""
    options = load_options()
    setup_logging(options.get("log_level", "info"))
    monitors = options.get("mdns_monitors", [])
    if not monitors:
        log.info("Keine mdns_monitors konfiguriert - exit")
        write_output([])
        return
    results: list[dict] = []
    for monitor in monitors:
        if not monitor.get("enabled", True):
            log.info(f"monitor {monitor.get('name')} disabled - skipped")
            continue
        slug = slugify(monitor.get("name", "monitor"))
        try:
            result = run_monitor(monitor)
        except Exception as e:  # noqa: BLE001 - keep main loop resilient
            log.error(f"monitor {monitor.get('name')} crashed: {e}")
            result = {
                "name": monitor.get("name", "monitor"),
                "state": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service_type": None,
                "service_name": None,
                "hostname": None,
                "address": None,
                "port": None,
                "txt_records": [],
                "error": f"crash: {e}",
                "duration_ms": 0,
                "filter": monitor.get("filter", []),
                "service_types_scanned": monitor.get("service_types", []),
            }
        results.append(result)
        try:
            publish_mqtt(monitor, result, options, slug)
        except Exception as e:  # noqa: BLE001 - publish failures must not crash the loop
            log.error(f"publish_mqtt failed for {monitor.get('name')}: {e}")
    write_output(results)


if __name__ == "__main__":
    main()