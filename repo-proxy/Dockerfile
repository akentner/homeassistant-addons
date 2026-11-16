ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# Scaffold only: the proxy service is not implemented yet (see GOAL.md)
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
