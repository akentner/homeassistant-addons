#!/usr/bin/env python3
"""Transform HA options.json into AppConfig-compatible YAML.

HA options.json uses nested dicts for adapters (e.g. input_adapters.fritz_callmonitor),
while AppConfig expects lists of AdapterConfig objects. This script bridges the gap.
"""

import json
from pathlib import Path

import yaml

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = "/tmp/phone-logger-config.yaml"


def transform(options: dict) -> dict:
    config: dict = {}

    # Direct fields
    for key in ("log_level", "timezone"):
        if key in options:
            config[key] = options[key]

    config["data_path"] = "/addon_config"

    # phone — from pbx.phone, normalise country_code (strip leading + / 00)
    pbx_raw = options.get("pbx", {})
    phone_raw = pbx_raw.get("phone", {})
    country_code = phone_raw.get("country_code", "49")
    if country_code.startswith("+"):
        country_code = country_code[1:]
    elif country_code.startswith("00"):
        country_code = country_code[2:]
    config["phone"] = {
        "country_code": country_code,
        "local_area_code": phone_raw.get("local_area_code", ""),
    }

    # pbx — trunks / msns / devices (phone stays at top-level)
    pbx: dict = {}
    for key in ("trunks", "msns", "devices"):
        if key in pbx_raw:
            pbx[key] = pbx_raw[key]
    if pbx:
        config["pbx"] = pbx

    # input_adapters
    fritz_raw = options.get("input_adapters", {}).get("fritz_callmonitor", {})
    config["input_adapters"] = [
        {
            "type": "fritz",
            "name": "fritz",
            "enabled": fritz_raw.get("enabled", False),
            "config": {
                "host": fritz_raw.get("host", "192.168.178.1"),
                "port": fritz_raw.get("port", 1012),
            },
        },
        {"type": "rest", "name": "rest", "enabled": True},
    ]

    # resolver_adapters — sqlite and json_file always enabled
    tellows_raw = options.get("resolver_adapters", {}).get("tellows", {})
    config["resolver_adapters"] = [
        {
            "type": "json_file",
            "name": "json_file",
            "enabled": True,
            "config": {"path": "contacts.json"},
        },
        {"type": "sqlite", "name": "sqlite", "enabled": True},
        {
            "type": "tellows",
            "name": "tellows",
            "enabled": tellows_raw.get("enabled", False),
            "config": {"ttl_days": tellows_raw.get("cache_ttl_days", 30)},
        },
        {
            "type": "dastelefon",
            "name": "dastelefon",
            "enabled": True,
            "config": {"ttl_days": 30},
        },
    ]

    # output_adapters — call_log always enabled
    output_adapters: list = [
        {"type": "call_log", "name": "call_log", "enabled": True},
    ]

    # Webhooks
    for i, wh in enumerate(options.get("output_webhooks", [])):
        if wh.get("url"):
            name = wh.get("name") or f"webhook-{i + 1}"
            output_adapters.append(
                {
                    "type": "webhook",
                    "name": name,
                    "enabled": True,
                    "config": {
                        "url": wh["url"],
                        "method": wh.get("method", "POST"),
                        "headers": wh.get("headers", []),
                    },
                }
            )

    # MQTT output adapter
    mqtt = options.get("mqtt", {})
    if mqtt.get("host"):
        mqtt_config: dict = {
            "broker": mqtt["host"],
            "port": mqtt.get("port", 1883),
            "topic_prefix": mqtt.get("topic", "phone-logger"),
        }
        for key in ("client_id", "username", "password"):
            if key in mqtt:
                mqtt_config[key] = mqtt[key]
        output_adapters.append(
            {
                "type": "mqtt",
                "name": "mqtt",
                "enabled": True,
                "config": mqtt_config,
            }
        )

    config["output_adapters"] = output_adapters
    return config


def main() -> None:
    options_path = Path(OPTIONS_PATH)
    if not options_path.exists():
        print(f"No options.json at {OPTIONS_PATH}, writing empty config", flush=True)
        Path(OUTPUT_PATH).write_text("{}\n")
        return

    with open(options_path) as f:
        options = json.load(f)

    config = transform(options)

    with open(OUTPUT_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"Config written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
