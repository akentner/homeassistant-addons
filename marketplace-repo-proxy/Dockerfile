ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# git-daemon carries git-http-backend on Alpine; python3 runs init, sync, access store and CLI
RUN apk add --no-cache git git-daemon lighttpd python3 \
    && test -x /usr/libexec/git-core/git-http-backend \
    && mkdir -p /var/empty

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/marketplace-repo-proxy
COPY app/ ./app/
COPY rootfs/ /
# run.sh is the body of the s6 oneshot "init"; s6-overlay (PID 1) supervises the lighttpd and sync longruns
COPY run.sh /etc/s6-overlay/s6-rc.d/init/run
