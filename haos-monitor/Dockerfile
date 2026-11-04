ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# python3 only for the GUI server: its skeleton is stdlib-only and the browser lib is vendored, nothing is downloaded
RUN apk add --no-cache openssh-client jq busybox-extras mosquitto-clients python3

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/haos-monitor-gui

# The GUI (Python server on the admin-ui skeleton plus the Preact page) listens on the internal port 8100 behind the
# ingress gate; run.sh starts it next to busybox httpd. No WORKDIR: the legacy scripts keep their working directory.
COPY app/ /opt/haos-monitor-gui/app/
# served by the skeleton at /icon (static root); the store reads icon.png/logo.png from the add-on directory
COPY icon.png /opt/haos-monitor-gui/app/web/static/icon.png
COPY run.sh monitor.sh status.sh mqtt.sh /
COPY httpd.conf /etc/httpd.conf
COPY status.cgi /www/cgi-bin/status
COPY metrics.cgi /www/cgi-bin/metrics
COPY hosts.cgi /www/api/hosts.json
COPY incidents.cgi /www/api/incidents.json
# busybox httpd on 8099 serves the machine endpoints only (the page now comes from the GUI server);
# /api/* are the clean URLs of the /cgi-bin/* endpoints (kept for existing Gatus/Prometheus configs)
RUN chmod +x /run.sh /monitor.sh /status.sh /mqtt.sh /www/cgi-bin/status /www/cgi-bin/metrics \
    /www/api/hosts.json /www/api/incidents.json \
 && ln -s ../cgi-bin/status /www/api/status.json \
 && ln -s ../cgi-bin/metrics /www/api/metrics.txt

CMD ["/run.sh"]
