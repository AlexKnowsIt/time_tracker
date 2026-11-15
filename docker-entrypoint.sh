#!/bin/sh
# Server: Rechte auf /data korrigieren und als Nutzer "app" weiterlaufen.
# Home-Assistant-Add-on (erkennbar an /data/options.json): /data gehört root, daher als root.
set -e
if [ "$(id -u)" = 0 ] && [ ! -f /data/options.json ]; then
    chown app:app /data
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
