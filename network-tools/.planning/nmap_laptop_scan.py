#!/usr/bin/env python3
"""Periodischer nmap ARP-Scan + JSON-Output fuer Home Assistant.

Erkennt bekannte MAC-Adressen im lokalen Subnetz und schreibt das Ergebnis
als JSON, das spaeter vom command_line sensor gelesen wird.

Verwendung:
    python3 /homeassistant/scripts/nmap_laptop_scan.py [--once] [--subnet 192.168.178.0/24]

Optionen:
    --once        Einmaliger Scan, dann exit (fuer Tests/Cron)
    --loop N      Alle N Sekunden scannen (default: 60, Endlosschleife)
    --subnet CIDR Subnetz scannen (default: 192.168.178.0/24)
    --output PATH JSON-Datei (default: /config/www/nmap_laptop_scan.json)
    --hosts HOST  JSON-Datei mit Host-MAC-Map (default: nmap_laptop_hosts.json neben Skript)

Voraussetzungen:
    - nmap installiert (apk add nmap / apt install nmap)
    - sudoers: root ALL=(ALL) NOPASSWD: /usr/bin/nmap
    - Schreibrecht im Output-Verzeichnis
"""
import argparse
import json
import logging
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SUBNET = "192.168.178.0/24"
DEFAULT_OUTPUT = "/config/www/nmap_laptop_scan.json"
DEFAULT_HOSTS = SCRIPT_DIR / "nmap_laptop_hosts.json"
DEFAULT_INTERVAL = 60
NMAP_TIMEOUT = 90

# Hosts-Datei Format: {"<MAC-upper>": "label"}
HOSTS_TEMPLATE = """{
    "74:78:27:98:90:EE": "lap-aleken-tux1 LAN (enp57s0u1u4)",
    "68:54:5A:5D:28:CA": "lap-aleken-tux1 WLAN (wlan0)",
    "AC:1A:3D:AD:8D:07": "aleken-w10-lap2 LAN (Dell-Dock)",
    "C4:3D:1A:89:3E:83": "aleken-w10-lap2 WLAN"
}
"""


log = logging.getLogger("nmap_laptop_scan")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def load_hosts(path: Path) -> dict[str, str]:
    """Laedt MAC -> Label Map. Erstellt Template-Datei falls fehlend."""
    if not path.exists():
        log.warning(f"Hosts-Datei fehlt: {path} - erstelle Template")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HOSTS_TEMPLATE)
        log.info(f"Template erstellt: {path}")
    try:
        data = json.loads(path.read_text())
        return {k.upper(): v for k, v in data.items()}
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Hosts-Datei nicht lesbar: {e}")
        return {}


