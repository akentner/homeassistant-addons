ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# No default on purpose: the version comes from build.yaml (args.VERSION) so it cannot go stale here
ARG VERSION
ARG NTFY_ARCH=amd64
# Optional pin; when empty the checksum is taken from the release's checksums.txt
ARG NTFY_SHA256=

# python3 only for the admin GUI; the statically linked ntfy binary comes from the upstream release at build time
RUN apk add --no-cache python3 \
 && curl -fsSL -o /tmp/ntfy.tar.gz "https://github.com/binwiederhier/ntfy/releases/download/v${VERSION}/ntfy_${VERSION}_linux_${NTFY_ARCH}.tar.gz" \
 && curl -fsSL -o /tmp/checksums.txt "https://github.com/binwiederhier/ntfy/releases/download/v${VERSION}/checksums.txt" \
 && if [ -n "${NTFY_SHA256}" ]; then echo "${NTFY_SHA256}  /tmp/ntfy.tar.gz" > /tmp/want.txt; else grep " ntfy_${VERSION}_linux_${NTFY_ARCH}.tar.gz\$" /tmp/checksums.txt | sed "s| .*|  /tmp/ntfy.tar.gz|" > /tmp/want.txt; fi \
 && [ -s /tmp/want.txt ] \
 && sha256sum -c /tmp/want.txt \
 && tar -xzf /tmp/ntfy.tar.gz --strip-components=1 -C /tmp "ntfy_${VERSION}_linux_${NTFY_ARCH}/ntfy" \
 && install -m 0755 /tmp/ntfy /usr/local/bin/ntfy \
 && rm -rf /tmp/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /opt/ntfy-gui
COPY app/ ./app/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
