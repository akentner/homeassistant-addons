ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

RUN apk add --no-cache openssh-client jq busybox-extras mosquitto-clients

COPY run.sh monitor.sh status.sh mqtt.sh /
COPY status.cgi /www/cgi-bin/status
COPY metrics.cgi /www/cgi-bin/metrics
RUN chmod +x /run.sh /monitor.sh /status.sh /mqtt.sh /www/cgi-bin/status /www/cgi-bin/metrics

CMD ["/run.sh"]
