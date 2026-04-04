# Meridian Claude Max Proxy — Configuration

## Options

### `log_level` (required)

Controls proxy verbosity.

| Value     | Description                   |
| --------- | ----------------------------- |
| `debug`   | Verbose output for debugging  |
| `info`    | Standard operational messages |
| `warning` | Warnings and errors only      |
| `error`   | Errors only                   |

Default: `info`

### `port` (required)

TCP port the proxy listens on. Must match the port you use in client base URLs.

Default: `3456`

Change this only if port 3456 is already in use on your network.

## Example Configuration

```yaml
log_level: "info"
port: 3456
```

## Notes

- Credentials are stored at `/data/.claude` and persist across add-on restarts.
- Re-authentication is only required if the OAuth token expires or is revoked.
- The proxy accepts connections from any interface (LAN, Tailscale) on the configured port.
