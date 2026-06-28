#!/usr/bin/env python3
"""ARP-based host detection using arping. Writes results to /data/results/arping_scan.json."""
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

OPTIONS_FILE = Path("/data/options.json")
OUTPUT_FILE = Path("/data/results/arping_scan.json")
STATE_FILE = Path("/data/state/arping_state.json")
MQTT_AVAIL_TOPIC = "network-tools/arping/availability"

LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

log = logging.getLogger("arping_scan")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=LOG_LEVEL_MAP.get(level.lower(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.error(f"Options nicht lesbar: {e}")
        return {}


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.rename(STATE_FILE)


def arping_host(ip: str, interface: str) -> dict:
    """Sends 2 ARP requests to ip via arping (Thomas Habets, Alpine default).

    Uses -i for interface (Thomas Habets convention, not iputils -I).
    Checks stdout + stderr combined — arping version/platform determines which stream is used.
    """
    cmd = ["arping", "-c", "2", "-w", "3", "-i", interface, ip]
    log.debug(f"arping: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error(f"arping {ip} Fehler: {e}")
        return {"reachable": False, "mac": None, "rtt_ms": None}

    output = result.stdout + result.stderr
    log.debug(f"arping {ip} stdout: {result.stdout!r}")
    log.debug(f"arping {ip} stderr: {result.stderr!r}")

    reachable = result.returncode == 0
    mac = None
    rtt_ms = None

    if reachable:
        # Format: "60 bytes from 44:4e:6d:22:40:48 (192.168.178.1): index=0 time=904.918 usec"
        mac_match = re.search(r"from ([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", output)
        # Prefer avg RTT from stats line; fall back to first packet usec value
        rtt_avg = re.search(r"rtt min/avg/max/std-dev = [\d.]+/([\d.]+)/", output)
        rtt_usec = re.search(r"time=([\d.]+)\s*usec", output)
        if mac_match:
            mac = mac_match.group(1).upper()
        if rtt_avg:
            rtt_ms = float(rtt_avg.group(1))
        elif rtt_usec:
            rtt_ms = float(rtt_usec.group(1)) / 1000

    log.info(f"arping {ip}: {'OK' if reachable else 'FAIL'} mac={mac} rtt={rtt_ms}ms")
    if reachable and mac is None:
        log.warning(f"arping {ip}: MAC nicht parsebar aus Output: {output!r}")
    return {"reachable": reachable, "mac": mac, "rtt_ms": rtt_ms}


def scan(options: dict, state: dict) -> dict:
    hosts = options.get("arping_hosts", [])
    interface = options.get("interface", "eth0")
    threshold = int(options.get("disconnect_threshold", 3))
    results = []

    for host in hosts:
        ip = host.get("ip", "")
        label = host.get("label", ip)
        expected_mac = (host.get("mac") or "").upper() or None
        device_name = host.get("device_name") or None

        if not ip:
            continue

        probe = arping_host(ip, interface)
        mac_match = None
        if expected_mac and probe["mac"]:
            mac_match = probe["mac"] == expected_mac

        # Flap detection: update per-host state
        host_state = state.get(ip, {"consecutive_failures": 0, "effective_reachable": True})
        if probe["reachable"]:
            host_state["consecutive_failures"] = 0
            host_state["effective_reachable"] = True
        else:
            host_state["consecutive_failures"] = host_state.get("consecutive_failures", 0) + 1
            if host_state["consecutive_failures"] >= threshold:
                host_state["effective_reachable"] = False
        host_state["last_raw_reachable"] = probe["reachable"]
        state[ip] = host_state

        results.append(
            {
                "label": label,
                "ip": ip,
                "expected_mac": expected_mac,
                "device_name": device_name,
                "reachable": probe["reachable"],
                "effective_reachable": host_state["effective_reachable"],
                "consecutive_failures": host_state["consecutive_failures"],
                "mac": probe["mac"],
                "mac_match": mac_match,
                "rtt_ms": probe["rtt_ms"],
            }
        )

    return {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "scan_ok": True,
        "interface": interface,
        "disconnect_threshold": threshold,
        "hosts_total": len(hosts),
        "hosts_reachable": sum(1 for r in results if r["effective_reachable"]),
        "results": results,
    }


def write_output(data: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.rename(OUTPUT_FILE)
    log.info(f"Scan: {data['hosts_reachable']}/{data['hosts_total']} erreichbar -> {OUTPUT_FILE}")


def _mac_to_entity_key(mac: str) -> str:
    return mac.lower().replace(":", "")


def _device_name_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _build_discovery_payload(result: dict, prefix: str, entity_key: str) -> dict:
    slug = f"networktools_arping_{entity_key}_status"
    state_topic = f"{prefix}/binary_sensor/{slug}/state"
    attrs_topic = f"{prefix}/binary_sensor/{slug}/attributes"
    device_name = result.get("device_name")
    if device_name:
        device_id = f"networktools_arping_device_{_device_name_slug(device_name)}"
        device_block = {
            "identifiers": [device_id],
            "name": device_name,
            "model": "Network Host",
            "manufacturer": "Network Tools",
        }
    else:
        device_block = {
            "identifiers": [f"networktools_arping_{entity_key}"],
            "name": result["label"],
            "model": "Network Host",
            "manufacturer": "Network Tools",
        }
    return {
        "name": result["label"],
        "unique_id": slug,
        "default_entity_id": f"binary_sensor.{slug}",
        "state_topic": state_topic,
        "json_attributes_topic": attrs_topic,
        "device_class": "connectivity",
        "payload_on": "ON",
        "payload_off": "OFF",
        "availability_topic": MQTT_AVAIL_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": device_block,
    }


def _build_attributes(result: dict, scan_timestamp: str, disconnect_threshold: int) -> dict:
    attrs: dict = {
        "ip": result["ip"],
        "label": result["label"],
        "scan_timestamp": scan_timestamp,
        "last_raw_reachable": result["reachable"],
        "consecutive_failures": result["consecutive_failures"],
        "disconnect_threshold": disconnect_threshold,
    }
    if result.get("mac"):
        attrs["mac"] = result["mac"]
    if result.get("expected_mac"):
        attrs["expected_mac"] = result["expected_mac"]
    if result.get("mac_match") is not None:
        attrs["mac_match"] = result["mac_match"]
    if result.get("rtt_ms") is not None:
        attrs["rtt_ms"] = result["rtt_ms"]
    return attrs


def publish_mqtt(data: dict, options: dict) -> None:
    if not options.get("mqtt_enabled"):
        return

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt nicht verfügbar — MQTT-Publishing übersprungen")
        return

    host = options.get("mqtt_host") or "core-mosquitto"
    port = int(options.get("mqtt_port") or 1883)
    username = options.get("mqtt_username") or None
    password = options.get("mqtt_password") or None
    prefix = (options.get("mqtt_discovery_prefix") or "homeassistant").rstrip("/")

    # paho-mqtt 2.x requires CallbackAPIVersion; 1.x does not have it
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="network-tools-arping")
    else:
        client = mqtt.Client(client_id="network-tools-arping")
    if username:
        client.username_pw_set(username, password)

    try:
        client.connect(host, port, keepalive=10)
    except OSError as e:
        log.error(f"MQTT connect {host}:{port} fehlgeschlagen: {e}")
        return

    scan_timestamp = data.get("scan_timestamp", "")
    disconnect_threshold = data.get("disconnect_threshold", 3)

    for result in data.get("results", []):
        mac = result.get("expected_mac") or result.get("mac")
        if not mac:
            log.debug(f"MQTT: kein MAC für {result['ip']} — übersprungen")
            continue

        entity_key = _mac_to_entity_key(mac)
        discovery_payload = _build_discovery_payload(result, prefix, entity_key)
        state_topic = discovery_payload["state_topic"]
        attrs_topic = discovery_payload["json_attributes_topic"]
        discovery_topic = f"{prefix}/binary_sensor/networktools_arping_{entity_key}_status/config"
        effective = result.get("effective_reachable", result["reachable"])

        client.publish(discovery_topic, json.dumps(discovery_payload), retain=True)
        client.publish(state_topic, "ON" if effective else "OFF", retain=True)
        client.publish(
            attrs_topic,
            json.dumps(_build_attributes(result, scan_timestamp, disconnect_threshold)),
            retain=True,
        )
        log.debug(f"MQTT published: {entity_key} -> {'ON' if effective else 'OFF'} (raw={'ON' if result['reachable'] else 'OFF'}, fails={result['consecutive_failures']})")

    client.disconnect()
    log.info(f"MQTT: {len(data.get('results', []))} Hosts publiziert an {host}:{port}")


def main() -> None:
    options = load_options()
    setup_logging(options.get("log_level", "info"))
    state = load_state()
    data = scan(options, state)
    save_state(state)
    write_output(data)
    publish_mqtt(data, options)


if __name__ == "__main__":
    main()
