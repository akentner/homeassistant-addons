ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

ARG BW_CLI_VERSION=2026.10.1

# nodejs/npm only for the Bitwarden CLI; sops + age for the SOPS provider; git + ssh for the SOPS git source; py3-yaml for the YAML round trip; py3-jinja2 for synthetic keys
RUN apk add --no-cache nodejs npm python3 py3-yaml py3-jinja2 sops age git openssh-client \
 && npm install -g --omit=dev --no-fund --no-audit "@bitwarden/cli@${BW_CLI_VERSION}" \
 && npm cache clean --force \
 && rm -rf /root/.npm /tmp/*

COPY app/ /opt/secrets-sync/app/
COPY run.sh /run.sh
# git-askpass hands the https token from env to git (never argv)
RUN chmod +x /run.sh /opt/secrets-sync/app/bin/git-askpass

WORKDIR /opt/secrets-sync
CMD ["/run.sh"]
