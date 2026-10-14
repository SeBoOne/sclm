# SCLM — Star Citizen Loot Manager

Star Citizen Loot-Verlosungs-Tool für Gruppen.

## Docker (empfohlen)

**Voraussetzung:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installieren.

### Starten

```bash
docker compose up -d
```

Die App läuft dann auf **http://localhost:5000**

Die Datenbank wird im Docker Volume `sc_loot_data` gespeichert.

### Admin-Secret herausfinden

**Methode 1 — Helper-Script:**
```bash
bash get-secret.sh
```

**Methode 2 — Container-Logs:**
```bash
docker compose logs sc-loot-raffle | grep "Admin-Panel"
```

**Methode 3 — Direkt im Container:**
```bash
docker exec sc-loot-raffle-sc-loot-raffle-1 python3 -c "
import sqlite3; con=sqlite3.connect('/data/data.db')
print(con.execute(\"SELECT value FROM config WHERE key='admin_secret'\").fetchone()[0])
"
```

**Methode 4 — Localhost API** (nur wenn Server läuft):
```
http://localhost:5000/api/admin/secret-hint
```
⚠ Dieser Endpunkt ist nur von localhost erreichbar, nicht von außen.

### Stoppen

```bash
docker compose down
```

### Updates einspielen

Neue Dateien in den Ordner kopieren, dann:

```bash
docker compose up -d --build
```

---

## Lokaler Start (ohne Docker)

**Voraussetzung:** Python 3.8+ installiert.

```bash
pip install flask flask-cors
python server.py
```

Das Admin-Secret wird beim Start in der Konsole angezeigt.

---

## Port ändern

In `docker-compose.yml` die Zeile `"5000:5000"` auf z.B. `"8080:5000"` ändern.

## Reverse Proxy / HTTPS

Nginx Proxy Manager oder Traefik auf `localhost:5000` (bzw. den gewählten Port) zeigen lassen.

---

## Rechtliches

Dies ist eine inoffizielle Star-Citizen-Fan-Website, nicht verbunden mit der Cloud Imperium-Gruppe. SCLM ist ein nicht-kommerzielles Community-Tool und folgt der [CIG Fan Content Policy](https://support.robertsspaceindustries.com/hc/en-us/articles/360006895793-Star-Citizen-Fankit-and-Fandom-FAQ).

## Lizenz

MIT — siehe [LICENSE](LICENSE)

## Deployment aus Registry (empfohlen für Server)

Das Image wird bei jedem Push auf `main` automatisch von GitHub Actions gebaut und nach GHCR gepusht.

```yaml
services:
  sc-loot-raffle:
    image: ghcr.io/seboone/sclm:latest
    ports:
      - "5000:5000"
    volumes:
      - sc_loot_data:/data
    restart: unless-stopped

volumes:
  sc_loot_data:
```

Updates einspielen:

```bash
docker compose pull && docker compose up -d
```

> Wichtig: Beim Umstieg von `build:` auf `image:` den **gleichen Volume-Namen** behalten, sonst ist die Datenbank „weg" (sie liegt dann im alten Volume).
