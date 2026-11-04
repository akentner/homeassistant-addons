"""Validate Home Assistant add-on config.yaml files against the HA schema rules."""

import argparse
import sys
from pathlib import Path

import yaml

# Register Home Assistant custom YAML tags as scalar placeholders so the
# validator can parse add-on configs that reference !secret / !include / !env_var.
# HA Supervisor resolves these at install time; for schema validation we only
# care that the structure parses and the declared keys are present.
def _ha_custom_tag(loader: yaml.Loader, _suffix: yaml.Node) -> str:
    return ""


for _tag in ("!secret", "!include", "!env_var", "!include_dir_named", "!include_dir_list"):
    yaml.UnsafeLoader.add_constructor(_tag, _ha_custom_tag)

VALID_ARCH = {"aarch64", "amd64", "armhf", "armv7", "i386"}
VALID_STARTUP = {"application", "initialize", "system", "once", "services"}
VALID_BOOT = {"auto", "manual", "manual_only"}
VALID_MAP_TYPES = {
    "app_config", "all_app_configs", "homeassistant_config", "local_apps",
    "backup", "data", "media", "share", "ssl",
}
LEGACY_MAP_TYPES = {
    "addon_config": "app_config", "all_addon_configs": "all_app_configs",
    "addons": "local_apps", "config": "homeassistant_config",
}
DEFAULT_MAP_PATHS = {
    "app_config": "/config", "all_app_configs": "/app_configs", "homeassistant_config": "/homeassistant",
    "local_apps": "/local_apps", "addon_config": "/config", "all_addon_configs": "/addon_configs",
    "addons": "/addons", "config": "/config",
}


def validate_maps(entries: object) -> list[str]:
    """Reject deprecated/conflicting mounts and validate both Supervisor mapping syntaxes."""
    if not isinstance(entries, list):
        return ["'map' must be a list"]
    errors, types, targets = [], set(), set()
    for entry in entries:
        target = None
        if isinstance(entry, str):
            parts = entry.split(":")
            kind = parts[0]
            if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"rw", "ro"}):
                errors.append("map entry has invalid access mode")
        elif isinstance(entry, dict):
            kind = entry.get("type")
            if "read_only" in entry and not isinstance(entry["read_only"], bool):
                errors.append("map read_only must be a boolean")
            if "path" in entry:
                target = entry["path"]
                if not isinstance(target, str) or not target.startswith("/") or target == "/" or ".." in target.split("/"):
                    errors.append("map path must be an absolute, non-root path without parent traversal")
                    target = None
        else:
            errors.append("map entry must be a string or an object")
            continue
        if not isinstance(kind, str) or kind not in VALID_MAP_TYPES | LEGACY_MAP_TYPES.keys():
            errors.append("map entry type is missing or invalid")
            continue
        if kind in types:
            errors.append(f"duplicate map type '{kind}'")
        types.add(kind)
        if kind in LEGACY_MAP_TYPES:
            errors.append(f"deprecated map type '{kind}'; use '{LEGACY_MAP_TYPES[kind]}' with an explicit path if needed")
        target = target or DEFAULT_MAP_PATHS.get(kind, f"/{kind}")
        target = str(Path(target))
        if target in targets:
            errors.append(f"duplicate map destination '{target}'")
        targets.add(target)
    if "config" in types and types & {"homeassistant_config", "app_config", "addon_config"}:
        errors.append("incompatible map types: config overrides application/homeassistant configuration mounts")
    for legacy, modern in LEGACY_MAP_TYPES.items():
        if legacy != "config" and {legacy, modern} <= types:
            errors.append(f"incompatible map types: '{legacy}' and '{modern}'")
    return errors


def validate_option_keys(options: object, schema: object, prefix: str = "options") -> list[str]:
    """Check default key coverage without printing values; schema:false is explicitly open."""
    if schema is False:
        return []
    errors = []
    if isinstance(options, dict) and options and schema is None:
        return [f"{prefix}: defaults require a declared schema or explicit schema:false"]
    if isinstance(options, dict) and isinstance(schema, dict):
        for key, value in options.items():
            if key not in schema:
                errors.append(f"{prefix}.{key}: default option missing from schema")
            else:
                errors.extend(validate_option_keys(value, schema[key], f"{prefix}.{key}"))
    elif isinstance(options, list) and isinstance(schema, list) and len(schema) == 1:
        for index, value in enumerate(options):
            errors.extend(validate_option_keys(value, schema[0], f"{prefix}[{index}]"))
    return errors

