#!/bin/bash
# Gibt das Admin-Secret des laufenden Containers aus
# Verwendung: bash get-secret.sh [container-name]

CONTAINER=${1:-sc-loot-raffle}

echo "=== SC Loot Raffle — Admin Secret ==="
echo ""

# Method 1: aus den Container-Logs
echo "Aus Container-Logs:"
docker logs "$CONTAINER" 2>/dev/null | grep "Admin-Panel\|admin_secret\|Secret" | tail -5

echo ""
echo "Per API (innerhalb des Containers):"
docker exec "$CONTAINER" python3 -c "
import sqlite3, os
db = os.environ.get('DATA_DIR', '/app') + '/data.db'
try:
    con = sqlite3.connect(db)
    sec = con.execute(\"SELECT value FROM config WHERE key='admin_secret'\").fetchone()
    if sec:
        print(f'  Admin-Secret: {sec[0]}')
        print(f'  Admin-URL:    http://localhost:5000/#admin?secret={sec[0]}')
    else:
        print('  Noch nicht initialisiert — Container starten.')
except Exception as e:
    print(f'  Fehler: {e}')
" 2>/dev/null || echo "  Container nicht gefunden oder läuft nicht."
