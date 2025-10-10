# Home Assistant Add-ons Repository by akentner

Home Assistant Add-Ons managed by akentner

This repository contains Home Assistant add-ons with automated upstream monitoring and update capabilities.

Add-on documentation: <https://developers.home-assistant.io/docs/add-ons>

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fakentner%2Fhomeassistant-addons)

## Features

✅ **Automated Updates** - Add-ons automatically track upstream releases
🔄 **Multi-Add-on Support** - Scalable system for unlimited add-ons
📝 **Version Management** - Automatic version bumping and changelog generation
🛡️ **Error Handling** - Robust error handling with GitHub issue creation
⚡ **Parallel Processing** - All add-ons updated simultaneously

See [Auto-Update Documentation](./docs/AUTO_UPDATE_GUIDE.md) for details.

## Add-ons

This repository contains the following add-ons:

### [Fritz!Box Call Monitor to MQTT](./fritz-callmonitor2mqtt)

![Supports amd64 Architecture][amd64-shield]

_Monitors Fritz!Box call events and forwards them to MQTT broker._

**Features:**

- Real-time call monitoring from Fritz!Box
- MQTT integration for Home Assistant
- Configurable country codes and area codes
- Automatic upstream version tracking
- Health check endpoint

## Development

### Adding New Add-ons

1. Create a new directory for your add-on
2. Add the required files: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`
3. Create `.upstream.yaml` for automatic updates (optional)
4. Update this README.md

### Auto-Update System

The repository includes an automated system that monitors upstream repositories for new releases and automatically updates add-ons. See [docs/AUTO_UPDATE_GUIDE.md](./docs/AUTO_UPDATE_GUIDE.md) for complete documentation.

### Manual Testing

Use the included development container to test add-ons locally:

```bash
# Start Home Assistant Supervisor in dev mode
supervisor_run
```

## Documentation

- [Auto-Update System Guide](./docs/AUTO_UPDATE_GUIDE.md) - Complete guide for automated upstream monitoring
- [Home Assistant Add-on Development](https://developers.home-assistant.io/docs/add-ons) - Official documentation

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
