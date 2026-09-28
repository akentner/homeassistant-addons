ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24

FROM $BUILD_FROM

# cups + cups-filters: print server + driverless/IPP-Everywhere filter chain
# avahi + avahi-tools: mDNS/DNS-SD advertisement (the AirPrint fix lives in the
#   generated avahi-daemon.conf, not in package selection)
# dbus: required by avahi-daemon (system bus)
# python3: runs generate_config.py (stdlib json only, no extra packages needed)
# brlaser: CUPS driver for Brother monochrome laser/LED printers
#   (https://github.com/pdewacht/brlaser, packaged in Alpine's community repo,
#   confirmed present as brlaser-6.2.8-r0 for this image's Alpine 3.24 base).
#   Root cause this fixes: raw `socket://` (JetDirect) printers with no real
#   PostScript support -- e.g. a Brother MFC-7460DN -- were registered with
#   `drv:///sample.drv/generic.ppd` (generic PostScript). Sent over a raw
#   socket with no format negotiation, the printer cannot parse the PS bytes
#   and cycles form-feeds, printing a 1-page PDF as endless blank pages.
#   brlaser ships a real PPD generator for these printers instead. Installed
#   unconditionally (small package, no downside for installs that leave the
#   per-printer `driver` option at its default `generic`) -- see
#   `printers[].driver` in cups/config.yaml and cups/DOCS.md.
# cups-pdf: PDF-only virtual print queue backend
#   (https://www.cups-pdf.de/, packaged in Alpine's community repo, confirmed
#   present as cups-pdf-3.0.2-r0 for this image's Alpine 3.24 base). Backs the
#   optional paperless_upload feature (disabled by default, D-07): prints to
#   this queue produce a real PDF file on disk instead of driving a physical
#   device, picked up by upload-worker.py and uploaded to a paperless-ngx
#   instance. apk resolves cups-pdf's own dependencies (incl. ghostscript for
#   its internal PostScript->PDF conversion step) automatically.
# py3-requests: HTTP client used by upload-worker.py for the multipart POST +
#   `Authorization: Token <token>` request to paperless-ngx (confirmed present
#   as py3-requests-2.33.1-r0 for this image's Alpine 3.24 base, D-01).
#   Rejected: hand-rolled stdlib urllib multipart encoding -- requests' files=
#   param carries much lower risk than reimplementing multipart/form-data by
#   hand.
RUN apk add --no-cache \
    cups \
    cups-filters \
    avahi \
    avahi-tools \
    dbus \
    python3 \
    brlaser \
    cups-pdf \
    py3-requests

# Preserve the stock cupsd.conf exactly as shipped by the cups package, before
# anything ever patches it. generate_config.py's build_cupsd_conf() always
# patches FROM this pristine backup at every startup (never from the live
# /etc/cups/cupsd.conf) so restarting the same long-lived container never
# double-patches or drifts from the original template.
RUN cp /etc/cups/cupsd.conf /etc/cups/cupsd.conf.stock

# Same pristine-backup rationale as above, for cups-pdf's own stock conf --
# guarded with `|| true` since the exact stock file's presence depends on the
# cups-pdf apk package's own postinst behavior (build-time verified via this
# phase's own internal/verify-cups-paperless-upload.sh).
RUN cp /etc/cups/cups-pdf.conf /etc/cups/cups-pdf.conf.stock || true

# Empirically discovered while verifying this phase (internal/verify-cups-
# paperless-upload.sh): Alpine's cups-pdf-3.0.2-r0 package ships its backend
# at 0755 (world-executable). CUPS decides whether to run a backend as root
# purely from its file permissions -- a backend that is executable by
# "other" is run as the unprivileged filter user (lp), never root. cups-pdf's
# own code explicitly refuses to run unless invoked as root ("CUPS-PDF cannot
# be called without root privileges!", confirmed live in
# /var/log/cups/error_log), so every print job to the queue silently no-ops
# without ever producing a PDF. Debian's packaging ships the same binary at
# 0700 for exactly this reason; Alpine's does not. chmod 700 here makes CUPS
# recognize it as root-required and run it accordingly.
RUN chmod 700 /usr/lib/cups/backend/cups-pdf

COPY run.sh generate_config.py print-history-poller.py upload-worker.py /

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
