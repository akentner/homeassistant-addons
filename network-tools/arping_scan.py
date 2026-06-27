#!/usr/bin/env python3
"""ARP-based host detection using arping. Writes results to /data/results/arping_scan.json."""
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OPTIONS_FILE = Path("/data/options.json")
OUTPUT_FILE = Path("/data/results/arping_scan.json")

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


def arping_host(ip: str, interface: str) -> dict:
    """Sends 2 ARP requests to ip via arping (Thomas Habets, Alpine default).

    Uses -i for interface (Thomas Habets convention, not iputils -I).
    """
    cmd = ["arping", "-c", "2", "-w", "3", "-i", interface, ip]
    log.debug(f"arping: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error(f"arping {ip} Fehler: {e}")
        return {"reachable": False, "mac": None, "rtt_ms": None}

    reachable = result.returncode == 0
    mac = None
    rtt_ms = None

    if reachable:
        mac_match = re.search(r"\[([0-9A-Fa-f:]{17})\]", result.stdout)
        rtt_match = re.search(r"(\d+(?:\.\d+)?)\s*ms", result.stdout)
        if mac_match:
            mac = mac_match.group(1).upper()
        if rtt_match:
            rtt_ms = float(rtt_match.group(1))

    log.info(f"arping {ip}: {'OK' if reachable else 'FAIL'} mac={mac} rtt={rtt_ms}ms")
    return {"reachable": reachable, "mac": mac, "rtt_ms": rtt_ms}


def scan(options: dict) -> dict:
    hosts = options.get("arping_hosts", [])
    interface = options.get("interface", "eth0")
    results = []

    for host in hosts:
        ip = host.get("ip", "")
        label = host.get("label", ip)
        expected_mac = (host.get("mac") or "").upper() or None

        if not ip:
            continue

        probe = arping_host(ip, interface)
        mac_match = None
        if expected_mac and probe["mac"]:
            mac_match = probe["mac"] == expected_mac

        results.append(
            {
                "label": label,
                "ip": ip,
                "expected_mac": expected_mac,
                "reachable": probe["reachable"],
                "mac": probe["mac"],
                "mac_match": mac_match,
                "rtt_ms": probe["rtt_ms"],
            }
        )

    return {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "scan_ok": True,
        "interface": interface,
        "hosts_total": len(hosts),
        "hosts_reachable": sum(1 for r in results if r["reachable"]),
        "results": results,
    }


def write_output(data: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.rename(OUTPUT_FILE)
    log.info(f"Scan: {data['hosts_reachable']}/{data['hosts_total']} erreichbar -> {OUTPUT_FILE}")


def main() -> None:
    options = load_options()
    setup_logging(options.get("log_level", "info"))
    data = scan(options)
    write_output(data)


if __name__ == "__main__":
    main()
