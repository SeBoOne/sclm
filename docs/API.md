# SCLM — API-Referenz (Standard-Version v5.0)

Vollständige Referenz für Menschen und KI-Agenten, die eigene Clients, Bots,
Dashboard-Integrationen oder Automationen auf SCLM bauen wollen.

Alle Beispiele gegen `https://sclm.site` (bzw. deine eigene Instanz).
Alle Anfragen/Antworten sind JSON (`Content-Type: application/json`), außer `/setup`.

---

## 0. Grundregeln

- **Input-Validierung (Härtung 3A, ab v5.0+):**
  - **Textfelder** (`name`, `type`, `grade`, `size`, …): JSON-Zeichenkette oder `null`.
    Zahlen/Booleans/Listen/Objekte → `400 {"error":"<feld> muss eine Zeichenkette sein"}`.
  - **Numerische Felder** (`qty`, `scu`, `delta`, `sale_revenue`, `total_revenue`, `max_wishes`):
    JSON-Zahl **oder** numerische Saite (`"3"` → 3). Booleans/nicht-numerische Saiten/Listen →
    `400 {"error":"<feld> muss eine Zahl sein"}`. NaN/Infinity (auch als JSON-Literal) →
    `400 {"error":"<feld> darf nicht NaN oder unendlich sein"}`.
  - **Ganzzahl-Felder** (3C: `qty`, Loot-`delta`, `max_wishes`): nicht-ganzzahlige Zahlen
    werden abgelehnt — `1.5` → `400 {"error":"<feld> muss eine Ganzzahl sein"}`.
    Ganzzahlige Fließkommazahlen und Saiten (`3.0`, `"3"`, `"3.0"`) werden akzeptiert.
    Rein numerische Felder (`scu`, `sale_revenue`, `total_revenue`, Waren-`delta`) bleiben
    Dezimalzahlen.
  - **Obergrenzen** (beim Speichern geprüft, Konstanten am Anfang von `server.py`):
    `qty` 1–10000 (3C: von 100000 gesenkt) · `delta` ±100000 · `scu` 0–1.000.000.000 ·
    `sale_revenue`/`total_revenue` 0–1.000.000.000.000 → Verstoß `400 {"error":"<feld> muss
    zwischen <lo> und <hi> sein"}`. Zusätzlich `RAFFLE_MAX_TOTAL` = 50000: Ziehungen werden
    vor der Instanz-Expansion abgelehnt (§10).
  - **Altbestand (korrumpierte Altwerte):** numerische Werte, die sich nicht sicher
    serialisieren lassen (z. B. `qty` = 1e20 oder `Infinity` aus Daten vor der Härtung),
    erscheinen als `null` statt als Zahl — bei `qty`, `scu`, `sale_revenue` in Detail-Payloads
    und bei `loot_count`, `commodity_scu`, `commodity_revenue` in `GET /api/sessions`
    (auch `loot_count`/`participant_count` der Liste sind geschützt; solche Werte zählen bei
    Summen und Ziehungen wie nicht vorhanden).
  - **JSON-Fehler unter `/api/*`:** 400/404/405/415/500 antworten jetzt JSON `{"error":"…"}`
    (415 = fehlender `Content-Type: application/json`; 500 generisch, ohne Traceback).
    Für Seiten-URLs bleibt HTML.
- **Kein CORS**: Die API ist auf dieselbe Origin beschränkt (Browser-Clients von sclm.site).
  Server-zu-Server (Bots, Tools, Home Assistant, OpenDeck) ist problemlos möglich.
- **Keine Webhooks / kein WebSocket**: Statusänderungen werden per Polling gelesen
  (siehe §10 Polling-Empfehlungen).
- **Keine Cookies / keine Sessions auf Serverseite**: Jede Anfrage muss ihre
  Berechtigung selbst mitbringen. Der Server ist zustandslos bezüglich Login.
- **`sid` vs `code`** — wichtigste Stolperfalle:
  - `sid` = Session-**ID** (8 Zeichen, `a-z0-9`), aus `POST /api/session/create` oder `GET /api/sessions`.
    Pfadparameter `<sid>` erwartet **immer die ID**.
  - `code` = 6-stelliger **Code** (`A-Z0-9`): `admin_code` oder `join_code`.
    Nur `GET /api/session/<code>` akzeptiert einen Code im Pfad.
    Ein `sid` im GET-Pfad → `404 {"error":"sid im Pfad nicht erlaubt: GET /api/session/<admin_code oder join_code> verwenden"}`.
- **ID-Längen**: Session-/Teilnehmer-/Loot-/Ergebnis-IDs sind 8 Zeichen (`a-z0-9`).
  Teilnehmer-Keys (`pcode`) sind URL-sichere Secrets (~22 Zeichen). Admin-Secret ist 32 Hex-Zeichen.

---

## 1. Authentifizierung — drei Berechtigungsebenen

| Ebene | Wert | Wirkt | Transport |
|---|---|---|---|
| **Site-Admin** | `admin_secret` (32 Hex) | global, alle Sessions, Katalog | Header `X-SCLM-Secret` |
| **Session-Admin** | `admin_code` (6) | eine Session, volle Rechte | Header `X-SCLM-Code` |
| **Teilnehmer** | `join_code` (6) | eine Session, nur eigene Daten | Header `X-SCLM-Code` (der Code kommt nicht mehr aus `GET /api/sessions`) |
| **Eigentümerschaft** | `pcode` (~22 Zeichen) | ein Teilnehmer-Datensatz | **nur JSON-Body** `{"pcode": "…"}` |

### Übergabe: Header bevorzugt

Der Server liest Credentials in dieser Reihenfolge (Fallback-Kette):

1. Header `X-SCLM-Code` / `X-SCLM-Secret` ← **empfohlen**
2. Query-Parameter `?code=` (Legacy; für `secret` gilt die 3C-Einschränkung unten)
3. JSON-Feld `code` / `secret` im Body (Legacy; für `secret` gilt die 3C-Einschränkung unten)

**3C — Secret-Fallback nur noch für Body-Methoden:** `?secret=` und das Body-Feld
`secret` akzeptiert der Server nur noch bei `POST`/`PUT`/`PATCH`. Bei `GET`, `HEAD` und
`DELETE` wird das `admin_secret` **ausschließlich** aus dem Header `X-SCLM-Secret` gelesen
— Query-Zeilen landen in jedem Access-Log und das Secret soll dort nicht auftauchen.
Betrifft alle Endpunkte, die `admin_secret` prüfen (`GET /api/sessions`,
`GET /api/admin/data`, `DELETE /api/admin/...` u. a.). Codes (`X-SCLM-Code`, `?code=`,
Body `code`) sind davon **nicht** betroffen und bleiben wie bisher überall gültig.

`pcode` wird **ausschließlich im JSON-Body** gelesen (`"pcode": "…"`). Ein Header
`X-SCLM-Pcode` wird **nicht** unterstützt (Test: Request nur mit Header →
`403 „Eigentumsnachweis fehlt"`).

**Regel für neue Integrationen:** ausschließlich Header verwenden — Query-Parameter landen in
Access-Logs, Browser-History und Referern.

```bash
# Session mit Join-Code laden
curl -s https://sclm.site/api/session/ABC123 \
     -H 'X-SCLM-Code: ABC123'

# Loot als Session-Admin anlegen
curl -s -X POST https://sclm.site/api/session/9k2m4x7q/loot \
     -H 'Content-Type: application/json' \
     -H 'X-SCLM-Code: ADMINCODE' \
     -d '{"name":"Aputarma Blaster","size":"3","qty":1}'
```

Codes werden beim Vergleich normalisiert: `code`/`admin_code` werden uppercase verglichen,
`join_code` ebenfalls (der Server uppercasing den gesendeten Wert). **Praktisch:** `admin_code`
und `join_code` darfst du in beliebiger Schreibweise senden (`vh0zon` = `VH0ZON`).
`pcode` ist dagegen **case-sensitive** — `SecureEq` vergleicht exakt; `pc.upper()` scheitert
(verifiziert: `403 „Nicht autorisiert für diesen Teilnehmer"`). Vergleich ist
konstantzeit-behaftet (Timing-Attenuation).

---

## 2. Rollenmodell im Detail

