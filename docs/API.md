# SCLM — API-Referenz (Standard-Version v5.0)

Alle Endpunkte (außer `/setup`, `/api/stats`, `/api/sessions`, `/api/items/search`,
`/api/commodities/search`, `/api/participants/search`, `/api/raidhelper/parse`)
erfordern Authentifizierung.

## Authentifizierung

| Rolle | Code | Übergabe |
|---|---|---|
| Site-Admin | `admin_secret` (32-Zeichen-Hex) | Header `X-SCLM-Secret` (Query-Param `secret` als Legacy-Fallback) |
| Session-Admin | 6-stelliger `admin_code` | Header `X-SCLM-Code` (Query-Param `code` als Legacy-Fallback) |
| Teilnehmer | 6-stelliger `join_code` | Header `X-SCLM-Code` |

Session-Admins und Teilnehmer können nur ihre eigene Session bearbeiten;
Teilnehmer können nur IHREN eigenen Teilnehmer-Eintrag ändern (pcode-Bindung,
H5-Fix). Fehlerantworten sind JSON: `{"error": "..."}` mit Status 400/403/404/410.

## Global

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/stats` | `{session_count, total_loot_raffled, total_scu, total_revenue}` |
| GET | `/api/sessions` | Alle Sessions (joined list, ohne Codes) |
| GET | `/api/items/search?q=&limit=` | Loot-Autocomplete (UEx-Katalog) |
| GET | `/api/commodities/search?q=&limit=` | Ware-Autocomplete |
| GET | `/api/participants/search?q=` | Teilnehmer-Autocomplete (innerhalb der Session) |
| POST | `/api/raidhelper/parse` | Raid-Helper-Paste einlesen → Teilnehmerliste |
| GET | `/setup` | First-Run: Setup-Seite |
| POST | `/setup` | First-Run-Setup (Secret-Prüfung, 410 wenn bereits konsumiert) |

## Session-Lifecycle

| Methode | Pfad | Body/Beschreibung |
|---|---|---|
| POST | `/api/session/create` | `{name, image_url?, revenue?}` → `{id, admin_code, join_code}` |
| GET | `/api/session/<code>` | Session nach admin_code ODER join_code |
| PATCH | `/api/session/<sid>/settings` | `{code, max_wishes?, locked?, image_url?, revenue?, for_sale_mode?}` |
| POST | `/api/session/<sid>/regenerate_codes` | Codes neu generieren |
| DELETE | `/api/session/<sid>` | Session löschen |

## Teilnehmer

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/session/<sid>/participants` | `{code, name, added_by: "admin"|"self"}` → `{id, name, pcode}` |
| DELETE | `/api/session/<sid>/participants/<pid>` | Teilnehmer entfernen |
| PATCH | `/api/session/<sid>/participants/<pid>` | `{code, pcode, waived?, collected?}` |
| POST | `/api/session/<sid>/wishes` | `{code, participant_id, loot_ids[], pcode}` — Wish-Liste oder (leere Liste) No-Interest |

## Loot & Waren

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/session/<sid>/loot` | `{code, name, qty?, for_sale?}` |
| DELETE | `/api/session/<sid>/loot/<lid>` | Loot entfernen |
| PATCH | `/api/session/<sid>/loot/<lid>/qty` | `{code, delta}` |
| PATCH | `/api/session/<sid>/loot/<lid>/sale` | `{code, for_sale, sale_revenue?}` |
| POST | `/api/session/<sid>/commodities` | `{code, name, scu}` |
| PATCH | `/api/session/<sid>/commodities/<cid>` | `{code, ...}` |
| PATCH | `/api/session/<sid>/commodities/<cid>/qty` | `{code, delta}` |
| DELETE | `/api/session/<sid>/commodities/<cid>` | Ware entfernen |

## Raffle

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/session/<sid>/raffle` | Raffle ausführen → `{ok, mode}` (`mode` = `no_interest` | `wish` | ...) |
| PATCH | `/api/session/<sid>/raffle/<rid>` | `{code, pcode?, waived?, collected?}` |
| GET | `/api/session/<sid>/raffle/result_for/<pid>` | Ergebnis für einen Teilnehmer |

## Site-Admin (Secret)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/admin/data` | Katalog (Items, Participants, Commodities) |
| POST | `/api/admin/items` | Item anlegen |
| DELETE | `/api/admin/items/<key>` | Item löschen |
| POST | `/api/admin/participants` / DELETE `/<name>` | Teilnehmer-Katalog |
| POST | `/api/admin/commodities` / DELETE `/<name>` | Waren-Katalog |
| POST | `/api/admin/uex_import` | UEX-Katalog-Import |
| POST | `/api/admin/verify` | Secret verifizieren |
| POST | `/api/admin/change_secret` | Secret ändern |
| GET | `/api/admin/secret-hint` | Hinweis (gehärtet, M6) |
