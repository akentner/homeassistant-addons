ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

ARG BW_CLI_VERSION=2026.10.0

# nodejs/npm only for the Bitwarden CLI; sops + age for the SOPS provider; py3-yaml for the YAML round trip
RUN apk add --no-cache nodejs npm python3 py3-yaml sops age \
 && npm install -g --omit=dev --no-fund --no-audit "@bitwarden/cli@${BW_CLI_VERSION}" \
 && npm cache clean --force \
 && rm -rf /root/.npm /tmp/*

COPY app/ /opt/secrets-sync/app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

WORKDIR /opt/secrets-sync
CMD ["/run.sh"]