**Site-Admin (`admin_secret`)**
- Kann jede Session lesen/schreiben/löschen (ersetzt Session-Admin-Berechtigung).
- Kann gesperrte Sessions wieder **entsperren** (darf nur er, siehe §4).
- Verwaltet die globalen Kataloge (Items/Waren/Teilnehmer-Namen) und das Secret.
- Das Secret ist in den Container-Logs (`docker logs <container>`) beim ersten Start,
  bzw. in `/root/get-secret.sh` auf dem Host.

**Session-Admin (`admin_code`)**
- Ersteller einer Session. Volle Kontrolle über deren Teilnehmer, Loot, Waren, Ziehung.
- Darf sperren, aber **nicht** entsperren.

**Teilnehmer (`join_code`)**
- Darf: Session lesen, Selbstregistrierung, eigene Wünsche, eigenes Ergebnis,
  eigener Abgeholt/Verzicht-Status.
- Darf **nicht**: fremde Teilnehmer ändern, Loot/Waren ändern, Ziehung starten, Session-Einstellungen.
- Greift zusätzlich über `pcode` auf „seinen" Teilnehmer-Datensatz zu (§5).

---

## 3. Datenobjekte

### Session

```json
{
  "id": "9k2m4x7q",
  "name": "Jumptown Raid #4",
  "created": "03.11.2026",
  "admin_code": "K7P2QM",         // nur sichtbar für Session-Admin / Site-Admin
  "join_code": "ABC123",
  "max_wishes": 3,
  "locked": false,
  "raffle_locked": false,
  "commodities_locked": false,
  "raffle_done": false,
  "raffle_mode": "wish",           // "wish" | "no_interest" — berechnet, nicht gesetzt
  "total_revenue": 125000.0,       // Umsatz aus Waren (kann null sein)
  "image_url": "https://…",        // kann null sein
  "is_admin": true,                // nur bei GET /api/session/<code>
  "participants": [ … ],
  "loot": [ … ],
  "commodities": [ … ],
  "results": [ … ],                // leer solange raffle_done=false
  "commodity_summary": {
    "total_scu": 1200.0,
    "total_revenue": 180000.0,     // total_revenue + Verkaufserlöse aus Loot
    "sale_revenue": 55000.0,
    "count": 4
  }
}
```

`raffle_mode` wird serverseitig berechnet: `no_interest` wenn
`Summe(qty aller nicht-verkauften Loot-Items) < Anzahl Teilnehmer`, sonst `wish`.
Das entscheidet, welche Auswahl-Oberfläche Teilnehmer sehen.

### Participant

```json
{
  "id": "p8n2k4rt",
  "session_id": "9k2m4x7q",
  "name": "[AAWA]S3-RT-4N",
  "added_by": "admin",             // "admin" | "self"
  "wishes": ["l1id2x3y"],          // loot_ids im Wunschmodus
  "no_interest": ["l9z8y7x6"],     // loot_ids im Kein-Interesse-Modus
  "pcode": "AbCdEf…"               // nur sichtbar für Session-Admin / Site-Admin
}
```

### Loot

```json
{
  "id": "l1id2x3y",
  "session_id": "9k2m4x7q",
  "name": "Aputarma Blaster",
  "qty": 2,
  "type": null,                    // null | MIL | STE | COM | CIV | IND (Komponentenklasse)
  "grade": null,                   // Komponente: "A"–"D"
  "size": "3",                     // "0"–"8" (UI-Label S0–S8, API-Wert ohne "S")
  "loot_key": "apputarma blaster|||3",   // Dedupe-Hash: name|type|grade|size (lowercase)
  "for_sale": 0,
  "sale_revenue": null,
  "wish_count": 3                  // wie viele Teilnehmer dieses Item wollen
}
```

**Typ-/Größen-Semantik (wichtig):** Der Server validiert `type`/`grade`/`size` nicht auf
Wertelisten — er speichert, was gesendet wird. Die Web-UI nutzt diese Konvention:

| Kategorie in der UI | gesendete Felder |
|---|---|
| Item | `type:null, grade:null, size:null` |
| Ship Weapon | `type:null, grade:null, size:"1"…"8"` (Labels S1–S8) |
| Komponente | `type:"MIL"|"STE"|"COM"|"CIV"|"IND", grade:"A"…"D", size:"0"…"8"` (Labels S0–S8) |

`size` ist **immer ein String ohne „S"** (`"3"`, nicht `"S3"`). Fremde Werte (`"weapon"`,
`"S3"`) werden gespeichert, erzeugen aber **andere `loot_key`s** → Duplikate desselben
Items. Halte dich an die Konvention oben.

**3C — keine leeren Saiten:** `type`, `grade` und `size` kennen nur `null` oder einen
Wert — ein dritter Zustand `""` wird nicht gespeichert. Leere oder nur aus Leerzeichen
bestehende Saiten (z. B. `type:""`, `grade:"   "`) normalisiert der Server beim Speichern
(Loot POST, Admin-Item POST) zu `null`, als hätte man das Feld weggelassen.


Dedupe läuft über `loot_key`: identische Kombination aus Name/Typ/Grade/Größe wird
**gemerged** (Menge erhöht), nicht doppelt angelegt.

### Commodity (verkaufte Ware)

```json
{ "id": "c5v6b7n8", "session_id": "9k2m4x7q", "name": "Ryo Ice Tea", "scu": 120.0 }
```

Dedupe über `lower(name)` innerhalb der Session (SCU wird aufaddiert).

### Raffle-Ergebnis

```json
{
  "id": "r3t4y5u6",
  "session_id": "9k2m4x7q",
  "participant_id": "p8n2k4rt",
  "participant_name": "[AAWA]S3-RT-4N",
  "won": [ { "name": "Aputarma Blaster", "type": null, "grade": null, "size": "3" } ],
  "won_json": "[…]",               // Rohfassung von won
  "won_by_wish": 1,                // 1 = mindestens ein Item per Wunsch erhalten
  "waived": 0,
  "collected": 0
}
```

---

## 4. Zustände und was sie blockieren

| Schalter | Setting | Wirkung | Entsperren durch |
|---|---|---|---|
| `locked` | `PATCH /settings {"locked":true}` | Komplette Session schreibgeschützt: Teilnehmer, Loot, Waren, Wünsche, Codes, Ziehung | **nur Site-Admin** (`admin_secret`) |
| `raffle_done` | automatisch nach Ziehung | Ziehung gesetzt, Ergebnisse lesbar | – |
| `raffle_locked` | `PATCH /settings` | Verhindert erneute Ziehung (manuell) | Session-Admin |
| `commodities_locked` | `PATCH /settings` | Waren-Tabelle zu | Session-Admin |
| `setup_viewed` | `/setup` konsumiert | `/setup` liefert nur noch `410` | `POST /admin/change_secret` setzt ihn zurück |

`locked` ist der harte Notstop — nach der Ziehung empfiehlt sich `locked: true`.
Beachte: `PATCH /settings {"locked": false}` ohne `admin_secret` ergibt `403`.

---

## 5. Eigentümerschaft: `pcode` (Teilnehmer-Key)

Jeder Teilnehmer-Datensatz kann einen `pcode` haben. Er begrenzt, **wer** für diesen
Eintrag Wünsche speichern und seinen Gewinn markieren darf.

### Fall A — Selbstregistrierung
`POST /api/session/<sid>/participants` mit `join_code` (kein Admin-Code):
→ Server erzeugt `pcode`, gibt ihn **einmalig** im Response zurück.

```json
{ "id": "p8n2k4rt", "name": "Sebo", "pcode": "xYz…16byte" }
```

**Der Client muss diesen Wert dauerhaft speichern** (localStorage/DB). Ohne ihn gibt es
keinen Wunsch-Zugriff mehr.

### Fall B — Vom Admin angelegt (`pcode` ist null)
Ein vom Session-Admin angelegter Teilnehmer ist zunächst „herrenlos". Er wird beim
**ersten Claim** gebunden (First-Come):

1. Teilnehmer POSTet Wünsche mit `join_code` **und** einem eigenen `pcode`-Wert:
   ```json
   POST /api/session/<sid>/wishes
   { "participant_id": "p8n2k4rt", "loot_ids": ["l1id2x3y"], "pcode": "vom_client_erzeugt", "mode": "wish" }
   ```
   (Kein Header-Ersatz möglich — `pcode` muss im Body stehen, siehe §1.)
