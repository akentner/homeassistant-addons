# Home Assistant Add-on: Phone Logger

[![Release][release-shield]][release] [![License][license-shield]][license]

Dieses Add-on integriert das Python-Projekt [phone-logger](https://github.com/akentner/phone-logger) als Home Assistant
Add-on.

## Features

- Flexible Adapter-Konfiguration (input, resolver, output)
- Strenges, Home Assistant-konformes Schema
- Datenpersistenz über das Add-on-Volume

## Konfiguration

Die Konfiguration erfolgt über die Home Assistant Add-on-Oberfläche. Siehe `DOCS.md` für Details zum Schema und zu allen
Optionen.

## Upstream

Dieses Add-on basiert auf: <https://github.com/akentner/phone-logger>

## Hinweise

- MQTT-Unterstützung folgt in einer späteren Version.
- Für Webhooks ist aktuell nur die URL konfigurierbar.

<!-- Badge Links -->

[release-shield]: https://img.shields.io/badge/version-v1.0.3-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.3
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
