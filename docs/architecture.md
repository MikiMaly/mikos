# Mikos — Personal OS: Architektura

Single-user osobní operační systém pro správu tasků (pravidelných i nepravidelných)
a vizualizaci zdravotních dat z Garminu (MVP: spánek).

## 1. Cíle a non-cíle

**Cíle (MVP)**
- Jeden dashboard: "Co mám dnes" — tasky + včerejší spánek + 7d trend
- Pravidelné tasky (RRULE: daily / weekly / custom) i ad-hoc tasky
- Automatická denní synchronizace spánku z Garmin Connect
- Self-hosted, data lokálně, přístup z desktopu i mobilu (responsive web)

**Non-cíle (zatím)**
- Multi-user, sdílení, kolaborace
- Kalendář sync (Google/CalDAV) — později
- Habit tracking, journal — později
- Native mobile aplikace — později (PWA stačí)
- Real-time spolupráce

## 2. High-level topologie

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (desktop / mobil)                │
│                     Next.js — responsive web                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS (REST + JSON)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│   Reverse proxy (Caddy / nginx) — TLS, auth gate            │
└──────────────────────────────┬──────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────────┐    ┌──────────────┐
│  API server  │      │   Scheduler /    │    │  PostgreSQL  │
│   FastAPI    │◄────►│   Worker         │◄──►│      16      │
│              │      │   APScheduler    │    │              │
└──────┬───────┘      └────────┬─────────┘    └──────────────┘
       │                       │
       │                       │  nightly @ 06:00
       │                       ▼
       │              ┌────────────────────┐
       └─────────────►│  GarminAdapter     │
                      │  python-garmin-    │
                      │  connect           │
                      └────────┬───────────┘
                               │
                               ▼
                      Garmin Connect (externí)
```

Vše v Docker Compose. Vzdálený přístup přes Tailscale (preferováno — žádný
veřejný port) nebo Cloudflare Tunnel.

## 3. Komponenty

### 3.1 Frontend — `web/`
- **Next.js** (App Router), TypeScript
- **TanStack Query** pro server state
- **shadcn/ui** + Tailwind
- **PWA** manifest + service worker (offline cache dashboardu)

Klíčové stránky:
- `/` — Today: dnešní výskyty tasků + sleep card + quick add
- `/tasks` — všechny tasky, filtry, recurrence editor
- `/health/sleep` — detail + trendy (7d / 30d / 90d)
- `/settings` — Garmin login, nastavení sync

### 3.2 Backend — `api/`
- **FastAPI**, Python 3.12
- **SQLAlchemy 2** + **Alembic** migrations
- **Pydantic v2** schémata
- Auth: jednoduchý session cookie (single-user, žádné OAuth)

### 3.3 Scheduler — `worker/`
Sdílený codebase s API, ale samostatný proces v Compose:
- Materializace RRULE → konkrétní `task_occurrence` rows (rolling 60denní okno)
- Nightly Garmin sync (06:00 lokální čas)
- Retry policy s exponenciálním backoffem

### 3.4 Storage
- **PostgreSQL 16** — primární store
- **Volume** pro `pgdata`, denní `pg_dump` do `backups/` (samostatný kontejner s cronem)

## 4. Datový model

```
users                          (single row — single user, ale schéma připravené)
  id, name, timezone, created_at

tasks                          (definice — pro recurring i one-off)
  id, user_id, title, description, priority, tags[],
  due_at TIMESTAMPTZ NULL,     -- one-off task má due_at, recurring má NULL
  rrule TEXT NULL,             -- RFC 5545 (např. "FREQ=WEEKLY;BYDAY=MO,WE")
  rrule_start DATE NULL,
  rrule_end DATE NULL,
  status ENUM('active','archived'),
  created_at, updated_at

task_occurrences               (materializované výskyty — co je v daný den "to do")
  id, task_id, occurs_on DATE, occurs_at TIMESTAMPTZ NULL,
  status ENUM('pending','done','skipped'),
  completed_at TIMESTAMPTZ NULL,
  notes TEXT,
  UNIQUE(task_id, occurs_on)

sleep_sessions                 (Garmin sleep — denní záznam)
  id, user_id, date DATE,      -- "noc končící touto datem"
  start_at TIMESTAMPTZ, end_at TIMESTAMPTZ,
  duration_seconds INT,
  deep_seconds INT, light_seconds INT, rem_seconds INT, awake_seconds INT,
  score INT NULL,              -- Garmin sleep score 0–100
  hrv_avg_ms FLOAT NULL,
  resting_hr INT NULL,
  raw JSONB,                   -- celý payload pro pozdější use-cases
  source TEXT DEFAULT 'garmin',
  fetched_at TIMESTAMPTZ,
  UNIQUE(user_id, date)

sync_runs                      (audit log pro nightly job)
  id, source, started_at, finished_at, status, error TEXT, records_upserted INT
```

**Proč materializovat occurrences místo počítat RRULE on-the-fly:**
- Stav (done/skipped) musí být per-výskyt — nestačí RRULE definice
- Rychlé dotazy "co je dnes" / "co bylo tento týden" bez expanze pravidla
- Trade-off: trochu složitější logika při editaci RRULE (regenerace budoucích occurrences)

## 5. API design (klíčové endpointy)

```
GET    /api/today                       → { tasks: [...occurrences], sleep: {...} }
GET    /api/tasks?status=active
POST   /api/tasks                       { title, due_at | rrule, ... }
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
POST   /api/occurrences/{id}/complete
POST   /api/occurrences/{id}/skip