2. Server sieht `pcode IS NULL` → setzt den Wert auf den übergebenen → der Eintrag gehört jetzt diesem Client.
3. Spätere Anfragen müssen denselben `pcode` mitbringen, sonst `403 „Nicht autorisiert für diesen Teilnehmer"`.

Der Client erfindet den `pcode` selbst (zufällig, ≥16 Zeichen) und legt ihn lokal ab —
genau so macht es die Web-UI.

### Fall C — Key aushändigen
Session-Admin sieht in `GET /api/session/<code>` (mit `admin_code`) bei allen
Teilnehmern den `pcode`-Wert und kann ihn weitergeben, damit Teilnehmer auf einem
anderen Gerät fortfahren können.

### Wichtige Konsequenzen für Tool-Bauer
- **Ohne `pcode` kein Wunsch-Speichern für Nicht-Admins** — `403 „Eigentumsnachweis fehlt"`.
- **Einmal claimter Datensatz ist ohne Key nicht wiederherstellbar** (außer über Admin).
- Mit `admin_code` brauchst du **keinen** `pcode` und darfst **jeden** Teilnehmer ändern.
- Participants dürfen `waived`/`collected` nur **setzen**, nicht zurücknehmen (one-way).
  Admin/Site-Admin können beides in beide Richtungen.

---

## 6. Endpunkte — Global & Discovery

| Methode | Pfad | Auth | Beschreibung |
|---|---|---|---|
| GET | `/api/stats` | keine | Globalaggregate |
| GET | `/api/sessions` | keine* | Session-Liste |
| GET | `/api/items/search?q=` | keine | Item-Katalog-Autocomplete (max 12) |
| GET | `/api/commodities/search?q=` | keine | Ware-Autocomplete (max 10) |
| GET | `/api/participants/search?q=` | keine | Teilnehmer-Namen-Katalog (max 12) |
| POST | `/api/raidhelper/parse` | keine | Raid-Helper-JSON → Teilnehmerliste |
| GET/POST | `/setup` | Besitzproof | Ersteinrichtung |

### `GET /api/stats`
```json
{ "total_loot": 340, "total_loot_raffled": 297, "total_scu": 4200.0,
  "total_revenue": 812500.0, "session_count": 12, "participant_count": 47 }
```
`participant_count` zählt **distinct Namen** über alle Sessions (keine Duplikatzählung).

### `GET /api/sessions`
Array, neueste zuerst. Pro Eintrag:
```json
{ "id":"9k2m4x7q", "name":"Jumptown Raid #4", "created":"03.11.2026",
  "join_code":null, "admin_code": null, "locked":false, "raffle_done":false,
  "participant_count":9, "loot_count":14, "commodity_scu":1200.0,
  "commodity_revenue":180000.0, "image_url":"https://…" }
```
**`join_code` und `admin_code` sind hier standardmäßig `null`.** Seit Härtung 3B wird die
Feldstruktur nicht entfernt, aber **nur mit gültigem `X-SCLM-Secret`** (Site-Admin) mit
Werten gefüllt — seit Härtung 3C bei `GET` **ausschließlich per Header**; ein `?secret=`
in der Query wird bei diesem Endpunkt ignoriert, die Einträge bleiben `null` (POST/PUT/
PATCH behalten den Query-/Body-Fallback, §1). Alt-Clients, die das Secret trotzdem per
GET-Query senden, gelten seit 3C als unauthentifiziert — und ein einmal gesendetes
Secret bleibt trotzdem in den Access-Logs lesbar, Secret-Rotation ist danach weiterhin
notwendig. Ein Session-`admin_code` allein reicht **nicht**: er berechtigt nur diese eine
Session und liefert in der Liste weiterhin `null`. Wer einen Join-Code braucht, bekommt
ihn über `GET /api/session/<admin_code oder join_code>` (Session-Detail, §7). Für eine
Lese-Ansicht **ohne** Code ist seit Runde 4A `GET /api/public/session/<id>` der vorgesehene
Weg (siehe `GET /api/public/session/<sid>` in §7). Die Liste
selbst ist weiter öffentlich — Namen, Datum, Teilnehmerzahl, Lootzahl, Umsätze bleiben
sichtbar. **Clients dürfen aus dieser Liste keinen Join-Code mehr ableiten** (UI zeigt
dafür ein Code-Eingabefeld pro Event-Karte).
Bei korrumpierten Altwerten (Altbestand) können `loot_count`, `commodity_scu` und
`commodity_revenue` hier als `null` erscheinen (Serialisierung shielded: Ausreißer mit
`|wert| > 1e15` oder nicht endliche Werte; Text-Ausreißer in `loot.qty` ergeben in der
Liste `loot_count` **`0`**, da SQL-`SUM` Text ignoriert, und negativer Altbestand erscheint
als negative Zahl — der Shield hat keine Untergrenze).

### `GET /api/items/search?q=aputarma`
```json
[ { "loot_key":"apputarma blaster|||3", "name":"Aputarma Blaster",
    "type":null, "grade":null, "size":"3" } ]
```
Sucht im **globalen** Katalog (`item_db`), nicht in einer Session. `%`,`_` in der Query
werden escaped (kein Wildcard-Injekt). `item_db` enthält exakt die Werte, die je beim
Loot-Import gesendet wurden — abweichende client-seitige Schreibweisen tauchen hier also
ebenso abweichend auf.

`/api/participants/search` und `/api/commodities/search` arbeiten ebenfalls **global**
(`participant_db` / `commodity_db`) — nicht session-bezogen.
- `item_db`: wird bei jedem `POST …/loot` (`INSERT OR IGNORE`), bei Admin-Katalog und UEX-Import gefüllt.
- `commodity_db`: wird bei jedem `POST …/commodities` gefüllt.
- `participant_db`: wird **nur** über Raid-Helper-Import und `POST /api/admin/participants` gefüllt —
  das Anlegen von Session-Teilnehmern füllt ihn **nicht**. Session-eigene Namen liest du aus
  `GET /api/session/<code>`.

### `POST /api/raidhelper/parse`
Body: `{"json_data": { … }}` — der JSON-Export eines Raid-Helper-Events.
```json
{ "name":"15.10.2026 — [AAWA] Jumptown Mining",
  "participants":["[AAWA]S3-RT-4N","…"],
  "image_url":"https://…" }
```
- Titel-Prefix `[E]` wird entfernt; ohne `date` wird heute (`DD.MM.YYYY`) gesetzt.
- `signUps` mit Klasse `Absence`, `Bench`, `Late` werden verworfen.
- `image_url` kommt aus `advancedSettings.image`.
- Namen landen direkt im globalen Teilnehmer-Katalog. **Noch keine Session nötig** —
  Ergebnis dient als Vorlage für `POST /api/session/create` + Teilnehmer-POSTs.
- Fehler: `400 {"error": "<Ausnahmetext>"}` bei ungültigem JSON.

### `/setup` (First-Run)
- `GET /setup`: Anzeige. `410` wenn bereits konsumiert.
- `POST /setup` mit `{"secret": "<admin_secret>"}`: Besitzproof → `200` (Setup bestätigt).
  Falsches Secret → `200` mit Fehlerseite (kein Leak des echten Secrets).
- Nach Konsum nur noch `410`; `POST /api/admin/change_secret` setzt den Status zurück.

---

## 7. Endpunkte — Session-Lebenszyklus

| Methode | Pfad | Auth | Body | Antwort |
|---|---|---|---|---|
| POST | `/api/session/create` | keine | `{name, max_wishes?, image_url?}` | `{id, admin_code, join_code}` |
| GET | `/api/session/<code>` | Code im Pfad | – | vollständiges Session-Objekt |
| GET | `/api/public/session/<sid>` | keine | – | Session-Objekt **ohne Codes** (öffentliche Lese-Ansicht, Abschnitt unten) |
| PATCH | `/api/session/<sid>/settings` | Admin/Site-Admin | beliebig (unten) | `{"ok":true}` |
| POST | `/api/session/<sid>/regenerate_codes` | Session-Admin | – | `{admin_code, join_code}` |
| DELETE | `/api/session/<sid>` | Admin/Site-Admin | – | `{"ok":true}` |

