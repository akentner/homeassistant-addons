#!/usr/bin/env python3
"""Transform HA options.json into LiteLLM-compatible YAML.

HA options.json uses HA Supervisor's nested-dict schema (e.g. providers.openai_api_key),
while LiteLLM expects a `model_list` array with explicit `model_name` + `litellm_params` keys.
This script bridges the gap.

Plan 01 ships the minimal envelope: `model_list` from options.models + empty `general_settings`.
Plan 02 expands the transformation to handle master_key/salt_key env-var references, provider_keys
routing, and `litellm_params` pass-through.
"""

import json
from pathlib import Path

import yaml

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = "/data/litellm_config.yaml"


def transform(options: dict) -> dict:
    """Translate HA options.json schema → LiteLLM proxy config.yaml.

    Plan 01 implements pass-through for `models` and emits the empty `general_settings`
    envelope. Plan 02 will add master_key, salt_key, router_settings, and provider_key
    routing (env-var references so secrets stay in /data and never land in YAML).
    """
    config: dict = {
        "model_list": list(options.get("models", [])),
        "general_settings": {},
    }
    return config


def main() -> None:
    options_path = Path(OPTIONS_PATH)
    if not options_path.exists():
        # First install / config not yet saved — emit a placeholder LiteLLM config that
        # still passes YAML validation (Plan 02 wires master_key defaults from run.sh BEFORE
        # this script is called, so on first start the env-var references are already set).
        config = {"model_list": [], "general_settings": {}}
    else:
        with options_path.open() as f:
            options = json.load(f)
        config = transform(options)

    # Plan 02 will prepend `litellm_settings: { master_key: os.environ["LITELLM_MASTER_KEY"], ... }`
    # here so the generated YAML references env-vars (no plaintext secrets in /data/litellm_config.yaml).

    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
