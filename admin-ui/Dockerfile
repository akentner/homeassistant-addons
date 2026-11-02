ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

# python3 only: the server skeleton is stdlib-only and the browser lib is vendored, so nothing is downloaded at build time
RUN apk add --no-cache python3

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /opt/admin-ui
COPY app/ ./app/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