### POST /api/session/create
```json
{ "name": "Jumptown Raid #4", "max_wishes": 3, "image_url": "https://…/banner.png" }
```
- `name` Pflicht, ≤200 Zeichen.
- `max_wishes` optional, Default **3**, Bereich **1–10** (Ganzzahl), sonst `400`.
  3C: `2.5` → `max_wishes muss eine Ganzzahl sein`; `4.0` und `"4"` sind ok.
- `image_url` optional: nur `http(s)://`, ≤2048 Zeichen, keine `<>"'`/Kontrollzeichen —
  sonst still `null` (kein Fehler!).
- Antwort enthält **beide Codes nur einmal** — danach nur noch über `GET /api/session/<admin_code>`.

Fehler: `400 {"error":"Name erforderlich"}`, `{"error":"Name zu lang"}`,
`{"error":"max_wishes muss eine Ganzzahl sein"}`, `{"error":"max_wishes muss zwischen 1 und 10 liegen"}`.

### GET /api/session/&lt;code&gt;
Der Pfad akzeptiert **`admin_code` oder `join_code`** (Groß-/Kleinschreibung egal).
- Mit `admin_code`: `is_admin: true`, `admin_code` und alle `pcode`-Werte werden mitgeliefert.
- Mit `join_code`: `is_admin: false`, `admin_code` und `pcode` werden **entfernt**.
- `404 {"error":"Code ungültig"}` bei falschem Code.
- `404 {"error":"sid im Pfad nicht erlaubt: GET /api/session/<admin_code oder join_code> verwenden"}`
  wenn im Pfad eine **existierende Session-ID** statt eines Codes steht.
- Vollständige Daten inkl. `participants[].wishes` und `loot[].wish_count` — auch ohne Login-Status.
  Additiv (Härtung 3A): `participants[].wish_count`, `participants[].no_interest_count`,
  `results[].won_count`.
  3C-Präzisierung: `no_interest_count` ist die **Anzahl** der `no_interest`-Einträge
  (`len(no_interest)`, also 0, 1, 2, 3 …) — kein Boolean-Ersatz (1/0) mehr.

### GET /api/public/session/&lt;sid&gt; — öffentliche Lese-Ansicht (Runde 4A)

Der **einzige Lese-Endpunkt**, der eine **Session-ID im Pfad** akzeptiert (die
Schreib-Endpunkte `/api/session/<sid>/…` nehmen weiterhin sid **plus** Code). Kein Code,
kein `X-SCLM-Secret`, kein Header überhaupt nötig — `GET` genügt. `GET /api/session/<code>`
bleibt davon unberührt und akzeptiert **weiter nur Codes** (sid im Pfad → `404`).

**Gilt für alle Sessions**: offen, abgeschlossen (`raffle_done`) und gesperrt (`locked`).
Eine Sperre blockiert nur **Schreibzugriff**, nie das Lesen.

Ausgeliefert werden dieselben Daten wie beim Join-Code-Leser — **nur ohne Codes**:

| Bereich | Felder |
|---|---|
| Session | `id`, `name`, `created`, `max_wishes`, `locked`, `raffle_locked`, `commodities_locked`, `raffle_done`, `raffle_mode`, `total_revenue`, `image_url`, `commodity_summary`, `is_admin` (immer `false`) |
| `participants[]` | `id`, `name`, `added_by`, `wishes` (loot_ids), `no_interest` (loot_ids), `wish_count`, `no_interest_count` |
| `loot[]` | `id`, `name`, `qty`, `type`, `grade`, `size`, `for_sale`, `sale_revenue`, `wish_count` |
| `commodities[]` | `id`, `name`, `scu` |
| `results[]` | `id`, `participant_id`, `participant_name`, `won` (Objekte, wie bei `won_json` zuvor), `won_count`, `won_by_wish`, `waived`, `collected` |

**Ausdrücklich NICHT enthalten** (weder oben noch in `participants[]`, `loot[]`, `results[]`
oder den `won`-Objekten): `join_code`, `admin_code`, `pcode`. Ein `pcode` wird im
Admin-Zweig von `get_session` ergänzt — dieser Pfad wird hier nie betreten.

Fehler: `404 {"error":"Session nicht gefunden"}` bei unbekannter oder nicht existenter
`sid` (immer JSON, nie HTML). `POST/PUT/PATCH/DELETE` auf diesem Pfad gibt es nicht (`405`).

Altbestand-Shielding wie beim Codes-Leser: `loot.qty`, `loot.sale_revenue`,
`commodities.scu` und `total_revenue` werden mit `|wert| > 1e15` oder nicht endlichen
Werten zu `null`; `commodity_summary.total_scu/total_revenue/sale_revenue` sind zusätzlich
abgeschirmt. Die Antwort crasht bei vergifteten Altwerten nicht.

**Empfehlung an Connector-/Manifest-Clients** (Overlay-Manifest, z. B. `sclm.json`; das
Manifest liegt außerhalb dieses Repos — dort nichts ungefragt ändern): damit
„Meine Verlosungen" wieder **ohne Codes** funktioniert, `scan.code_field` auf `"id"` und
`scan.detail_endpoint` auf `/api/public/session/{code}` stellen — der `{code}`-Platzhalter
wird dann mit der Session-ID gefüllt. `match_path` (`participants[].name`) funktioniert
unverändert.

### PATCH /api/session/&lt;sid&gt;/settings
Teilbar: nur die übergebenen Felder werden geändert.

| Feld | Typ | Regeln |
|---|---|---|
| `name` | string | nicht leer, ≤200 → sonst `400` |
| `max_wishes` | int | 1–10 |
| `total_revenue` | number | `null`/`""` löscht; negativ → `400` |
| `locked` | bool | `true` jeder Berechtigte; `false` nur Site-Admin (`403`) |
| `image_url` | string | wie oben |
| `raffle_locked` | bool | – |
| `commodities_locked` | bool | – |

Auth: `admin_code` **oder** `admin_secret`. `404` wenn sid unbekannt.

⚠ **Teilweises Update-Falle:** Ein Feld als `""` zu senden ist nicht „unverändert".
`name: ""` → `400`, `total_revenue: ""` → Wert wird gelöscht. Felder, die du nicht
ändern willst, **nicht** mitschicken.

### POST /api/session/&lt;sid&gt;/regenerate_codes
Nur Session-Admin. `403` wenn nur `join_code`, `403 {"error":"Session gesperrt"}` wenn `locked`.
Neue 6-stellige Codes (Kollisionen gegen alle vorhandenen Codes geprüft). Alte Codes sind sofort ungültig.
Anwendungsfall: Join-Code geleakt, Teilnehmer sollen neu eingeladen werden.

### DELETE /api/session/&lt;sid&gt;
Admin oder Site-Admin. Löscht Session; Kinddaten hängen über `ON DELETE CASCADE`
(Teilnehmer, Loot, Wünsche, Waren, Ergebnisse). Kein Undo.

---

## 8. Endpunkte — Teilnehmer & Wünsche

| Methode | Pfad | Auth | Body |
|---|---|---|---|
| POST | `/api/session/<sid>/participants` | join oder admin | `{name, added_by?}` |
| PATCH | `/api/session/<sid>/participants/<pid>` | Admin | `{name}` |
| DELETE | `/api/session/<sid>/participants/<pid>` | Admin | – |
| POST | `/api/session/<sid>/wishes` | join+pcode oder admin | `{participant_id, loot_ids, pcode?, mode?}` |

### POST …/participants (anlegen)
```json
{ "name": "[AAWA]S3-RT-4N", "added_by": "self" }
```
- Name ≤120 Zeichen, nicht leer.
- Dedupe: **case-insensitive** innerhalb der Session. Bereits vorhanden →
  `409 {"error":"Name bereits vorhanden","id":"p8n2k4rt"}` — die vorhandene ID wird
  mitgeliefert, damit Clients korrekt weiterarbeiten können (ID vorhanden ⇒ Claim-Pfad
  mit `pcode` statt Neuanlage).
