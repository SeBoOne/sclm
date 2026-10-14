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
docker compose logs sc-loot-raffle | grep "ADMIN SECRET"
```
Seit Härtungsrunde 2 (N2) wird das Secret im Log standardmäßig **maskiert**
(nur die ersten 4 Zeichen + Länge). Das vollständige Secret wird nur mit
`SHOW_SECRET_ON_START=1` (als ENV im Container) ausgegeben.

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
⚠ Dieser Endpunkt ist nur von **localhost (127.0.0.1/::1)** oder explizit erlaubten
Proxies (`TRUSTED_PROXIES`=kommagetrennte IPs, als ENV) erreichbar — nicht von außen.
Der Endpunkt lässt sich vollständig abschalten, indem man `DISABLE_SECRET_HINT=1` setzt.

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

Pflichtdisclaimer (englischer Originalwortlaut, identisch mit der About-Seite):

> This is an unofficial Star Citizen fansite, not affiliated with the Cloud Imperium group of companies.
> All content on this site not authored by its host or users are property of their respective owners.
> Star Citizen®, Roberts Space Industries® and Cloud Imperium® are registered trademarks of Cloud Imperium Rights LLC.

## Lizenz

MIT — siehe [LICENSE](LICENSE)

**Hinweis auf Fremd-Assets:** Die Dateien `static/sc-fan-logo.png` (CIG-Fankit) und `static/uex-badge.png` (UEX Corp) sind Eigentum der jeweiligen Rechteinhaber (Cloud Imperium Rights LLC bzw. UEX Corp) und stehen **nicht** unter der MIT-Lizenz. Sie werden ausschließlich im Rahmen der nicht-kommerziellen CIG Fan Content Policy bzw. der UEX-Nutzungsbedingungen verwendet.

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
