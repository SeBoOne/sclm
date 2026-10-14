#!/bin/sh
# Entrypoint: muss als root starten (USER root im Dockerfile).
# 1) /data (Volume) für den app-User schreibbar machen — bestehende Volumes sind
#    root-owned (aus Zeiten vor der Non-root-Härtung), sonst: readonly database.
# 2) Danach auf den unprivilegierten app-User abgeben und gunicorn starten.
set -e
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /data
    exec gosu app:app "$@"
fi
exec "$@"
