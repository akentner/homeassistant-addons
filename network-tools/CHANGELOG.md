# Changelog

All notable changes to the **Network Tools** add-on are documented in this file. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

This add-on has no upstream — every entry below is hand-written by the maintainers.

## [Unreleased]

### Added

- _Nothing yet._

## [0.5.0-3] - 2026-09-27

### Fixed

- Ship a minimal `avahi-daemon.conf` with `[publish]\npublish-addresses=no`. This add-on's avahi-daemon only ever
  browses (`avahi-browse`, for the `mdns_monitors` feature) and never needs to advertise itself, but previously ran with
  the Alpine package's default (publishing-enabled) config. Because this add-on runs `host_network: true`, its
  avahi-daemon shared the host's IP addresses with every other host_network add-on (e.g. `cups`), and its default
  reverse-PTR publication raced with theirs — causing a perpetual, mutual RFC 6762 probe-conflict rename loop on both
  sides. (Note: `disable-publishing=yes` looks like the more obvious fix but was empirically verified to NOT suppress
  address-record registration on this avahi build — `publish-addresses=no` is the setting that actually works.)

## [0.4.0] - 2026-08-08

### Changed

- Re-publish MQTT birth message per scan, so HA re-sees sensor state after the container restarts without waiting for
  the next status change.

[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/network-tools/v0.5.0-3...HEAD
[0.5.0-3]: https://github.com/akentner/homeassistant-addons/compare/network-tools/v0.4.0...network-tools/v0.5.0-3
[0.4.0]: https://github.com/akentner/homeassistant-addons/tree/network-tools/v0.4.0
