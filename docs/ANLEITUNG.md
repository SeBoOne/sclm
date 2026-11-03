# SCLM — Anleitung (Ersteller & Teilnehmer)

SCLM ist ein Web-Tool zur fairen Verlosung von Loot in Star Citizen nach gemeinsamen
Missionsläufen. Es läuft im Browser — sowohl am PC als auch mobil. Sprache umschaltbar
(DE/EN, oben in der Kopfzeile), Farbschema (Ion/Cargo/Uplink) über das kleine Dropdown
in der Kopfzeile — die Wahl wird im Browser gespeichert.

---

## Ablauf in 60 Sekunden

1. **Ersteller** öffnet sclm.site → „+ Neues Event" → Name + max. Wünsche → **Event erstellen**
2. Ersteller teilt den **6-stelligen Join-Code** (und optional den Admin-Code) mit der Crew
3. **Teilnehmer** geben den Join-Code ein, wählen/registrieren ihren Namen, markieren ihre Wünsche
4. Ersteller legt Loot ein (und ggf. verkaufte Waren mit SCU)
5. Ersteller startet die **Ziehung** — SCLM verteilt fair, niemand muss würfeln
6. Teilnehmer sehen ihr Ergebnis und markieren „abgeholt" oder „Verzicht"

---

## A. Anleitung für Ersteller (Session-Admin)

### 1. Event anlegen

