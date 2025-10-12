# Home Assistant Add-on: Fritz!Box Call Monitor to MQTT

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

[![Discord][discord-shield]][discord] [![Community Forum][forum-shield]][forum]

Monitor and forward Fritz!Box call events to MQTT.

## About

This add-on connects to your Fritz!Box call monitor and forwards all call events
(incoming, outgoing, connected, disconnected) to an MQTT broker. This allows you
to integrate Fritz!Box telephony events into Home Assistant automations and
notifications.

The add-on is based on the [fritz-callmonitor2mqtt][fritz-callmonitor2mqtt] application and provides:

- Real-time call monitoring from Fritz!Box
- MQTT integration with Home Assistant
- Support for multiple MSNs (Multiple Service Numbers)
- Extension configuration for better call identification
- Comprehensive logging and debugging options

![Fritz!Box Call Monitor Preview][screenshot]
mqtt_qos: 1
mqtt_retain: true
mqtt_keep_alive: 60
mqtt_connect_timeout: 30

````yaml

## Advanced Configuration

### PBX Settings

```yaml
# Multiple Service Numbers (MSNs)
pbx_msns: ["12345", "12346", "12347", "12348", "56789"]
pbx_country_code: "49"
pbx_local_area_code: "1234"
````

### Extensions Configuration

The add-on supports configuring extensions for better call identification:

```yaml
pbx_extensions:
  # Voicebox Extensions (**600-**609 range)
  - number: "**600"
    name: "AB 22"
    type: "VOICEBOX"
  - number: "**601"
    name: "AB 24"
    type: "VOICEBOX"
  - number: "**602"
    name: "AB Firmen"
    type: "VOICEBOX"

  # DECT Extensions (**610-**619 range)
  - number: "**610"
    name: "EG 24"
    type: "DECT"
  - number: "**611"
    name: "OG 24"
    type: "DECT"
  - number: "**612"
    name: "K 24"
    type: "DECT"
  - number: "**613"
    name: "EG 22"
    type: "DECT"
  - number: "**614"
    name: "OG 22"
    type: "DECT"
  - number: "**615"
    name: "K 22"
    type: "DECT"

  # VoIP Extensions (**620-**629 range)
  - number: "**620"
    name: "DG 24"
    type: "VOIP"
  - number: "**621"
    name: "T 22 (990134)"
    type: "VOIP"
  - number: "**623"
    name: "T 22 (3698237)"
    type: "VOIP"
```

### Extension Types

- `VOICEBOX`: Answering machine extensions
- `DECT`: DECT phone extensions
- `VOIP`: VoIP phone extensions

### Application Settings

```yaml
app_log_level: "info" # debug, info, warning, error, critical
app_call_history_size: 50
app_reconnect_delay: 10
app_health_check_port: 8080
app_timezone: "Europe/Berlin"
database_data_dir: "/data"
```

## Complete Example Configuration

```yaml
fritzbox_host: "192.168.1.1"
fritzbox_port: 1012

pbx_msns: ["12345", "12346", "12347", "12348", "56789"]
pbx_country_code: "49"
pbx_local_area_code: "1234"

mqtt_broker: "192.168.1.10"
mqtt_port: 1883
mqtt_username: ""
mqtt_password: ""
mqtt_client_id: "fritz-callmonitor2mqtt"
mqtt_topic_prefix: "fritz/callmonitor"
mqtt_qos: 1
mqtt_retain: true
mqtt_keep_alive: 60
mqtt_connect_timeout: 30

pbx_extensions:
  - number: "**600"
    name: "AB 22"
    type: "VOICEBOX"
  - number: "**610"
    name: "EG 24"
    type: "DECT"
  - number: "**620"
    name: "DG 24"
    type: "VOIP"

app_log_level: "debug"
app_call_history_size: 50
app_reconnect_delay: 5
app_health_check_port: 8080
app_timezone: "Europe/Berlin"
database_data_dir: "/data"
```

[discord-shield]: https://img.shields.io/discord/478094546522079232.svg
[discord]: https://discord.me/hassioaddons
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg
[forum]: https://community.home-assistant.io/
[maintenance-shield]: https://img.shields.io/maintenance/yes/2025.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-production-green.svg
[release-shield]: https://img.shields.io/badge/version-v1.3.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.3.1
[screenshot]: https://github.com/akentner/homeassistant-addons/raw/main/fritz-callmonitor2mqtt/images/screenshot.png
[fritz-callmonitor2mqtt]: https://github.com/akentner/fritz-callmonitor2mqtt
