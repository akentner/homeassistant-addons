#!/usr/bin/env python3
"""Merge HA options into a Gatus-compatible config.yaml.

Reads /data/options.json (HA add-on options) and optionally /addon_config/config.yaml
(user-provided Gatus config with endpoints, alerting, etc.). Produces a merged config
at /tmp/gatus-config.yaml with web.port and operational settings forced from HA options.
"""

import json
import sys
from pathlib import Path

import yaml

OPTIONS_PATH = "/data/options.json"
USER_CONFIG_PATH = "/addon_config/config.yaml"
OUTPUT_PATH = "/tmp/gatus-config.yaml"

INGRESS_PORT = 8099

EXAMPLE_CONFIG = {
    "endpoints": [
        {
            "name": "Example",
            "url": "https://example.com",
            "interval": "5m",
            "conditions": ["[STATUS] == 200"],
        }
    ]
}


def load_options() -> dict:
    path = Path(OPTIONS_PATH)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def load_user_config() -> dict:
    path = Path(USER_CONFIG_PATH)
    if not path.exists():
        print(f"No user config at {USER_CONFIG_PATH}, using example endpoint.", flush=True)
        return dict(EXAMPLE_CONFIG)
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def build_config(options: dict, user_config: dict) -> dict:
    config = dict(user_config)

    # web section — port and address are always overridden for HA ingress
    web = config.get("web", {})
    if not isinstance(web, dict):
        web = {}
    web["port"] = INGRESS_PORT
    web["address"] = "0.0.0.0"
    config["web"] = web

    # storage
    storage_type = options.get("storage_type", "memory")
    storage: dict = {"type": storage_type}
    if storage_type == "sqlite":
        storage["path"] = "/addon_config/gatus.db"
        storage["caching"] = True  # in-memory cache to reduce DB reads
    config["storage"] = storage

    # metrics
    if "metrics" in options:
        config["metrics"] = bool(options["metrics"])

    return config


def main() -> None:
    options = load_options()
    user_config = load_user_config()
    config = build_config(options, user_config)

    output = Path(OUTPUT_PATH)
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Config written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