- Mit `admin_code`: `added_by: "admin"`, `pcode` im Response **null** → Claim nötig (§5 Fall B).
  `added_by` im Body wird ignoriert; die Rolle entscheidet.
- Mit `join_code`: `added_by: "self"`, `pcode` wird generiert und zurückgegeben.
- `403 {"error":"Session gesperrt"}` wenn `locked`.

Mehrfach-Anlage durch Commas: Die Web-UI splittet `"A, B, C"` clientseitig und POSTet
einzeln — die API nimmt pro Request **genau einen** Namen.

### PATCH …/participants/&lt;pid&gt; (umbenennen)
Nur Admin. `{"name": "Neuer Name"}`; leerer String ändert nichts. Wünsche bleiben erhalten.
Kein Dedupe-Check gegen andere Namen → Duplicate sind möglich.

### DELETE …/participants/&lt;pid&gt;
Nur Admin. Entfernt Teilnehmer **und** dessen Wünsche/No-Interest-Einträge.

### POST …/wishes
```json
{ "participant_id": "p8n2k4rt", "loot_ids": ["l1id2x3y","l2ab12cd"],
  "pcode": "xYz…", "mode": "wish" }
```
- `mode`: `"wish"` (Default) oder `"no_interest"` — je nach Session-`raffle_mode` senden.
- **Ersetzt vollständig** (`DELETE` + `INSERT`): keine inkrementelle Änderung möglich.
  Leere Liste = Wünsche löschen.
- `loot_ids` **muss ein Array sein** (kein String), sonst `400 {"error":"loot_ids muss eine Liste sein"}`.
- Alle IDs müssen zu **dieser** Session gehören → sonst `400 „Ungültiges Loot-Item für diese Session"`.
- Teilnehmer muss existieren → sonst `404 „Teilnehmer nicht in dieser Session"`.
- Nur-Admin-Pfad: `pcode` nicht nötig, jeder Teilnehmer beliebig änderbar.
- Nur-Join-Pfad: `pcode` Pflicht (`403 „Eigentumsnachweis fehlt"`), `max_wishes`-Grenze
  (`400 „Maximal N Wünsche erlaubt"`), Eigentümerschaftsprüfung (`403 „Nicht autorisiert für diesen Teilnehmer"`).
- Ein herrenloser Datensatz wird beim ersten erfolgreichen Aufruf claimt.
- Verkaufte Items (`for_sale:1`) können **nicht** gewünscht werden:
  `400 {"error":"Gegenstand ist für Verkauf markiert","loot_ids":["<id>",…]}` (mode `wish`).
  `mode: "no_interest"` ist davon unberührt. Das Markieren als Verkauf löscht bestehende
  Wünsche weiterhin automatisch.

Beispiel Admin setzt Wünsche für jemanden:
```bash
curl -s -X POST https://sclm.site/api/session/9k2m4x7q/wishes \
  -H 'X-SCLM-Code: ADMINCODE' -H 'Content-Type: application/json' \
  -d '{"participant_id":"p8n2k4rt","loot_ids":["l1id2x3y"],"mode":"wish"}'
```

---

## 9. Endpunkte — Loot & Waren

| Methode | Pfad | Auth | Body |
|---|---|---|---|
| POST | `…/loot` | Admin | `{name, qty?, type?, grade?, size?}` |
| PATCH | `…/loot/<lid>/qty` | Admin | `{delta}` |
| PATCH | `…/loot/<lid>/sale` | Admin | `{for_sale?, sale_revenue?}` |
| DELETE | `…/loot/<lid>` | Admin | – |
| POST | `…/commodities` | Admin | `{name, scu?}` |
| PATCH | `…/commodities/<cid>` | Admin | `{name?, scu?}` |
| PATCH | `…/commodities/<cid>/qty` | Admin | `{delta}` |
| DELETE | `…/commodities/<cid>` | Admin | – |

### POST …/loot
```json
{ "name":"Aputarma Blaster", "size":"3", "qty":2 }              // Ship Weapon
{ "name":"Quantum Core", "type":"MIL", "grade":"A", "size":"1" } // Komponente
{ "name":"Medkit" }                                              // einfaches Item
```
- `name` ≤120, `qty` Default 1, Bereich **1–10000** (3C; `400` bei nicht-Ganzzahl wie `1.5`
  → `qty muss eine Ganzzahl sein`; `3.0` und `"3"` ok).
- Feldkonvention siehe §3 (Typ-Semantik) — `type`/`grade`/`size` werden nicht auf
  Wertelisten validiert; leere Saiten werden zu `null` normalisiert (3C). `name: ""` bleibt
  `400 {"error":"Name erforderlich"}`.
- Dedupe über `loot_key` → existierendes Item: `qty` wird **erhöht**, Response enthält die
  vorhandene `id`. **Nicht** identisch: eigener Eintrag.
- Antwort `{"id":"l1id2x3y","key":"apputarma blaster|||3"}`.
- Nebenwirkung: Name/Typ wandert in den globalen Katalog `item_db` (`INSERT OR IGNORE`).

### PATCH …/loot/&lt;lid&gt;/qty
`{"delta": -1}` → `qty = max(1, qty + delta)` (geht nie unter 1). Für Löschen DELETE nutzen.
`delta` ist Ganzzahl-Feld (Bereich ±100000; 3C: `1.5` → `400 delta muss eine Ganzzahl sein`,
`2.0` ok).

### PATCH …/loot/&lt;lid&gt;/sale
```json
{ "for_sale": true }             // aus der Verlosung nehmen
{ "sale_revenue": 25000 }        // Verkaufserlös
{ "sale_revenue": null }         // löschen
```
`for_sale: true` **löscht alle Wünsche und No-Interest-Einträge** für dieses Item.
`sale_revenue` negativ → `400`.

### DELETE …/loot/&lt;lid&gt;
Entfernt Item **und** alle Wünsche/No-Interest dazu (Kaskade manuell implementiert).

### POST …/commodities
`{"name":"Ryo Ice Tea","scu":120}` — Dedupe über `lower(name)` (SCU wird aufaddiert).
`scu` Default 0, negativ → `400`.

### PATCH /qty / DELETE …/commodities/…
- `qty`: `{"delta": 12.5}` → `scu = max(0, scu + delta)` (Float erlaubt).
- `PATCH` Body `{"scu": 200}` setzt absolut; `{"name": "…"}` setzt Namen (leer ⇒ leerer Name möglich).
- `commodities_locked` blockiert diese Endpunkte **nicht** serverseitig (UI-Filter) — Sperre
  ist ein reiner UI-Zustand. Für echten Schutz `locked` verwenden.

---

## 10. Endpunkte — Ziehung

| Methode | Pfad | Auth | Antwort |
|---|---|---|---|
| POST | `…/raffle` | **nur Session-Admin** | `{"ok":true,"mode":"wish"}` |
| PATCH | `…/raffle/<rid>` | Admin/Site-Admin/join+pcode | `{"ok":true}` |
| GET | `…/raffle/result_for/<pid>` | join oder admin | `{"result": {…}}` |

Rate-Limit: `POST …/raffle` = **20 Requests / 60 s pro IP** → `429`.

### POST /api/session/&lt;sid&gt;/raffle
- **Body-Pflicht:** leerer Request ohne `Content-Type: application/json` → `415` (JSON unter `/api/*`).
  Richtig: `-H 'Content-Type: application/json' -d '{}'`.
- `400 {"error":"Braucht Teilnehmer und Loot"}` wenn Teilnehmer **oder** nicht-verkauftes Loot fehlt.
- **3C-Ausbaugrenze (vor der Expansion geprüft):** Summe der zu expandierenden Loot-Instanzen
  (Mengen aller nicht-verkauften Items; Altbestand-`qty` wird dabei wie in der Ziehung auf
  10000 gekappt mitgezählt) > `RAFFLE_MAX_TOTAL` = **50000** →
  `400 {"error":"Zu viele Loot-Instanzen für eine Ziehung (max 50000)", "loot_instanzen": <Anzahl>}`.
  Die Ziehung startet dann **nicht** (keine Ergebnisse, `raffle_done` unverändert).
- Modus-Auswahl automatisch:
  - `total_items >= participant_count` → `"wish"`
  - `total_items <  participant_count` → `"no_interest"`
