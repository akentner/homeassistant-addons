#!/usr/bin/env python3
"""Transform HA options.json into LiteLLM-compatible YAML.

HA options.json uses HA Supervisor's nested-dict schema (e.g. providers.openai_api_key),
while LiteLLM expects a `model_list` array with explicit `model_name` + `litellm_params` keys
AND references secrets via env-vars (not plaintext in YAML).

This script bridges the gap. Secrets NEVER land in the generated YAML — they are referenced
via `${VAR}` placeholders that bashio + run.sh materialize via env-vars before exec litellm.

Plan 02 expands the Plan 01 envelope to:
- Emit `litellm_settings.master_key: "${LITELLM_MASTER_KEY}"` (D-11 env-var pattern)
- Route each model's api_key to the appropriate provider env-var (openai → OPENAI_API_KEY, etc.)
- Emit `general_settings.telemetry: false` (LiteLLM default-on telemetry is unwanted in LAN add-on)
- Handle the full Options schema from config.yaml (D-25/D-26)
"""

import json
import os
from pathlib import Path

import yaml

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = "/data/litellm_config.yaml"

# Provider → env-var name mapping (D-25/D-26 + D-17 expansion)
PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "azure": "AZURE_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    # ollama + bedrock use a different key naming convention:
    # ollama needs no key (LAN-only), bedrock uses AWS_* env chain
    "ollama": None,
    "bedrock": "AWS_ACCESS_KEY_ID",  # + AWS_SECRET_ACCESS_KEY in env chain
    # custom_openai + others → operator must export a CUSTOM_API_KEY env-var
    # (documented in DOCS.md as a workaround for non-listed providers)
}

DEFAULT_CONFIG = {
    "model_list": [],
    "general_settings": {
        "telemetry": False,
    },
    "litellm_settings": {
        "master_key": os.environ.get("LITELLM_MASTER_KEY", ""),
        "drop_params": True,
    },
}


def _provider_env_var(provider: str) -> str | None:
    """Return the env-var name for a given provider, or None for keyless providers."""
    if provider in PROVIDER_ENV_VARS:
        return PROVIDER_ENV_VARS[provider]
    # Unknown provider → operator must export a CUSTOM_API_KEY env-var; warn via bashio
    # (the actual warning happens in run.sh before this script is invoked)
    return "CUSTOM_API_KEY"


def _build_model_entry(model: dict) -> dict:
    """Translate one HA options.models[] entry to a LiteLLM model_list entry.

    Per D-26, model.name matches `^[a-zA-Z0-9._:/+-]{1,256}$` (slash allowed for LiteLLM path
    syntax). Provider is free-form (`str?`); api_key is per-model override OR provider default.
    """
    name = model.get("name", "")
    provider = model.get("provider", "")
    api_base = model.get("api_base")
    api_key_override = model.get("api_key")  # per-model override
    model_name_alias = model.get("model_name")  # upstream alias
    litellm_params_extra = model.get("litellm_params")  # pass-through (rpm, tpm, etc.)

    # Default model_name = upstream alias if set, else the litellm path-syntax name
    upstream_model = model_name_alias or name

    # Resolve api_key: per-model override > provider default env-var
    if api_key_override:
        # Operator set a per-model key inline (still risky; DOCS.md warns to use secrets.yaml)
        api_key_ref = api_key_override
    else:
        env_var = _provider_env_var(provider)
        if env_var is None:
            # Keyless provider (ollama) — omit api_key from YAML entirely
            api_key_ref = None
        else:
            api_key_ref = f"${{{env_var}}}"

    # Build the model_list entry per LiteLLM schema
    litellm_params: dict = {"model": upstream_model}
    if api_key_ref:
        litellm_params["api_key"] = api_key_ref
    if api_base:
        litellm_params["api_base"] = api_base

    # Pass-through extra litellm_params (rpm, tpm, timeout, etc.) — operator-provided YAML/JSON
    if litellm_params_extra:
        # litellm_params_extra may be a JSON string or a dict; accept both
        if isinstance(litellm_params_extra, str):
            try:
                litellm_params.update(json.loads(litellm_params_extra))
            except json.JSONDecodeError:
                # Treat as raw passthrough if not valid JSON
                litellm_params["raw_extra"] = litellm_params_extra
        elif isinstance(litellm_params_extra, dict):
            litellm_params.update(litellm_params_extra)

    return {
        "model_name": name,
        "litellm_params": litellm_params,
    }


def transform(options: dict) -> dict:
    """Translate HA options.json schema → LiteLLM proxy config.yaml.

    Master/Salt keys are NEVER inlined — they reference env-vars that run.sh materializes
    from `/data/.litellm_*_key` files (auto-gen fallback) or `!secret` resolution.
    """
    config = {
        "model_list": [_build_model_entry(m) for m in options.get("models", [])],
        "general_settings": {
            "telemetry": False,
        },
        "litellm_settings": {
            # Env-var reference, NOT plaintext (D-11/D-12 invariant)
            "master_key": "${LITELLM_MASTER_KEY}",
            "drop_params": True,
        },
    }

    # LiteLLM 1.40+ supports salt_key for token-hashing; if available, reference it
    # (LiteLLM silently ignores unknown keys in older versions, so this is safe to emit
    # unconditionally — verified in Plan 04 E2E)
    config["litellm_settings"]["salt_key"] = "${LITELLM_SALT_KEY}"

    return config


def main() -> None:
    options_path = Path(OPTIONS_PATH)
    if not options_path.exists():
        # First install / config not yet saved — emit a placeholder LiteLLM config that
        # still passes YAML validation. run.sh has already exported LITELLM_MASTER_KEY etc.,
        # so the env-var references resolve correctly.
        config = DEFAULT_CONFIG
    else:
        with options_path.open() as f:
            options = json.load(f)
        config = transform(options)

    # Always honor runtime env-vars over any inline plaintext (security invariant)
    config["litellm_settings"]["master_key"] = "${LITELLM_MASTER_KEY}"
    config["litellm_settings"]["salt_key"] = "${LITELLM_SALT_KEY}"

    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
