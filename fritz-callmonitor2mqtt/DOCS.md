# Home Assistant Add-on: FRITZ!Box Call Monitor to MQTT

Monitor and forward FRITZ!Box call events to MQTT for Home Assistant integration.

## Installation

The installation of this add-on is pretty straightforward and not different in
comparison to installing any other Home Assistant add-on.

1. Click the Home Assistant My button below to open the add-on on your Home Assistant instance.

   [![Open this add-on in your Home Assistant instance.][addon-badge]][addon]

1. Click the "Install" button to install the add-on.
1. Start the "FRITZ!Box Call Monitor to MQTT" add-on.
1. Check the logs of the add-on to see if everything went well.
1. Configure your FRITZ!Box and MQTT settings (see configuration section).

## Configuration

**Note**: _Remember to restart the add-on when the configuration is changed._

Example add-on configuration:

```yaml
fritzbox_host: "192.168.1.1"
fritzbox_port: 1012
pbx_msns: ["12345", "12346", "12347", "12348", "56789"]
pbx_country_code: "49"
pbx_local_area_code: "1234"
mqtt_broker: "core-mosquitto"
mqtt_port: 1883
mqtt_username: "mosquitto"
mqtt_password: "mosquitto"
mqtt_client_id: "fritz-callmonitor2mqtt"
mqtt_topic_prefix: "fritz/callmonitor"
mqtt_qos: 1
mqtt_retain: true
pbx_extensions:
  - number: "**610"
    name: "Kitchen Phone"
    type: "DECT"
  - number: "**600"
    name: "Answering Machine"
    type: "VOICEBOX"
app_log_level: "info"
```

**Note**: _This is just an example, don't copy and paste it! Create your own!_

### Option: `fritzbox_host`

The hostname or IP address of your FRITZ!Box. Default is `fritz.box`.

### Option: `fritzbox_port`

The port of the FRITZ!Box call monitor service. Default is `1012`.

**Note**: _You need to enable the call monitor service on your FRITZ!Box by dialing `#96*5*` on a connected phone._

### Option: `pbx_msns`

A list of Multiple Service Numbers (MSNs) to monitor. Leave empty to monitor all numbers.

Example:

```yaml
pbx_msns: ["12345", "12346", "12347", "12348", "56789"]
```

### Option: `pbx_country_code`

The country code for phone number formatting. Default is `"49"` (Germany).

### Option: `pbx_local_area_code`

The local area code for phone number formatting.

### Option: `pbx_extensions`

Configuration for PBX extensions to provide better call identification.

Example:

```yaml
pbx_extensions:
  # Voicebox Extensions (**600-**609 range)
  - number: "**600"
    name: "Answering Machine 1"
    type: "VOICEBOX"
  - number: "**601"
    name: "Answering Machine 2"
    type: "VOICEBOX"

  # DECT Extensions (**610-**619 range)
  - number: "**610"
    name: "Kitchen Phone"
    type: "DECT"
  - number: "**611"
    name: "Living Room Phone"
    type: "DECT"

  # VoIP Extensions (**620-**629 range)
  - number: "**620"
    name: "Office Phone"
    type: "VOIP"
  - number: "**621"
    name: "Home Office"
    type: "VOIP"
```

#### Extension Types

- `VOICEBOX`: Answering machine extensions
- `DECT`: DECT phone extensions
- `VOIP`: VoIP phone extensions

### Option: `mqtt_broker`

The hostname or IP address of your MQTT broker. If you use the Home Assistant Mosquitto add-on, use `core-mosquitto`.

### Option: `mqtt_port`

The port of your MQTT broker. Default is `1883`.

### Option: `mqtt_username`

The username for your MQTT broker authentication.

### Option: `mqtt_password`

The password for your MQTT broker authentication.

### Option: `mqtt_client_id`

The MQTT client ID. Default is `fritz-callmonitor2mqtt`.

### Option: `mqtt_topic_prefix`

The MQTT topic prefix for all published messages. Default is `fritz/callmonitor`.

### Option: `mqtt_qos`

The MQTT Quality of Service level. Default is `1`.

### Option: `mqtt_retain`

Whether MQTT messages should be retained. Default is `true`.

### Option: `mqtt_keep_alive`

The MQTT keep-alive interval in seconds. Default is `60`.

### Option: `mqtt_connect_timeout`

