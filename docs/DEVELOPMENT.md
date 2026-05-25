# Development Guidelines

## Versioning Rules

Each add-on follows a specific versioning scheme for better management.

### Version Format per File

| File          | Format    | Example   | Purpose                      |
| ------------- | --------- | --------- | ---------------------------- |
| `config.yaml` | `X.Y.Z-N` | `1.3.1-0` | Add-on version with subpatch |
| `build.yaml`  | `X.Y.Z`   | `1.3.1`   | Upstream binary version      |
| `README.md`   | `vX.Y.Z`  | `v1.3.1`  | Badge display version        |

### Rules

1. **config.yaml**:

   - Always use subpatch format: `"X.Y.Z-N"`
   - New upstream versions start with `-0`
   - Add-on-only fixes increment: `-1`, `-2`, etc.

2. **build.yaml**:

   - Upstream version only, no subpatch: `"X.Y.Z"`
   - Matches the Docker image version

3. **README.md**:
   - Badge shows main version: `version-vX.Y.Z`
   - Release link shows main version: `tree/vX.Y.Z`

### Example of Correct Versioning

```yaml
# config.yaml
version: "1.3.1-0"

# build.yaml
VERSION: "1.3.1"

# README.md
[release-shield]: https://img.shields.io/badge/version-v1.3.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.3.1
```

### Why This Structure?

- **Upstream-Sync**: Add-on version follows upstream with `-0` reset
- **Add-on-Fixes**: Local fixes can be incremented independently
- **Clarity**: Clear separation between add-on and binary version
- **Maintainability**: Better version control and update management

## Version Update Tool

For manual version updates an automated tool is available:

```bash
# Simple version update
make update-version ADDON=<addon-name> VERSION=1.7.2

# With GitHub Release Check
make update-version ADDON=<addon-name> VERSION=1.7.2 CHECK_RELEASE=yes

# Dry-run mode (show only, no changes)
./scripts/update-version.py <addon-name> 1.7.2 --dry-run
```

The tool automatically updates:

- `config.yaml`: `version: "1.7.2-0"`
- `build.yaml`: `VERSION: "1.7.2"`
- `README.md`: Badges and release links

## Auto-Update System

Add-ons using `version_pattern: "sync"` in `.upstream.yaml` benefit from:

- Automatic detection of new upstream versions
- Automatic update of `config.yaml`
- Automatic reset of subpatch to `-0`

## Pre-commit Validation

A pre-commit hook automatically validates:

- Correct versioning in all files
- Consistency between version entries
- Compliance with the subpatch format
