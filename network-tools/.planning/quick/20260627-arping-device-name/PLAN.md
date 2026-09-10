---
slug: arping-device-name
created: 2026-06-27
status: in-progress
---

# Add device_name to arping_hosts config

Group multiple arping sensors under one HA device via optional `device_name` field.

## Goal

When multiple hosts share the same `device_name`, they appear as sensors on one HA device
instead of creating separate devices per host.

## Changes

### 1. config.yaml
- Add `device_name: str?` to schema `arping_hosts` entries
- Add `device_name` to the example options entry

### 2. arping_scan.py — scan()
- Read `device_name` from host config, pass through in result dict

### 3. arping_scan.py — _build_discovery_payload()
- If `device_name` present: device identifier = `networktools_arping_device_<slugified name>`,
  device name = `device_name`
- Else: keep current behavior (identifier per MAC, name = label)

### 4. Version bump: 0.2.1-0 → 0.2.2-0
