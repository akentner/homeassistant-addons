# Multi-Add-on Auto-Update System

## 🚀 Overview

This system automatically monitors **multiple add-ons** for new upstream releases and updates them accordingly. It is
fully scalable for any number of add-ons.

## 📁 Add-on Setup

### Create a `.upstream.yaml` for each add-on

```text
your-addon/
├── config.yaml
├── build.yaml
├── Dockerfile
├── run.sh
└── .upstream.yaml  ← This file configures auto-updates
```

### Example `.upstream.yaml`

```yaml
upstream:
  # GitHub repository of the upstream project
  repository: "owner/project-name"

  # Pattern for version tags (default: v*)
  version_pattern: "v*"

  # Regex to remove prefixes from version tags (e.g. "v1.0.3" -> "1.0.3")
  version_strip: "^v"

addon:
  # Version strategy for the add-on:
  # - "auto": Auto-increment (0.1-3 -> 0.1-4)
  # - "sync": Use same version as upstream
  version_pattern: "auto"
```

## 🔄 What happens automatically

### 1. **Daily Check** (6:00 UTC)

- System discovers all add-ons with `.upstream.yaml`
- Checks each configured upstream repository for new releases
- Compares current with available versions

### 2. **Parallel Updates**

For each add-on with available update:

- ✅ Updates `{addon}/build.yaml` with new VERSION
- ✅ Increments add-on version in `{addon}/config.yaml`
- ✅ Creates/updates `{addon}/CHANGELOG.md`
- ✅ Creates separate commit per add-on

### 3. **Intelligent Error Handling**

- Updates run in parallel and independently (`fail-fast: false`)
- On errors: Automatic GitHub issues with add-on-specific labels
- Detailed logs per add-on

## 🎯 Manual Control

### Update all add-ons

```text
Actions → "Auto-Update Add-ons when upstream releases" → "Run workflow"
```

### Specific add-on

```text
Actions → "Run workflow"
├── addon_name: "fritz-callmonitor2mqtt"  ← Only this add-on
└── force_update: true                    ← Force update
```

## 📋 Supported Configurations

### Version Patterns

```yaml
addon:
  version_pattern: "auto"    # 0.1-3 → 0.1-4 (recommended)
  version_pattern: "sync"    # 1.0.3 → 1.0.4 (follows upstream)
```

### Upstream Patterns

```yaml
upstream:
  version_pattern: "v*"      # Matches: v1.0.3, v2.1.0
  version_pattern: "*"       # Matches: 1.0.3, 2024.10.1
  version_strip: "^v"        # v1.0.3 → 1.0.3
  version_strip: "^release-" # release-1.0.3 → 1.0.3
```

## 🏗️ Adding a New Add-on

1. **Create add-on directory:**

   ```text
   my-new-addon/
   ├── config.yaml
   ├── build.yaml
   ├── Dockerfile
   ├── run.sh
   └── .upstream.yaml
   ```

2. **Configure `.upstream.yaml`:**

   ```yaml
   upstream:
     repository: "author/my-project"
     version_strip: "^v"
   addon:
     version_pattern: "auto"
   ```

3. **Done!** The system will automatically detect the new add-on on the next run.

## 📊 Monitoring & Status

### GitHub Actions Dashboard

- **Last Run:** When add-ons were last checked
- **Matrix View:** Status for each add-on individually
- **Commit History:** All automatic updates

### Automatic Issues

- On errors: Issue with label `addon:addon-name`
- Detailed error description
- Link to failed workflow run

## 🔧 Advanced Configuration

### Adjust Schedule

```yaml
schedule:
  - cron: "0 6 * * *" # Daily at 6:00 UTC
  - cron: "0 */12 * * *" # Every 12 hours
  - cron: "0 12 * * 1" # Mondays at 12:00 UTC
```

### Webhook Integration (optional)

The system can be extended to send webhooks when updates are available.

## ✅ Benefits

🔄 **Scalable** - Unlimited number of add-ons 🎯 **Specific** - Each add-on individually configurable 🛡️ **Robust** -
Errors in one add-on don't stop the others 📝 **Traceable** - Complete commit and issue history ⚡ **Efficient** -
Parallel processing of all add-ons 🔧 **Flexible** - Manually controllable or fully automatic

The system grows automatically with your add-ons! 🚀
