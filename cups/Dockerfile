ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24

FROM $BUILD_FROM

# cups + cups-filters: print server + driverless/IPP-Everywhere filter chain
# avahi + avahi-tools: mDNS/DNS-SD advertisement (the AirPrint fix lives in the
#   generated avahi-daemon.conf, not in package selection)
# dbus: required by avahi-daemon (system bus)
# python3: runs generate_config.py (stdlib json only, no extra packages needed)
RUN apk add --no-cache \
    cups \
    cups-filters \
    avahi \
    avahi-tools \
    dbus \
    python3

# Preserve the stock cupsd.conf exactly as shipped by the cups package, before
# anything ever patches it. generate_config.py's build_cupsd_conf() always
# patches FROM this pristine backup at every startup (never from the live
# /etc/cups/cupsd.conf) so restarting the same long-lived container never
# double-patches or drifts from the original template.
RUN cp /etc/cups/cupsd.conf /etc/cups/cupsd.conf.stock

COPY run.sh generate_config.py /

# CUPS restricts admin operations (lpadmin) to members of the SystemGroup
# (lpadmin by default per /etc/cups/cups-files.conf) -- root is not a member
# of that group by default even when running the whole container as root, so
# lpadmin would fail with "Forbidden" without this.
RUN addgroup root lpadmin \
    && chmod +x /run.sh

EXPOSE 631/tcp 631/udp
CMD ["/run.sh"]

# ### LABELS
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="akentner (https://github.com/akentner)" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Add-ons" \
    org.opencontainers.image.authors="akentner (https://github.com/akentner)" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/akentner" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