GET    /api/health/sleep?from=...&to=...
GET    /api/health/sleep/latest

POST   /api/sync/garmin                 → vynucený resync (manuálně z UI)
GET    /api/sync/runs                   → historie sync jobů
```

## 6. Garmin integrace

**Knihovna:** [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect)
(unofficial, login Garmin Connect účtem).

**Flow:**
1. V `/settings` user zadá Garmin email + heslo → uloženo zašifrovaně v DB
   (Fernet key v `.env`, mimo repo)
2. `GarminAdapter` se přihlásí, drží session token (refresh při expiraci)
3. Nightly job (06:00 lokálního času uživatele) stáhne sleep data za poslední 2 noci
   (idempotentní upsert podle `(user_id, date)`)
4. Při změně API knihovny → fallback: log error do `sync_runs`, UI ukáže warning banner

**Bezpečnost:** Credentials nikdy nelogovat, šifrovat at-rest, žádné odesílání mimo
lokální stack.

**Abstrakce:** `HealthSource` interface (`fetch_sleep(date_range) -> list[SleepRecord]`),
ať pozdější přidání Whoop / Oura / Apple Health nevyžaduje refactor.

## 7. Recurrence model (detail)

- Task s `rrule` je "šablona", neukazuje se sám v Today view
- Worker každou hodinu spustí `materialize_occurrences()`:
  - Pro každý active recurring task expanduje RRULE od `today` do `today + 60 dní`
  - Upsertem (`task_id`, `occurs_on`) doplní chybějící pending occurrences
  - Neměnit existující dokončené ani manuálně upravené
- Edit RRULE: smazat budoucí pending occurrences daného tasku → regenerace
- Edit jednoho výskytu (např. přesun jen tohoto): override flag, nedotčen šablonou

## 8. Deployment

`docker-compose.yml`:
```
services:
  web:        Next.js (build → standalone)
  api:        FastAPI + uvicorn
  worker:     stejný image jako api, jiný entrypoint
  db:         postgres:16-alpine, volume pgdata
  caddy:      reverse proxy + auto TLS (pro Tailscale není potřeba, jen pro CF tunnel)
  backups:    cron kontejner, denní pg_dump → ./backups/
```

**Vzdálený přístup (doporučeno):** Tailscale — žádný veřejný port, žádné TLS
certifikáty, telefon i laptop ve stejné tailnet, přístup přes
`http://mikos.tail-scale.ts.net`.

**Konfigurace:** `.env` (gitignored) — `DATABASE_URL`, `GARMIN_FERNET_KEY`,
`SESSION_SECRET`, `TZ`.

## 9. Struktura repa

```
mikos/
├── docs/
│   └── architecture.md       (tento dokument)
├── api/                      (FastAPI + Alembic)
│   ├── app/
│   │   ├── domain/           (tasks, health — čisté doménové modely)
│   │   ├── adapters/         (garmin, …)
│   │   ├── api/              (routery)
│   │   ├── db/               (models, migrations)
│   │   └── scheduler/        (APScheduler jobs)
│   └── pyproject.toml
├── web/                      (Next.js)
│   ├── app/
│   ├── components/
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   └── caddy/Caddyfile
└── README.md
```

## 10. Roadmap

**M0 — Kostra (1–2 dny práce)**
- Repo skeleton, Docker Compose, Postgres, prázdné Next.js + FastAPI, health check

**M1 — Tasky (3–5 dní)**
- CRUD tasků, RRULE, materializace occurrences, Today view, complete/skip

**M2 — Garmin sleep (2–3 dny)**
- Adapter, nightly sync, šifrované credentials, sleep card na dashboardu, detail stránka

**M3 — Polish (1–2 dny)**
- PWA manifest, backupy, error states, manuální resync button

**Backlog (post-MVP):** kalendář sync, HRV/steps/stress, habit tracking, journal,
korelace spánek ↔ task completion, push notifikace.

## 11. Klíčová rozhodnutí (rozhodnuto)

| Otázka | Volba | Důvod |
|---|---|---|
| Hosting | Self-hosted Docker | Privacy zdravotních dat, plná kontrola |
| Klient | Responsive web + PWA | Jeden codebase, mobil i desktop |
| Garmin | `python-garminconnect` | Funguje hned, žádný schvalovací proces |
| MVP scope | Tasks + sleep | Minimální, rychle do produkce |
| Recurrence | RFC 5545 RRULE + materializované occurrences | Standard + per-výskyt state |
| Backend lang | Python | Ekosystém pro Garmin + datové práce |
| DB | PostgreSQL | RRULE/JSONB/time-range queries, robustní |

## 12. Otevřené otázky

- Push notifikace na mobil — Web Push (potřebuje veřejnou URL, ne čistý Tailscale) vs.
  jen in-app reminders. Rozhodnout v M3.
- Šifrování Garmin credentials — Fernet symmetric key v `.env` stačí pro single-user
  scénář; pokud bys chtěl víc, integrace s `pass` / 1Password CLI při startu.
- Timezone handling — všechno v UTC v DB, převod na user TZ na hraně API. Sleep
  `date` = "noc končící tímto datem v user TZ".
