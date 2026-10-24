ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

RUN apk add --no-cache openssh-client jq busybox-extras mosquitto-clients

COPY run.sh monitor.sh status.sh mqtt.sh /
COPY httpd.conf /etc/httpd.conf
COPY index.html /www/index.html
COPY status.cgi /www/cgi-bin/status
COPY metrics.cgi /www/cgi-bin/metrics
COPY hosts.cgi /www/api/hosts.json
COPY incidents.cgi /www/api/incidents.json
# /api/* are the clean URLs of the /cgi-bin/* endpoints (kept for existing Gatus/Prometheus configs)
RUN chmod +x /run.sh /monitor.sh /status.sh /mqtt.sh /www/cgi-bin/status /www/cgi-bin/metrics \
    /www/api/hosts.json /www/api/incidents.json \
 && ln -s ../cgi-bin/status /www/api/status.json \
 && ln -s ../cgi-bin/metrics /www/api/metrics.txt

CMD ["/run.sh"]