The MQTT connection timeout in seconds. Default is `30`.

### Option: `app_log_level`

The `app_log_level` option controls the level of log output by the add-on and can
be changed to be more or less verbose, which might be useful when you are
dealing with an unknown issue. Possible values are:

- `trace`: Show every detail, like all called internal functions.
- `debug`: Shows detailed debug information.
- `info`: Normal (usually) interesting events.
- `warning`: Exceptional occurrences that are not errors.
- `error`: Runtime errors that do not require immediate action.
- `fatal`: Something went terribly wrong. Add-on becomes unusable.

Please note that each level automatically includes log messages from a more severe
level, e.g., `debug` also shows `info` messages. By default, the `app_log_level`
is set to `info`, which is the recommended setting unless you are troubleshooting.

### Option: `app_call_history_size`

The number of call events to keep in memory for history. Default is `50`.

### Option: `app_reconnect_delay`

The delay in seconds before attempting to reconnect after a connection loss. Default is `10`.

### Option: `app_health_check_port`

The port for the health check endpoint. Default is `8080`.

### Option: `app_timezone`

The timezone for timestamp formatting. Default is `Europe/Berlin`.

### Option: `database_data_dir`

The directory where call data is stored. Default is `/data`.

## FRITZ!Box Setup

To use this add-on, you need to enable the call monitor service on your FRITZ!Box:

1. Pick up any phone connected to your FRITZ!Box
2. Dial `#96*5*` to enable the call monitor
3. Dial `#96*4*` to disable the call monitor (if needed)

## MQTT Topics

The add-on publishes call events to the following MQTT topics (assuming default prefix `fritz/callmonitor`):

- `fritz/callmonitor/call/incoming` - Incoming call events
- `fritz/callmonitor/call/outgoing` - Outgoing call events
- `fritz/callmonitor/call/connected` - Call connected events
- `fritz/callmonitor/call/disconnected` - Call disconnected events

Each message contains detailed information about the call including:

- Timestamp
- Call ID
- Phone numbers (caller/callee)
- Extension information (if configured)
- Call duration (for disconnect events)

## Environment Variable Mapping

The add-on automatically maps the configuration to environment variables for full
compatibility with the upstream fritz-callmonitor2mqtt application:

- `pbx_msns` → `FRITZ_CALLMONITOR_PBX_MSN` (comma-separated)
- `pbx_extensions[i].number` → `FRITZ_CALLMONITOR_PBX_EXTENSION_i_NUMBER`
- `pbx_extensions[i].name` → `FRITZ_CALLMONITOR_PBX_EXTENSION_i_NAME`
- `pbx_extensions[i].type` → `FRITZ_CALLMONITOR_PBX_EXTENSION_i_TYPE`

## Known issues and limitations

- The FRITZ!Box call monitor must be manually enabled by dialing `#96*5*`
- Only one application can connect to the call monitor at a time
- The add-on currently only supports AMD64 architecture

## Changelog & Releases

This repository keeps a change log using [GitHub's releases][releases] functionality.

Releases are based on [Semantic Versioning][semver], and use the format of
`MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Support

Got questions?

You have several options to get them answered:

- The [Home Assistant Community Forum][forum].
- Join the [Reddit subreddit][reddit] in [/r/homeassistant][reddit]

You could also [open an issue here][issue] on GitHub.

## Authors & contributors

The original setup of this repository is by [Alexander Kentner][akentner].

For a full list of all authors and contributors, check [the contributor's page][contributors].

## License

MIT License

Copyright (c) 2025 Alexander Kentner

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the
Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

[addon-badge]: https://my.home-assistant.io/badges/supervisor_addon.svg
[addon]:
https://my.home-assistant.io/redirect/supervisor_addon/?addon=fritz-callmonitor2mqtt&repository_url=https%3A%2F%2Fgithub.com%2Fakentner%2Fhomeassistant-addons
[contributors]: https://github.com/akentner/homeassistant-addons/graphs/contributors
[forum]: https://community.home-assistant.io/
[issue]: https://github.com/akentner/homeassistant-addons/issues
[reddit]: https://reddit.com/r/homeassistant
[releases]: https://github.com/akentner/homeassistant-addons/releases
[semver]: https://semver.org/spec/v2.0.0.html
[akentner]: https://github.com/akentner