- **Wunsch-Modus:**
  - Phase 1: pro Item-Typ Round-Robin über alle Wunsch-Inhaber; vor jedem Zyklus Sortierung
    nach bisherigen Gewinnen aufsteigend, Gleichstand zufällig.
  - Phase 2: verbleibende Einzelstücke jeweils an den Teilnehmer mit den wenigsten Gewinnen.
- **Kein-Interesse-Modus:** Items werden zufällig gemischt; jedes geht an den fairsten
  Teilnehmer, der das Item **nicht** ausgeschlossen hat (Ausschluss aus `no_interest`).
  Schließen alle aus, wird trotzdem verteilt.
- Ergebnisse werden **pro Teilnehmer** als ein Datensatz geschrieben (`won` = alle Items dieses
  Teilnehmers). Bei erneutem Start: alte Ergebnisse werden **gelöscht** und neu geschrieben.
- `raffle_done` wird gesetzt. `raffle_locked` blockiert (UI) ein erneutes Starten — API-seitig
  ist ein Neustart technisch möglich und überschreibt die Ergebnisse.
- Zufallsbasis ist **nicht kryptografisch** (`random.shuffle`) — für interne Gruppen geeignet.

### PATCH …/raffle/&lt;rid&gt;
```json
{ "collected": true }
{ "waived": true }
{ "collected": false }   // nur Admin/Site-Admin
```
- `rid` = Ergebnis-ID aus `session.results[].id`.
- Teilnehmer (`join_code` + `pcode`): darf nur sein **eigenes** Ergebnis, nur **setzen**,
  nie zurücknehmen; `403 „Nicht autorisiert für diesen Gewinn"` ohne/ falschen `pcode`.
  Claim eines herrenlosen Datensatzes funktioniert auch hier.
- Admin: jeder Datensatz, beide Richtungen. `403 „Session gesperrt"` wenn `locked` —
  Site-Admin ignoriert die Sperre.

### GET …/raffle/result_for/&lt;pid&gt;
- `{"result": null}` wenn noch keine Ziehung stattgefunden hat **oder** kein Ergebnis
  für diesen Teilnehmer (Client muss `null` abfangen, nicht nur HTTP-Status).
- Sonst `{"result": { id, participant_id, participant_name, won:[…], won_by_wish, waived, collected, … }}`.

---

## 11. Endpunkte — Katalog & Site-Admin (alle `X-SCLM-Secret`)

| Methode | Pfad | Body | Antwort |
|---|---|---|---|
| GET | `/api/admin/data` | – | `{items:[…], participant_names:[…], commodity_names:[…]}` |
| POST | `/api/admin/items` | `{name, type?, grade?, size?}` | `{"ok":true,"key":…}` (`INSERT OR REPLACE`) |
| DELETE | `/api/admin/items/<loot_key>` | – | `{"ok":true}` |
| POST | `/api/admin/participants` | `{name}` | `{"ok":true}` |
| DELETE | `/api/admin/participants/<name>` | – | `{"ok":true}` |
| POST | `/api/admin/commodities` | *(keine Route — nur DELETE)* | – |
| DELETE | `/api/admin/commodities/<name>` | – | `{"ok":true}` |
| POST | `/api/admin/uex_import` | `{items:[{name,type,grade,size}]}` | `{ok,added,skipped,total}` |
| POST | `/api/admin/verify` | `{"secret": "…"}` | `200 {"ok":true}` / `403` |
| POST | `/api/admin/change_secret` | `{new_secret}` | `{"ok":true}` |
| GET | `/api/admin/secret-hint` | – | `{secret,…}` **nur localhost / TRUSTED_PROXIES** |

- Katalog-DELETE-Pfade nutzen `<path:key>` — der Loot-Key (`name|type|grade|size`) muss
  URL-kodiert werden (`|` → `%7C`).
- `change_secret`: altes Secret nötig (`403 „Aktuelles Kennwort falsch"`), neues ≥8 Zeichen
  (`400`). Rate-Limit 10/60 s. Setzt `setup_viewed` zurück.
- `verify`: Rate-Limit 30/60 s; nützlich um Secret-Gültigkeit vor einer Aktion zu prüfen.
- `uex_import`: Browser liefert bereits gemappte Werte (`type` in `MIL|STE|COM|CIV|IND`,
  `grade` in `A|D`, `size` Ziffernstring). Unbekannte Werte → `null`. Merge-Logik:
  gleicher `loot_key` ⇒跳过; gleicher Name mit anderen Attributen ⇒ Zeile wird
  **ersetzt** (alter Key gelöscht). `added` zählt neue **und** aktualisierte Einträge.
- `secret-hint`: gibt das Secret im Klartext zurück — standardmäßig nur von `127.0.0.1`/`::1`
  (oder IPs in `TRUSTED_PROXIES`). Mit `DISABLE_SECRET_HINT=1` komplett deaktiviert (`404`).
  **Nie** von außen in Automationen nutzen — Stattdessen `docker logs` / `get-secret.sh`.

Rate-Limits gesamt: `raffle` 20/60 s, `verify` 30/60 s, `change_secret` 10/60 s.
`429 {"error":"Zu viele Anfragen. Bitte später erneut versuchen."}`. Client-IP kommt aus
`X-Forwarded-For` (erster Eintrag) mit Fallback `remote_addr`.

---

## 12. Fehlerkatalog (complete)

| HTTP | Nachricht | Ursache / Behandlung |
|---|---|---|
| 400 | `Name erforderlich` | leerer/fehlender Name (Session, Teilnehmer) |
| 400 | `Name zu lang` | >200 (Session) / >120 (Teilnehmer, Loot, Ware) |
| 400 | `max_wishes muss eine Ganzzahl sein` / `muss zwischen 1 und 10 liegen` | Settings/Create (3C: auch bei `2.5`) |
| 400 | `total_revenue muss eine Zahl sein` / `darf nicht negativ sein` | Settings |
| 400 | `sale_revenue muss eine Zahl sein` / `darf nicht negativ sein` | Loot-Sale |
| 400 | `scu muss eine Zahl sein` / `darf nicht negativ sein` | Waren |
| 400 | `scu muss eine Zahl sein` / `scu darf nicht negativ sein` | Waren (POST/PATCH) |
| 400 | `total_revenue muss eine Zahl sein` / `total_revenue darf nicht negativ sein` | Settings |
| 400 | `sale_revenue muss eine Zahl sein` / `sale_revenue darf nicht negativ sein` | Loot-Verkauf |
| 400 | `delta muss eine Ganzzahl sein` | Loot-Menge (Int; 3C: auch bei `1.5`) |
| 400 | `delta muss eine Zahl sein` | Waren-Menge (SCU, Float erlaubt) |
| 400 | `qty muss eine Ganzzahl sein` | Loot (3C: auch bei `1.5`; Grenze 1–10000) |
| 400 | `Zu viele Loot-Instanzen für eine Ziehung (max 50000)` (+ Feld `loot_instanzen`) | POST …/raffle: >50000 zu expandierende Instanzen (§10, 3C) |
| 400 | `Keine Daten empfangen` | `uex_import` mit leerer `items`-Liste |
| 400 | `participant_id erforderlich` | Wünsche ohne ID |
| 400 | `loot_ids muss eine Liste sein` | Array-Typ zwingend (JSON-String reicht nicht) |
| 400 | `Ungültiges Loot-Item für diese Session` | loot_id aus anderer Session |
| 400 | `Maximal N Wünsche erlaubt` | nur Join-Code-Pfad, > `max_wishes` |
| 400 | `Braucht Teilnehmer und Loot` | Ziehung ohne Teilnehmer oder nicht-verkauftes Loot |
| 400 | *(Fehlerseite)* | Setup: zu kurzes/leeres Secret im First-Run |
| 403 | `Nicht autorisiert` | falscher/fehlender Code, falsches Secret, `verify`/`change_secret` |
| 403 | `Nicht autorisiert für diesen Teilnehmer` | wishes: fremder Datensatz / falscher `pcode` |
| 403 | `Nicht autorisiert für diesen Gewinn` | raffle-PATCH: fremder Teilnehmer / falscher `pcode` |
| 403 | `Eigentumsnachweis fehlt` | wishes ohne `pcode` (Join-Pfad) |
| 403 | `Nur ein Administrator kann entsperren` | `locked:false` ohne Site-Admin |
| 403 | `Session gesperrt` | `locked` blockiert Aktion (`regenerate_codes` ausgenommen Site-Admin) |
| 403 | `Aktuelles Kennwort falsch` | `change_secret` ohne korrektes altes Secret |
| 403 | `Ungültiges Kennwort` | `POST /api/admin/verify` mit falschem Secret |
| 400 | `Kennwort muss mindestens 8 Zeichen haben` | `change_secret` mit zu kurzem neue Secret |
| 403 | `Nur lokal erreichbar` | `secret-hint` von extern |
| 404 | `Nicht gefunden` | unbekannte Session-ID |
| 404 | `Session nicht gefunden` | `GET /api/public/session/<sid>` mit unbekannter/fehlender sid (Abschnitt „öffentliche Lese-Ansicht“, §7) |
| 404 | `Code ungültig` | `GET /api/session/<code>` mit falschem Code |
| 404 | `Teilnehmer nicht in dieser Session` | participant_id gehört nicht zur Session |
| 404 | `Deaktiviert` | `secret-hint` mit `DISABLE_SECRET_HINT=1` |
| 409 | `Name bereits vorhanden` (+ `id`) | Teilnehmer-Dedupe (case-insensitive) — `id` nutzen |
| 410 | *Setup abgeschlossen* | `/setup` nach Konsum |
| 429 | `Zu viele Anfragen. Bitte später erneut versuchen.` | Rate-Limit |

