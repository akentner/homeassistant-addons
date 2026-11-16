#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# Scaffold: the proxy service is not implemented yet (see GOAL.md); keep the container alive for the store.
bashio::log.level "$(bashio::config 'log_level')"
bashio::log.warning "Marketplace Repo Proxy is a scaffold, no service is started yet"
exec sleep infinity
