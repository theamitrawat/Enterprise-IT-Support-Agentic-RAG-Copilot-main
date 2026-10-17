#!/bin/sh
set -eu

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p /var/data
    chown appuser:appgroup /var/data
    exec su -s /bin/sh appuser -c 'exec "$@"' docker-entrypoint "$@"
fi

exec "$@"