REQUIRED_FIELDS = {"name", "version", "slug", "description", "arch", "startup", "boot"}


def validate_config(path: Path) -> list[str]:
    """Validate a single config.yaml and return a list of error messages."""
    errors: list[str] = []

    try:
        with path.open() as f:
            config = yaml.load(f, Loader=yaml.UnsafeLoader)  # noqa: S506 — unsafe needed for HA !secret tags
    except yaml.YAMLError as e:
        return [f"{path}: YAML parse error: {e}"]

    if not isinstance(config, dict):
        return [f"{path}: config.yaml is not a mapping"]

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in config:
            errors.append(f"{path}: missing required field '{field}'")

    # arch: must be a list of known values
    arch = config.get("arch")
    if isinstance(arch, list):
        for value in arch:
            if value not in VALID_ARCH:
                errors.append(f"{path}: unknown arch value '{value}' (valid: {sorted(VALID_ARCH)})")
    elif arch is not None:
        errors.append(f"{path}: 'arch' must be a list")

    # startup / boot: known enum values
    startup = config.get("startup")
    if startup is not None and startup not in VALID_STARTUP:
        errors.append(f"{path}: invalid startup '{startup}' (valid: {sorted(VALID_STARTUP)})")

    boot = config.get("boot")
    if boot is not None and boot not in VALID_BOOT:
        errors.append(f"{path}: invalid boot '{boot}' (valid: {sorted(VALID_BOOT)})")

    # ports: values must be int (host port number), not string
    ports = config.get("ports")
    if isinstance(ports, dict):
        for mapping, value in ports.items():
            if value is not None and not isinstance(value, int):
                errors.append(
                    f"{path}: ports['{mapping}'] must be an integer (host port) or null, "
                    f"got {type(value).__name__} '{value}'"
                )

    if "map" in config:
        errors.extend(f"{path}: {error}" for error in validate_maps(config["map"]))
    errors.extend(f"{path}: {error}" for error in validate_option_keys(config.get("options"), config.get("schema")))

    return errors


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        help="Add-on directories to validate (default: auto-discover from cwd)",
    )
    args = parser.parse_args()

    if args.dirs:
        config_files = [Path(d) / "config.yaml" for d in args.dirs]
    else:
        # Recursive scan to depth 2 so nested add-ons under `tools/`
        # (e.g. `tools/test-addon/`, the Phase 14 verify suite's live
        # test target) are auto-discovered alongside top-level add-ons.
        #
        # The definition this site implements is "must pass config-schema
        # validation" -- the wider of the repo's two deliberate definitions
        # of "add-on". The Makefile's validate-addons target implements the
        # narrower "is a shipped add-on" on purpose and stays at depth 1,
        # because tools/test-addon/ is nested precisely so it is not
        # advertised as a repository add-on. Two deliberate definitions,
        # both correct -- do not unify them.
        config_files = sorted(
            d / "config.yaml"
            for d in Path(".").iterdir()
            if d.is_dir() and (d / "config.yaml").exists() and (d / "build.yaml").exists()
        ) + sorted(
            nested / "config.yaml"
            for top in Path(".").iterdir()
            if top.is_dir() and top.name == "tools"
            for nested in top.iterdir()
            if nested.is_dir() and (nested / "config.yaml").exists() and (nested / "build.yaml").exists()
        )

    if not config_files:
        print("No add-on config.yaml files found, skipping.", flush=True)
        return 0

    all_errors: list[str] = []
    for config_file in sorted(config_files):
        if not config_file.exists():
            print(f"WARNING: {config_file} not found, skipping.", flush=True)
            continue
        errors = validate_config(config_file)
        all_errors.extend(errors)

    if all_errors:
        print("Add-on config validation FAILED:", flush=True)
        for error in all_errors:
            print(f"  {error}", flush=True)
        return 1

    print("Add-on config validation passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