`{"result": null}` bei `result_for` ist **200**, nicht 404 — Ergebnis fehlt noch.

---

## 13. Kanonische Abläufe (Rezepte)

### 13.1 Ersteller-Flow
```
POST /api/session/create            → {id, admin_code, join_code}   (beide speichern!)
POST /api/raidhelper/parse          → Teilnehmernamen (optional)
POST /api/session/{id}/participants → je Name, mit admin_code → pcode = null
POST /api/session/{id}/loot         → je Item (Menge >1 via qty)
POST /api/session/{id}/commodities  → je Ware
POST /api/session/{id}/raffle       → Ziehung (nur mit admin_code)
PATCH /api/session/{id}/settings    → {"locked": true}               (Notstop)
```

### 13.2 Teilnehmer-Flow (vom Admin schon angelegt — Regelfall in Gruppen)
```
GET  /api/session/{join_code}                       → Session + participant_id der Person
POST /api/session/{id}/wishes   {participant_id, loot_ids, pcode:<selbst erzeugen>, mode}
     → Server claimt den herrenlosen Datensatz
     → pcode lokal dauerhaft speichern (sonst Sperre bei Gerätewechsel)
GET  /api/session/{id}/raffle/result_for/{pid}      → {"result": null} bis Ziehung da ist
PATCH /api/session/{id}/raffle/{result_id} {collected:true, pcode}
```

### 13.3 Teilnehmer-Flow (Selbstregistrierung ohne Admin)
```
POST /api/session/{id}/participants {name}            (join_code) → {id, pcode}
POST /api/session/{id}/wishes       {participant_id, loot_ids, pcode, mode}
```

### 13.4 Teilnehmer will ihr Item nicht
```
POST …/raffle/{rid} {waived:true, pcode}
```
Es gibt **keinen** automatischen Weiterverkauf/Neuverteilung — waived ist nur ein Flag.
Wer das Item weitergeben will, muss den Admin bitten (Admin kann Flag zurücksetzen oder
Loot/Ergebnis manuell anpassen).

### 13.5 Join-Code versehentlich öffentlich
```
POST /api/session/{id}/regenerate_codes   (admin_code)
→ neue join_code + admin_code verteilen; alte Logins aller Teilnehmer brechen
```
Betroffene Teilnehmer müssen ihre `pcode`-Beziehung erneut aufbauen (Claim unter neuer Session-Codierung;
bestehende `pcode`-Werte bleiben an den Datensatz gebunden, nur der Session-Code ändert sich).

### 13.6 Lesemodus / Dashboard ohne Login
```
GET /api/sessions                    → Übersicht aller Events (keine Codes)
GET /api/public/session/{id}         → vollständige Einsicht OHNE Codes (Runde 4A)
GET /api/session/{join_code}         → dieselbe Einsicht, aber nur mit Code
GET /api/stats                       → Globalzahlen
```
Reicht für Discord-Bots, overlays, Stream-Overlays. **Seit Härtung 3B liefert die Liste
keine Join-Codes mehr** (`join_code: null` ohne `X-SCLM-Secret`). **Seit Runde 4A ist dafür
kein Code mehr nötig**: Listing → `id` → `GET /api/public/session/<id>` liefert Teilnehmer,
Loot, Wunsch-/No-Interest-Listen und Ziehungsergebnisse vollständig — für **jede** Session
(auch gesperrt und abgeschlossen). Wer **interagieren** will (Wünsche, Ergebnisse setzen,
Loot, Teilnehmer), braucht weiterhin Codes; der Codes-Leser `GET /api/session/<join_code>`
bleibt unverändert verfügbar.

**Hinweis an Clients (Overlay-Konnektor, KI-Agenten):** die Sessions-Liste liefert
weiterhin **keine** Codes und ist die einzige Quelle für `id`/`name`/Zähler. Öffentliche
Details laufen über `/api/public/session/<sid>`; alles Schreibende braucht
`X-SCLM-Code` (`admin_code`/`join_code` + ggf. `pcode`). **Eine sid darf nie in einen
`/api/session/<...>`-Pfad oder in `X-SCLM-Code` geschrieben werden** — dieser Pfad akzeptiert
nur Codes und lehnt sid mit `404` ab.

### 13.7 Teilnehmer-Key aushändigen (Gerätewechsel)
```
GET /api/session/{admin_code}   → participants[].pcode lesen
```
`pcode` an die Person geben; Client legt ihn unter `(session_id, participant_id)` ab.

---

## 14. Polling & Persistenz für Clients

- Kein Push — Statuswechsel werden erkannt durch: `GET /api/session/<code>`
  (`raffle_done`, `locked`, `participants[].wishes`) bzw. `result_for`.
- Empfohlene Intervalle: während laufendem Event **15–30 s**, nach Ziehung **60–120 s**,
  langfristige Dashboards **300 s**. Kein Burst (< 5 s) — Rate-Limits sind pro IP global.
- Zu speichern (Client-Seite, persistent):
  - `session_id`, `admin_code` (nur Ersteller), `join_code`
  - `participant_id` + `pcode` (Teilnehmer) — **der einzige Weg, den Wunsch-Zugriff zu behalten**
  - `result_id` nach Ziehung (für `PATCH collected/waived`)
- Idempotenz: `POST …/wishes` ist **ersetzend**, nicht additiv — mehrfaches Senden derselben
  Payload ist harmlos. `POST …/participants` ist beim zweiten Mal `409` (mit `id`).
  `POST …/raffle` ist **nicht** idempotent (überschreibt Ergebnisse).

---

## 15. Bauhinweise / typische Fallstricke

1. **Array statt String:** `loot_ids` muss echtes JSON-Array sein. Ein `"[\"lid\"]"` als String → `400`.
2. **Kein leeres Feld senden** in `PATCH /settings` — `name:""` → 400, `total_revenue:""` → Wert weg.
3. **Bool-Fallen:** `waived`/`collected` als `"false"` (String) ist truthy → wird gesetzt. Immer echtes `false`/`true` senden.
4. **Teilnehmer können Flags nicht zurücknehmen** — Fehlerbehandlung: Admin-Kontakt statt Retry.
5. **`result_for` liefert 200 mit `null`** — HTTP-Status allein reicht nicht als „kein Ergebnis".
6. **`sid` ≠ `code`:** alle Pfad-`<sid>` brauchen die Session-ID. `GET /api/session/<code>` braucht einen Code.
7. **`for_sale: true` löscht Wünsche** — vor dem Setzen prüfen, Teilnehmer informieren.
8. **Item-Dedupe ist Attribut-abhängig:** gleicher Name mit anderer `size` = anderes Item.
   UEX-Attribute (`S3` vs `3`) sind bei Waffen/Komponenten unterschiedlich notiert.
