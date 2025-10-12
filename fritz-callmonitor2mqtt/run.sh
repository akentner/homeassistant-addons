#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# FritzBox
FRITZ_CALLMONITOR_FRITZBOX_HOST=$(bashio::config 'fritzbox_host')
FRITZ_CALLMONITOR_FRITZBOX_PORT=$(bashio::config 'fritzbox_port')
export FRITZ_CALLMONITOR_FRITZBOX_HOST
export FRITZ_CALLMONITOR_FRITZBOX_PORT

# PBX
# Handle MSNs - support both array and string format
# First try to get the count of MSN entries
MSN_COUNT=$(bashio::config 'pbx_msns | length' 2>/dev/null || echo "0")

if [[ "$MSN_COUNT" -gt 0 ]]; then
    # Build MSN list from array elements
    MSN_LIST=""
    for ((i=0; i<MSN_COUNT; i++)); do
        MSN_ENTRY=$(bashio::config "pbx_msns[$i]" 2>/dev/null || echo "")
        if [[ -n "$MSN_ENTRY" ]]; then
            if [[ -z "$MSN_LIST" ]]; then
                MSN_LIST="$MSN_ENTRY"
            else
                MSN_LIST="$MSN_LIST,$MSN_ENTRY"
            fi
        fi
    done
    FRITZ_CALLMONITOR_PBX_MSN="$MSN_LIST"
else
    # Fallback: Try to get as raw config and handle different formats
    MSN_CONFIG=$(bashio::config 'pbx_msns' 2>/dev/null || echo "")
    if [[ -n "$MSN_CONFIG" ]] && [[ "$MSN_CONFIG" != "null" ]] && [[ "$MSN_CONFIG" != "[]" ]]; then
        # Check if it's a JSON array
        if echo "$MSN_CONFIG" | jq -e '. | type == "array"' >/dev/null 2>&1; then
            # It's an array - join with commas
            FRITZ_CALLMONITOR_PBX_MSN=$(echo "$MSN_CONFIG" | jq -r '. | join(",")')
        else
            # Handle newline-separated string format from bashio
            if echo "$MSN_CONFIG" | grep -q $'\n'; then
                # Convert newlines to commas and remove empty lines
                FRITZ_CALLMONITOR_PBX_MSN=$(echo "$MSN_CONFIG" | tr '\n' ',' | sed 's/,,\+/,/g' | sed 's/^,\|,$//g')
            else
                # It's a single string - use as is
                FRITZ_CALLMONITOR_PBX_MSN="$MSN_CONFIG"
            fi
        fi
    else
        FRITZ_CALLMONITOR_PBX_MSN=""
    fi
fi

FRITZ_CALLMONITOR_PBX_COUNTRY_CODE=$(bashio::config 'pbx_country_code')
FRITZ_CALLMONITOR_PBX_LOCAL_AREA_CODE=$(bashio::config 'pbx_local_area_code')

# Debug MSN processing
if [[ "${FRITZ_CALLMONITOR_APP_LOG_LEVEL}" == "debug" ]]; then
    bashio::log.debug "MSN Count: '$MSN_COUNT'"
    if [[ -n "${MSN_CONFIG:-}" ]]; then
        bashio::log.debug "MSN Config Raw: '$MSN_CONFIG'"
    fi
    bashio::log.debug "MSN Final: '$FRITZ_CALLMONITOR_PBX_MSN'"
fi

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

# Database
FRITZ_CALLMONITOR_DATABASE_DATA_DIR=$(bashio::config 'database_data_dir')
export FRITZ_CALLMONITOR_DATABASE_DATA_DIR

# Extensions Configuration
# Process pbx_extensions array from config
PBX_EXTENSIONS=$(bashio::config 'pbx_extensions')
if [[ -n "$PBX_EXTENSIONS" ]] && [[ "$PBX_EXTENSIONS" != "null" ]]; then
    EXTENSION_COUNT=$(echo "$PBX_EXTENSIONS" | jq '. | length')

    for ((i=0; i<EXTENSION_COUNT; i++)); do
        EXTENSION_NUMBER=$(echo "$PBX_EXTENSIONS" | jq -r ".[$i].number // empty")
        EXTENSION_NAME=$(echo "$PBX_EXTENSIONS" | jq -r ".[$i].name // empty")
        EXTENSION_TYPE=$(echo "$PBX_EXTENSIONS" | jq -r ".[$i].type // empty")

        if [[ -n "$EXTENSION_NUMBER" ]] && [[ -n "$EXTENSION_NAME" ]]; then
            export "FRITZ_CALLMONITOR_PBX_EXTENSION_${i}_NUMBER=$EXTENSION_NUMBER"
            export "FRITZ_CALLMONITOR_PBX_EXTENSION_${i}_NAME=$EXTENSION_NAME"

            if [[ -n "$EXTENSION_TYPE" ]] && [[ "$EXTENSION_TYPE" != "null" ]]; then
                export "FRITZ_CALLMONITOR_PBX_EXTENSION_${i}_TYPE=$EXTENSION_TYPE"
            fi

            bashio::log.debug "Extension $i: $EXTENSION_NUMBER -> $EXTENSION_NAME ($EXTENSION_TYPE)"
        fi
    done
fi

bashio::log.info "Starte fritz-callmonitor2mqtt..."

# Debug: Zeige alle Umgebungsvariablen
if [[ "${FRITZ_CALLMONITOR_APP_LOG_LEVEL}" == "debug" ]]; then
    bashio::log.debug "Umgebungsvariablen:"
    env | grep FRITZ_CALLMONITOR_ | sort
fi

# Starte die Go-Anwendung
exec /usr/local/bin/fritz-callmonitor2mqtt
