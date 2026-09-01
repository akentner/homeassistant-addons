"""Validate Home Assistant add-on config.yaml files against the HA schema rules."""

import argparse
import sys
from pathlib import Path

import yaml

VALID_ARCH = {"aarch64", "amd64", "armhf", "armv7", "i386"}
VALID_STARTUP = {"application", "initialize", "system", "once", "services"}
VALID_BOOT = {"auto", "manual", "manual_only"}
VALID_MAP_TYPES = {
    "addon_config",
    "app_config",
    "backup",
    "config",
    "data",
    "media",
    "share",
    "ssl",
}
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

    # map: each entry must have a valid 'type'
    map_entries = config.get("map")
    if isinstance(map_entries, list):
        for entry in map_entries:
            if isinstance(entry, dict):
                map_type = entry.get("type")
                if map_type is not None and map_type not in VALID_MAP_TYPES:
                    errors.append(
                        f"{path}: map entry type '{map_type}' is not valid "
                        f"(valid: {sorted(VALID_MAP_TYPES)})"
                    )

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
        config_files = [
            d / "config.yaml"
            for d in Path(".").iterdir()
            if d.is_dir() and (d / "config.yaml").exists() and (d / "build.yaml").exists()
        ]

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