9. **`raffle_mode` nicht setzbar** — nur durch Loot-Menge vs. Teilnehmerzahl beeinflussbar.
   Ein Client sollte `participants[].no_interest` vs `wishes` entsprechend der Sessions-`raffle_mode` pflegen.
10. **Neustart der Ziehung überschreibt Ergebnisse** — `collected`/`waived`-Markierungen gehen dabei verloren.
11. **`image_url` wird still ignoriert** wenn ungültig — nicht als Fehler behandeln, sondern URL validieren.
12. **`join_code` kommt nicht mehr aus `GET /api/sessions`** (seit Härtung 3B `null` ohne gültiges `X-SCLM-Secret`). Ein Client, der Events auflistet und dann beitreten will, muss den Code vom Ersteller erhalten oder ihn vom Site-Admin bekommen. Die UI löst das über ein Code-Eingabefeld auf der Event-Karte.
13. **Kein Multi-User-Lock:** gleichzeitige Wünsche desselben Teilnehmers aus zwei Clients können sich
    gegenseitig überschreiben (last-write-wins auf `DELETE`+`INSERT`). Ein Client pro Teilnehmer ist sicherer.
14. **Zwei Lesewege, zwei Pfad-Verträge (Runde 4A):** `/api/public/session/<sid>` nimmt **nur** die
    Session-ID und liefert **keine** Codes; `/api/session/<code>` nimmt **nur** Codes. Eine sid in
    `X-SCLM-Code` oder in `/api/session/<sid>` ist ein Client-Fehler → `404` (`sid im Pfad nicht
    erlaubt`), kein Server-Problem. Für eine reine Lese-Ansicht nie einen Code verwenden, für eine
    Interaktion nie die sid.

---

## 16. Verifikationsstand

Diese Referenz wurde gegen eine lokal ausgeführte Instanz des v5.0-Codes verifiziert
(2026-11-03, `server.py` Stand `main`; Codes und Session-IDS unten sind Wegwerfwerte einer
lokalen Testinstanz, nicht der Produktivinstanz). Nach Härtung 3A und 3B nachgeprüft
(2026-11-06, Stand `main` nach Merge von `fix/hardening-3b`, 44 Unit-Tests grün);
Härtung 3C (Zweig `fix/hardening-3c`, in diesem Stand gemerged) ebenfalls live
nachgeprüft (2026-11-06, 71 Unit-Tests grün). Runde 4A (öffentliche Lese-Ansicht, Zweig
`feat/public-session-view`) gegen eine lokale Instanz nachgeprüft (2026-11-06, 92 Unit-Tests
grün, 38 Live-Probe-Prüfungen, dazu UI-Rauchtest im Browser):

- `GET /api/sessions`: `join_code` und `admin_code` sind `null` ohne Authentifizierung; mit
  gültigem `X-SCLM-Secret` kommen beide zurück — seit Härtung 3C bei diesem `GET` **nur per
  Header**, `?secret=` in der Query wird ignoriert (Einträge bleiben `null`); mit halbem,
  falschem oder leerem Secret bleibt alles `null`; ein Session-`admin_code` im
  `X-SCLM-Code`-Header füllt die Liste **nicht**.
- Session-Detail unverändert: `GET /api/session/<join_code>` liefert den eigenen
  `join_code` (kein `admin_code`), `GET /api/session/<admin_code>` liefert `join_code` **und**
  `admin_code`. `admin_code`-Spalten in der `participants`-Tabelle liefert die API nie.
- Teilnehmer-Registrierung über `POST /api/session/<sid>/participants` (`code` im Body) und
  `pcode`-Ablauf unverändert funktionsfähig.
- UI: Event-Karte zeigt „👁 Ansehen" (sid, öffentlicher Endpunkt, ohne jeden Code) **und**
  „🔑 Ansehen mit Code" mit Inline-Eingabefeld; falscher Code zeigt „Code ungültig" inline,
  richtiger Code öffnet die Lesemaske; kein Code steht im HTML der Startseite. Reload der
  öffentlichen Ansicht lädt dieselbe Ansicht über `/api/public/session/<sid>` (im Access-Log
  taucht dabei **kein** `/api/session/<sid>` auf). Site-Admin-Maske zeigt weiterhin
  „👁 Ansehen" über `openRO(join_code)`.

- `pcode` nur im Body (Header ignoriert), case-sensitive; `admin_code`/`join_code` case-insensitive
- `409` bei DuplikatName (case-insensitive) inklusive vorhandener `id`
- `403 „Eigentumsnachweis fehlt"` ohne `pcode`, `403 „Nicht autorisiert für diesen Teilnehmer"` bei falschem `pcode`
- Claim-Mechanismus (First-Come) für Admin-angelegte Teilnehmer, auch über `PATCH …/raffle/<rid>`
- `400` bei `loot_ids` als String, `loot_ids: []` löscht Wünsche
- `415` bei POST/PATCH ohne `Content-Type: application/json`, `400` bei JSON-CT ohne Body
  (seit Härtung 3A als JSON-Antwort unter `/api/*`, siehe §0)
- `settings`: `name:""` → `400`, `total_revenue:""` → Wert `null`, `image_url` ungültig → still `null`
- `locked` per Session-Admin möglich, Entsperren nur mit `X-SCLM-Secret` (`403` sonst)
- `for_sale:true` entfernt Wünsche/No-Interest dieses Items
- Teilnehmer dürfen `waived`/`collected` nur setzen (Rücksetzen bleibt `1`)
- `regenerate_codes` mit `join_code` → `403`; neue Codes ungültig für alte Logins (`404`)
- Loot-Menge floor 1, Waren-SCU floor 0, Dedupe-Verhalten (Loot `loot_key`, Waren `lower(name)`)
- Rate-Limit `…/raffle`: 20 OK, dann `429`
- `raffle_mode`-Umschaltung (wish ↔ no_interest) und Ziehungsmodus im Response
- Kataloge: `item_db`/`commodity_db` füllen sich beim Anlegen, `participant_db` **nicht**
- `result_for` → `{"result": null}` vor der Ziehung

Runde 4A (öffentliche Lese-Ansicht, live geprüft):

- `GET /api/public/session/<sid>`: `200` **ohne** Header, Code oder Secret; `is_admin:false`;
  Teilnehmer, `wishes`/`no_interest`, `wish_count`/`no_interest_count`, Loot-Mengen,
  `for_sale`/`sale_revenue`, Waren-`scu`, `commodity_summary` und nach der Ziehung `results[]`
  mit `won`/`won_count` sind identisch zum Join-Code-Leser.
- Kein `join_code`-, `admin_code`- oder `pcode`-Schlüssel im Payload (rekursiv über dict/list
  geprüft, inkl. `won`-Objekten); keine Code-Werte im rohen JSON-Text; `won_json` wird nicht
  ausgeliefert.
- Unbekannte sid → `404 {"error":"Session nicht gefunden"}` als JSON (nie HTML);
  `POST` auf dem Pfad → `405` als JSON.
- `GET /api/session/<sid>` bleibt unverändert abgelehnt (`404 „sid im Pfad nicht erlaubt"`);
  `GET /api/session/<join_code>` und `/<admin_code>` unverändert funktional.
- Vergifteter Altbestand (`loot.qty=1e20`, `sale_revenue`/`scu`/`total_revenue=1e30` per
  Test-DB gesetzt): `200` ohne Crash, Felder erscheinen als `null`, keine `1e20`/`Infinity`
  im Payload; `commodity_summary` abgeschirmt.
- Gesperrte (`locked`) und abgeschlossene (`raffle_done`) Sessions sind öffentlich lesbar;
  Schreibversuche bleiben abgelehnt (ohne Codes `403 „Nicht autorisiert"`, mit Join-Code und
  Sperre `403 „Session gesperrt"`).
- `GET /api/sessions` liefert weiterhin keine Codes; `?secret=` bei GET ignoriert (3C),
  `X-SCLM-Secret`-Header liefert Codes (Probe mit Dummy-Secret, kein Produktivwert).

Nicht verändert durch diese Dokumentation: Verhaltensweisen, die nur aus dem Code ablesbar
sind (z. B. Zufallsbasis der Ziehung, `ON DELETE CASCADE`, UEX-Merge-Logik).
