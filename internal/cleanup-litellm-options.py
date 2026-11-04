#!/usr/bin/env python3
"""Remove obsolete LiteLLM model/provider options after a protected backup. Dry-run by default."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from urllib.request import Request, urlopen

OBSOLETE = {"models", "providers"}


def plan_options(info):
    """Accept only the stopped DB-configured LiteLLM generation and schema-absent legacy fields."""
    version = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-\d+", info.get("version", ""))
    if not version or tuple(map(int, version.groups())) < (1, 106, 6):
        raise ValueError("Unsupported LiteLLM version; inspect its configuration migration first")
    if info.get("state") != "stopped":
        raise ValueError("LiteLLM must already be stopped; this tool never stops it")
    options = info.get("options")
    schema = info.get("schema")
    if not isinstance(options, dict) or not isinstance(schema, list):
        raise ValueError("Unexpected Supervisor options/schema response")
    names = {entry["name"] for entry in schema if isinstance(entry, dict) and "name" in entry}
    if not names or names & OBSOLETE:
        raise ValueError("Legacy fields are still supported or the schema is unavailable; refusing cleanup")
    if set(options) - names - OBSOLETE:
        raise ValueError("Other unknown options exist; inspect them before cleanup")
    removed = sorted(set(options) & OBSOLETE)
    return removed, {key: value for key, value in options.items() if key not in OBSOLETE}


def backup_options(directory, options):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise ValueError("Backup directory must be private (0700)")
    path = directory / ("litellm-options-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
        json.dump(options, stream)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write cleaned options after backup")
    parser.add_argument("--slug", default="72a005f5_litellm")
    parser.add_argument("--endpoint", default="http://supervisor")
    parser.add_argument("--backup-dir", type=Path, default=Path("/data/supervisor-manifest-fixes"))
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_-]+", args.slug):
        parser.error("invalid app slug")
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        parser.error("SUPERVISOR_TOKEN is required; run inside an authorized SSH app")

    def api(suffix, payload=None):
        req = Request(args.endpoint.rstrip("/") + "/addons/" + args.slug + "/" + suffix,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                      data=None if payload is None else json.dumps(payload).encode())
        with urlopen(req, timeout=30) as response:
            result = json.load(response)
        if result.get("result") != "ok":
            raise ValueError("Supervisor rejected the request")
        return result.get("data")

    info = api("info")
    removed, cleaned = plan_options(info)
    print("Obsolete option names: " + (", ".join(removed) or "none"))
    if not args.apply or not removed:
        print("No changes made")
        return
    current = api("info")
    if current["options"] != info["options"] or current["schema"] != info["schema"] or current["version"] != info["version"] or current["state"] != "stopped":
        raise ValueError("App state/options changed during inspection; retry")
    backup = backup_options(args.backup_dir, info["options"])
    print("Protected backup: " + str(backup))
    api("options", {"options": cleaned})
    after = api("info")
    if after["options"] != cleaned or after["state"] != "stopped":
        raise ValueError("Post-update verification failed; inspect the protected backup")
    print("Cleanup verified; active options preserved, app remains stopped")


if __name__ == "__main__":
    main()
