#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# FritzBox
FRITZ_CALLMONITOR_FRITZBOX_HOST=$(bashio::config 'fritzbox_host')
FRITZ_CALLMONITOR_FRITZBOX_PORT=$(bashio::config 'fritzbox_port')
export FRITZ_CALLMONITOR_FRITZBOX_HOST
export FRITZ_CALLMONITOR_FRITZBOX_PORT

# PBX
FRITZ_CALLMONITOR_PBX_MSN=$(bashio::config 'pbx_msns' | jq -R -s -c 'split("\n") | map(select(length > 0)) | join(",")')
FRITZ_CALLMONITOR_PBX_COUNTRY_CODE=$(bashio::config 'pbx_country_code')
FRITZ_CALLMONITOR_PBX_LOCAL_AREA_CODE=$(bashio::config 'pbx_local_area_code')
export FRITZ_CALLMONITOR_PBX_MSN
export FRITZ_CALLMONITOR_PBX_COUNTRY_CODE
export FRITZ_CALLMONITOR_PBX_LOCAL_AREA_CODE

# MQTT
FRITZ_CALLMONITOR_MQTT_BROKER=$(bashio::config 'mqtt_broker')
FRITZ_CALLMONITOR_MQTT_PORT=$(bashio::config 'mqtt_port')
FRITZ_CALLMONITOR_MQTT_USERNAME=$(bashio::config 'mqtt_username')
FRITZ_CALLMONITOR_MQTT_PASSWORD=$(bashio::config 'mqtt_password')
FRITZ_CALLMONITOR_MQTT_CLIENT_ID=$(bashio::config 'mqtt_client_id')
FRITZ_CALLMONITOR_MQTT_TOPIC_PREFIX=$(bashio::config 'mqtt_topic_prefix')
FRITZ_CALLMONITOR_MQTT_QOS=$(bashio::config 'mqtt_qos')
FRITZ_CALLMONITOR_MQTT_RETAIN=$(bashio::config 'mqtt_retain')
FRITZ_CALLMONITOR_MQTT_KEEP_ALIVE=$(bashio::config 'mqtt_keep_alive')
FRITZ_CALLMONITOR_MQTT_CONNECT_TIMEOUT=$(bashio::config 'mqtt_connect_timeout')
export FRITZ_CALLMONITOR_MQTT_BROKER
export FRITZ_CALLMONITOR_MQTT_PORT
export FRITZ_CALLMONITOR_MQTT_USERNAME
export FRITZ_CALLMONITOR_MQTT_PASSWORD
export FRITZ_CALLMONITOR_MQTT_CLIENT_ID
export FRITZ_CALLMONITOR_MQTT_TOPIC_PREFIX
export FRITZ_CALLMONITOR_MQTT_QOS
export FRITZ_CALLMONITOR_MQTT_RETAIN
export FRITZ_CALLMONITOR_MQTT_KEEP_ALIVE
export FRITZ_CALLMONITOR_MQTT_CONNECT_TIMEOUT

# App
FRITZ_CALLMONITOR_APP_LOG_LEVEL=$(bashio::config 'app_log_level')
FRITZ_CALLMONITOR_APP_CALL_HISTORY_SIZE=$(bashio::config 'app_call_history_size')
FRITZ_CALLMONITOR_APP_RECONNECT_DELAY=$(bashio::config 'app_reconnect_delay')
FRITZ_CALLMONITOR_APP_HEALTH_CHECK_PORT=$(bashio::config 'app_health_check_port')
FRITZ_CALLMONITOR_APP_TIMEZONE=$(bashio::config 'app_timezone')
export FRITZ_CALLMONITOR_APP_LOG_LEVEL
export FRITZ_CALLMONITOR_APP_CALL_HISTORY_SIZE
export FRITZ_CALLMONITOR_APP_RECONNECT_DELAY
export FRITZ_CALLMONITOR_APP_HEALTH_CHECK_PORT
export FRITZ_CALLMONITOR_APP_TIMEZONE

bashio::log.info "Starte fritz-callmonitor2mqtt..."

# Debug: Zeige alle Umgebungsvariablen
if [[ "${FRITZ_CALLMONITOR_APP_LOG_LEVEL}" == "debug" ]]; then
    bashio::log.debug "Umgebungsvariablen:"
    env | grep FRITZ_CALLMONITOR_ | sort
fi

# Starte die Go-Anwendung
exec /usr/local/bin/fritz-callmonitor2mqtt