- Startseite → **„+ Neues Event"**:
  - **Event-Name** (z. B. „Jumptown Raid #4")
  - **Max. Wünsche pro Teilnehmer** (1–10, Standard 3)
- Nach dem Erstellen siehst du zwei Codes:
  - **Join-Code** → an die Crew verteilen (Teilnehmer-Login)
  - **Admin-Code** → nur für dich, das ist dein Veranstalter-Login
- Optional: **Raid-Helper-Import** — statt Namen einzutippen kannst du einen
  Raid-Helper-Event-Export (`.json`) hochladen; die Teilnehmer werden automatisch
  aus der Anmeldeliste übernommen.

> **Tipp:** Notiere dir beide Codes. Du kannst dich später über die Startseite mit
> dem Join-Code einloggen und siehst als Ersteller einen „Admin"-Schnellzugriff —
> dieser funktioniert pro Browser-Tab (Session-Speicherung) für das zuletzt
> erstellte Event.

### 2. Admin-Ansicht (5 Tabs)

Mit deinem Admin-Code eingeloggt hast du fünf Tabs:

**◈ Übersicht** — Live-Kennzahlen: Teilnehmer, Loot-Items, SCU der Waren,
Gesamteinnahmen, Sperr-Buttons:
- **Event sperren/entsperren** — gesperrt = nichts änderbar, nur Ansicht
- **Codes neu generieren** — wenn der Join-Code versehentlich weitergegeben wurde

**◈ Teilnehmer** — Namen hinzufügen (Komma für mehrere), Teilnehmer entfernen,
Wünsche anderer einsehen. Hier steht auch der 🔑-Button pro Teilnehmer:
kopiert den **Teilnehmer-Key**, den du an die Person weitergeben kannst (wird
gebracht, wenn sie sich selbstregistriert — sonst wird ihr Eintrag beim ersten
Wunsch-Speichern automatisch an sie gebunden).

**◈ Loot** — Items eintragen. Drei Kategorien:
- **Item** — freier Name (Autocomplete aus dem UEX-Katalog)
- **Waffe** — nur Größe (S0–S8)
- **Komponente** — Klasse (MIL/STE/COM/CIV/IND), Grade (A–D), Größe (0–8)
Menge pro Item per +/- anpassen. Ein Item entfernen, das schon Wünsche hat,
entfernt auch die Wünsche darauf.

**◈ Waren** — Verkaufte Ware eintragen (Name + SCU) und den **Gesamtumsatz**
hinterlegen. Die Umsätze fließen in die Statistik der Startseite ein und dienen
als Kontext für die Verteilung.

**◈ Verlosung** — Hier passiert die Magie (siehe unten).

### 3. Die Ziehung

Button **„Ziehung starten"**. SCLM wählt automatisch den fairen Modus:

- **Wunsch-Modus** (Standard, mehr Items als Teilnehmer):
  Gewünschte Items werden zuerst verteilt — Round-Robin „wer hat am wenigsten
  gewonnen bekommt zuerst", pro Zyklus neu sortiert. Danach gehen Rest-Items
  (keine Wünsche) an den Teilnehmer mit den wenigsten Gewinnen, Zufalls-Tiebreak.
- **Kein-Interesse-Modus** (weniger Items als Teilnehmer):
  Teilnehmer markieren stattdessen, was sie **nicht** wollen. Jedes Item geht an
  den bis dahin fairsten Empfänger, der es nicht ausgeschlossen hat.

Nach der Ziehung sperrt SCLM die Verlosung. Ergebnisse sind pro Teilnehmer sichtbar.

### 4. Nach der Ziehung

- Teilnehmer markieren selbstständig **abgeholt** oder **Verzicht** — du siehst den
  Status live im Tab Verlosung.
- Als Admin kannst du beide Markierungen ebenfalls setzen/korrigieren.
- Verkaufte Items: Erlös wird anteilig (nach 0,5 % Lagergebühr-Modell) angerechnet.

---

## B. Anleitung für Teilnehmer

### 1. Beitreten

1. Link von deinem Veranstalter erhalten (sclm.site) **oder** sclm.site öffnen
2. Unter **„Mit Code einloggen"** den **6-stelligen Join-Code** eingeben → Einloggen
3. **Namen wählen:** Falls du schon in der Liste bist → dein Name. Falls nicht →
   Namen eintippen (Selbstregistrierung) → du bist angemeldet.

> Dein „Angemeldet als"-Status bleibt im Browser-Tab erhalten — Reload ist kein
> Problem. Wechselst du Gerät/Tab, wählst du einfach wieder deinen Namen.

### 2. Wünsche setzen

- **Normaler Modus** (genug Items): Haken bei den Items setzen, die du haben
  willst — max. so viele wie der Veranstalter erlaubt (Standard 3).
- **Kein-Interesse-Modus** (wenige Items): Haken bei dem, was du **nicht** willst.
- **Speichern** — du landest auf der Warteseite. Die Seite aktualisiert sich
  automatisch; du kannst den Tab offen lassen.

### 3. Ergebnis

Nach der Ziehung siehst du sofort, was du bekommen hast (und ob es durch deinen
Wunsch zustande kam). Zwei Buttons:

- **✓ Abgeholt** — du hast den Loot erhalten
- **Verzicht** — du willst ihn nicht (das Item kann ggf. neu verteilt werden)

---

## C. Für alle: Lesemodus & Sonstiges

- **Lesansicht** („Ansehen" auf der Startseite): Einblick in Loot, Waren und
  Ziehungsergebnisse — ganz ohne Login. Ideal für Zuschauer oder den Discord-Share.
- **Administration** (Startseite, oben rechts): Nur für den Server-Betreiber
  (Secret-geschützt) — Katalog-Verwaltung, UEX-Import, Kennwort ändern.
- **Mobil:** Alle Ansichten sind responsive; Anmeldung und Wunsch-Auswahl
  funktionieren problemlos vom Handy.

> **Für Techniker / eigene Tools:** Die vollständige API-Referenz (Auth-Regeln, alle
> Endpunkte, Fehlerkatalog, Szenario-Beispiele) liegt in [API.md](API.md).

## D. Häufige Fragen

**Ich habe meinen Admin-Code verloren.**
Der Server-Betreiber kann Codes aus den Container-Logs bzw. der Datenbank auslesen
(siehe README). Alternativ: „Codes neu generieren" (Site-Admin) oder Event neu anlegen.

**Jemand fremder hat meinen Join-Code.**
Als Admin: Tab Übersicht → **Codes neu generieren**. Alle alten Links/Logins werden
ungültig, du verteilst den neuen Code an deine Crew.

**Ein Teilnehmer erscheint zweimal / will seinen Namen ändern.**
Admin-Tab Teilnehmer: Eintrag entfernen, neu anlegen. Wünsche gehen dabei verloren
(müssen neu gesetzt werden) — am besten vor der Ziehung klären.

**Warum bekomme ich weniger als andere?**
Der Algorithmus gleicht Gewinne aus: Wer in vergangenen Ziehungen mehr bekommen
hat, rutscht nach hinten. Über mehrere Events hinweg ist die Verteilung fair —
einzelne Ziehungen können asymmetrisch aussehen, das ist das Design.
