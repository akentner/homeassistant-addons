# Repo Proxy

Scaffold of an add-on that serves private GitHub repositories to the Home Assistant store. The goal and design questions
are in [GOAL.md](GOAL.md).

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml` and no
auto-update. Its image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA
base image only, 3-file version sync via `make update-version`, and a local `docker build` before every commit.

## Options

| Option      | Type                          | Default | Description                  |
| ----------- | ----------------------------- | ------- | ---------------------------- |
| `log_level` | `debug\|info\|warning\|error` | `info`  | Verbosity of the add-on log. |