def run_nmap(subnet: str, timeout: int = NMAP_TIMEOUT) -> str | None:
    """Fuehrt nmap ARP-Scan aus. Liefert XML-Output oder None bei Fehler.

    Versucht zuerst ohne sudo (HA SSH-Add-on laeuft als root).
    Fallback mit sudo fuer Hosts wo root nicht verfuegbar ist.
    """
    base_cmd = [
        "nmap", "-sn", "-PR",
        "--host-timeout", "5s",
        "--max-retries", "1",
        "-oX", "-",
        subnet,
    ]
    for cmd in (base_cmd, ["sudo", "-n"] + base_cmd):
        log.debug(f"nmap-Aufruf: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.error(f"nmap Timeout nach {timeout}s")
            return None
        except FileNotFoundError:
            log.debug(f"Binary nicht gefunden: {cmd[0]}")
            continue

        if result.returncode != 0:
            log.debug(f"nmap exit {result.returncode}: {result.stderr.strip()[:200]}")
            continue
        if not result.stdout.strip():
            log.debug("nmap lieferte leeren Output")
            continue
        return result.stdout

    log.error("nmap nicht aufrufbar (weder direkt noch via sudo)")
    return None
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log.error(f"nmap Timeout nach {timeout}s")
        return None
    except FileNotFoundError:
        log.error("nmap nicht installiert oder nicht im PATH")
        return None

    if result.returncode != 0:
        log.error(f"nmap exit {result.returncode}: {result.stderr.strip()}")
        return None
    if not result.stdout.strip():
        log.error("nmap lieferte leeren Output")
        return None
    return result.stdout


def parse_nmap_xml(xml: str) -> list[dict]:
    """Parsed nmap XML. Liefert Liste von {'ip', 'mac', 'vendor'}."""
    devices: list[dict] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        log.error(f"nmap-XML nicht parsebar: {e}")
        return devices

    for host in root.findall("host"):
        status = host.find("status")
        if status is None or status.get("state") != "up":
            continue

        ip_elem = host.find("address[@addrtype='ipv4']")
        mac_elem = host.find("address[@addrtype='mac']")
        name_elem = host.find("hostnames/hostname")

        if ip_elem is None:
            continue

        ip = ip_elem.get("addr") or ""
        mac = (mac_elem.get("addr") or "").upper() if mac_elem is not None else ""
        vendor = (mac_elem.get("vendor") or "") if mac_elem is not None else ""
        hostname = (name_elem.get("name") or "") if name_elem is not None else ""

        if not mac:
            continue

        devices.append({
            "ip": ip,
            "mac": mac,
            "vendor": vendor,
            "hostname": hostname,
        })
    return devices


def write_output(path: Path, hosts: dict[str, str], devices: list[dict],
                 subnet: str, scan_ok: bool, error: str | None = None) -> None:
    """Schreibt Ergebnis als JSON. Atomar ueber temp-Datei."""
    found_macs = {d["mac"]: d["ip"] for d in devices}
    matched = {
        mac: {"ip": found_macs[mac], "label": hosts[mac]}
        for mac in hosts
        if mac in found_macs
    }

    output = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "scan_ok": scan_ok,
        "error": error,
        "subnet": subnet,
        "total_devices": len(devices),
        "found_macs": found_macs,
        "matched": matched,
        "hosts_known": len(hosts),
        "hosts_matched": len(matched),
        "devices": devices,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(output, indent=2, sort_keys=True))
        tmp.rename(path)
    except OSError as e:
        log.error(f"Schreiben fehlgeschlagen: {e}")
        return
    log.info(
        f"Scan OK: {len(devices)} Hosts, {len(matched)}/{len(hosts)} bekannt -> {path}"
    )


def scan_once(subnet: str, output: Path, hosts: dict[str, str]) -> bool:
    """Ein Scan-Durchlauf. Liefert True bei Erfolg."""
    xml = run_nmap(subnet)
    if xml is None:
        write_output(output, hosts, [], subnet, scan_ok=False, error="nmap fehlgeschlagen")
        return False
    devices = parse_nmap_xml(xml)
    write_output(output, hosts, devices, subnet, scan_ok=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Periodischer nmap-Scan fuer Home Assistant Laptop-Erkennung",
    )
    parser.add_argument("--once", action="store_true", help="Einmaliger Scan, dann exit")
    parser.add_argument("--loop", type=int, default=None, metavar="SEC",
                        help="Endlosschleife, alle N Sekunden scannen")
    parser.add_argument("--subnet", default=DEFAULT_SUBNET, help="CIDR Subnetz")
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT),
                        help="JSON-Output-Pfad")
    parser.add_argument("--hosts", type=Path, default=DEFAULT_HOSTS,
                        help="JSON-Datei mit MAC->Label Map")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug-Output")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.once and args.loop is None:
        args.loop = DEFAULT_INTERVAL

    hosts = load_hosts(args.hosts)
    if not hosts:
        log.error("Keine Hosts definiert - Abbruch")
        return 1

    log.info(f"nmap_laptop_scan gestartet: subnet={args.subnet} hosts={len(hosts)}")
    log.info(f"Output: {args.output}")

    if args.once:
        return 0 if scan_once(args.subnet, args.output, hosts) else 1

    try:
        while True:
            scan_once(args.subnet, args.output, hosts)
            time.sleep(args.loop)
    except KeyboardInterrupt:
        log.info("Beendet durch SIGINT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
