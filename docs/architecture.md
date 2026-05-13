# Mikos — Personal OS: Architektura

Headless backend pro správu tasků (pravidelných i nepravidelných) a zdravotních
dat z Garminu. Dashboard renderuje [`MikiMaly/hub`](https://github.com/MikiMaly/hub)
(React + Vite na Cloudflare Pages, mmaly.cz) v privátní sekci.

## 1. Cíle a non-cíle

**Cíle (MVP)**
- Headless REST API pro tasky a Garmin sleep data
- Pravidelné tasky (RRULE) i nepravidelné (one-off)
- Automatická denní synchronizace spánku z Garmin Connect
- Bezpečný vzdálený přístup z `mmaly.cz/private/*` bez veřejného portu doma
- SSO přes Cloudflare Access — jeden login pro hub i Mikos

**Non-cíle**
- Mikos nemá vlastní frontend ani UI — všechno UI vlastní hub
- Multi-user, sdílení
- Vlastní auth (login form, password reset, …) — řeší CF Access
- Kalendář, habits, journal — backlog post-MVP

## 2. Topologie

```
                  ┌──────────────────────────────────────┐
                  │  Browser (desktop / mobil)           │
                  └─────────────────┬────────────────────┘
                                    │ HTTPS
                                    ▼
        ┌───────────────────────────────────────────────────┐
        │  mmaly.cz  —  Cloudflare Pages  (repo: hub)       │
        │  React + Vite SPA                                 │
        │  ├── /                public landing              │
        │  └── /private/*       dashboard (Mikos widgety)   │
        └─────────────────┬─────────────────────────────────┘
                          │  fetch('https://mikos-api.mmaly.cz/...')
                          │  Cookie: CF_Authorization=<jwt>
                          ▼
        ┌───────────────────────────────────────────────────┐
        │  Cloudflare Access  (Zero Trust)                  │
        │  Chrání:                                          │
        │    - mmaly.cz/private/*                           │
        │    - mikos-api.mmaly.cz                           │
        │  Vystavuje Cf-Access-Jwt-Assertion header.        │
        └─────────────────┬─────────────────────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────────────────────┐
        │  Cloudflare Tunnel  (cloudflared, žádný open port)│
        └─────────────────┬─────────────────────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────────────────────┐
        │  Mikos doma — Docker Compose                      │
        │   ┌─────────┐  ┌──────────┐  ┌────────────────┐   │
        │   │   api   │  │  worker  │  │  postgres 16   │   │
        │   │ FastAPI │  │APScheduler│  │                │   │
        │   └────┬────┘  └─────┬────┘  └────────────────┘   │
        │        └──────┬──────┘                            │
        │               ▼                                   │
        │      Garmin Connect (externí, nightly)            │
        └───────────────────────────────────────────────────┘
```

## 3. Komponenty

### 3.1 Hub (mimo tento repo)
- Repo `MikiMaly/hub`, React + Vite, deploy na Cloudflare Pages
- Privátní sekce `/private/*` — Mikos dashboard
- Volá Mikos API přes `fetch`, **žádný sdílený UI package** (hub si komponenty
  kreslí sám podle vlastního design systému)
- API base URL z env (`VITE_MIKOS_API_URL=https://mikos-api.mmaly.cz`)

### 3.2 Mikos API — `api/`
- **FastAPI**, Python 3.12
- **SQLAlchemy 2** + **Alembic**
- **Pydantic v2** schémata
- Žádný session login. Auth = validace `Cf-Access-Jwt-Assertion` header v middleware.
- CORS: povolen origin `https://mmaly.cz`, credentials včetně cookies

### 3.3 Worker — `worker/`
Stejný image jako api, jiný entrypoint:
- Hodinová materializace RRULE → `task_occurrences` (rolling 60denní okno)
- Nightly Garmin sync (06:00 Europe/Prague)
- Retry s exponenciálním backoffem, audit do `sync_runs`

### 3.4 Storage
- **PostgreSQL 16**, volume `pgdata`
- Denní `pg_dump` do `backups/` (samostatný kontejner s cronem)

### 3.5 Edge — `infra/`
- `cloudflared` kontejner s tunnel config (point na `api:8000`)
- Cloudflare Access policy v dashboardu — email rule pro tebe

## 4. Auth contract

**Hub → API:**
1. Uživatel jde na `mmaly.cz/private/dashboard`
2. CF Access zachytí → login (Google / GitHub / email OTP, podle CF nastavení)
3. CF vystaví cookie `CF_Authorization=<jwt>` pro `*.mmaly.cz`
4. SPA volá `fetch('https://mikos-api.mmaly.cz/api/today', { credentials: 'include' })`
5. CF Access propustí jen s platným JWT, do upstream requestu přidá
   `Cf-Access-Jwt-Assertion` header

**Mikos middleware:**
1. Čte `Cf-Access-Jwt-Assertion`
2. Validuje podpis proti JWKS `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`
   (cache 1 h)
3. Ověří `aud` claim = AUD tag aplikace
4. Ověří `email` claim je v allowlistu (z env `MIKOS_ALLOWED_EMAILS`)
5. Bez headeru / nevalidní JWT → 401

**Lokální dev:** middleware má override v `DEV_MODE=1` — přijme všechno z
`localhost`, hub volá `http://localhost:8000` napřímo.

## 5. Datový model

```
users
  id, email (unique), name, timezone, created_at
  -- single-user MVP, ale per-email lookup z JWT

tasks
  id, user_id, title, description, priority, tags[],
  due_at TIMESTAMPTZ NULL,
  rrule TEXT NULL,                  -- RFC 5545
  rrule_start DATE NULL,
  rrule_end DATE NULL,
  status ENUM('active','archived'),
  created_at, updated_at

task_occurrences
  id, task_id, occurs_on DATE, occurs_at TIMESTAMPTZ NULL,
  status ENUM('pending','done','skipped'),
  completed_at TIMESTAMPTZ NULL,
  notes TEXT,
  UNIQUE(task_id, occurs_on)

sleep_sessions
  id, user_id, date DATE,           -- "noc končící tímto datem v user TZ"
  start_at TIMESTAMPTZ, end_at TIMESTAMPTZ,
  duration_seconds INT,
  deep_seconds INT, light_seconds INT, rem_seconds INT, awake_seconds INT,
  score INT NULL,
  hrv_avg_ms FLOAT NULL,
  resting_hr INT NULL,
  raw JSONB,
  source TEXT DEFAULT 'garmin',
  fetched_at TIMESTAMPTZ,
  UNIQUE(user_id, date)

sync_runs
  id, source, started_at, finished_at, status, error TEXT, records_upserted INT

garmin_credentials
  user_id PK, email_enc BYTEA, password_enc BYTEA, session_token_enc BYTEA NULL,
  updated_at
  -- šifrováno Fernet, klíč v MIKOS_FERNET_KEY env
```

## 6. API contract

Base: `https://mikos-api.mmaly.cz`

```
GET    /api/today                       → { tasks: Occurrence[], sleep: Sleep | null }
GET    /api/tasks?status=active
POST   /api/tasks                       { title, due_at | rrule, ... }
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
POST   /api/occurrences/{id}/complete
POST   /api/occurrences/{id}/skip
POST   /api/occurrences/{id}/reschedule { occurs_at }

GET    /api/health/sleep?from=YYYY-MM-DD&to=YYYY-MM-DD
GET    /api/health/sleep/latest

POST   /api/sync/garmin                 → 202 + run_id
GET    /api/sync/runs?source=garmin

POST   /api/settings/garmin             { email, password }   -- upsert creds
GET    /api/settings/garmin/status      → { connected, last_sync_at }
```

Všechny endpointy: JSON in/out, `Cf-Access-Jwt-Assertion` required (nebo
`DEV_MODE=1` lokálně).

## 7. Garmin integrace

- Knihovna [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect)
- Credentials uložené v `garmin_credentials` šifrované Fernet (klíč mimo repo)
- Nightly job: stáhne sleep za poslední 2 noci, upsert podle `(user_id, date)`
- Při změně Garmin API → error do `sync_runs`, GET `/api/sync/runs` to ukáže
  v UI banner
- Abstrakce `HealthSource` interface pro pozdější Whoop / Oura / Apple Health

## 8. Recurrence model

- Task s `rrule` je šablona, neukazuje se sám v Today
- Worker hodinově expanduje RRULE od `today` do `today + 60 dní`, upsert
  pending occurrences
- Edit RRULE: smaž budoucí `pending` occurrences daného tasku → regenerace
- Per-výskyt override (přesun, skip) zůstává — šablona je nemění

## 9. Deployment

`infra/docker-compose.yml`:
```
services:
  api:          FastAPI + uvicorn, expose 8000 jen v interní síti
  worker:       stejný image, entrypoint = scheduler
  db:           postgres:16-alpine, volume pgdata
  cloudflared:  Cloudflare Tunnel, point na api:8000
  backups:      cron kontejner, denní pg_dump → ./backups/
```

`.env` (gitignored):
```
DATABASE_URL=postgresql://...
MIKOS_FERNET_KEY=<base64>
CF_ACCESS_TEAM_DOMAIN=mmaly.cloudflareaccess.com
CF_ACCESS_AUD=<app aud tag z CF dashboardu>
MIKOS_ALLOWED_EMAILS=miki@example.com
TZ=Europe/Prague
DEV_MODE=0
```

**Cloudflare nastavení (mimo kód):**
- DNS: `mikos-api.mmaly.cz` → CNAME na tunnel hostname
- Access application: `mikos-api.mmaly.cz`, policy email = tvůj email
- Druhá Access application: `mmaly.cz/private/*` (totéž)

## 10. Struktura repa

```
mikos/
├── docs/
│   └── architecture.md
├── api/                        (FastAPI)
│   ├── app/
│   │   ├── auth/               (CF Access JWT middleware)
│   │   ├── domain/             (tasks, health — doménové modely)
│   │   ├── adapters/           (garmin, ...)
│   │   ├── api/                (routery)
│   │   ├── db/                 (modely, alembic)
│   │   └── scheduler/          (APScheduler jobs)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── cloudflared/config.yml
│   └── backups/cron
└── README.md
```

## 11. Rozhodnutí

| Otázka | Volba | Důvod |
|---|---|---|
| Frontend | Žije v hub repu (React + Vite) | mmaly.cz už na CF Pages, sdílený design |
| UI sdílení | Žádné — hub volá API a renderuje sám | Minimální coupling, hub má vlastní design system |
| Hosting backendu | Self-hosted Docker doma | Privacy zdravotních dat |
| Vzdálený přístup | Cloudflare Tunnel | Žádný veřejný port, navazuje na CF stack |
| SSO | Cloudflare Access | Zdarma, chrání hub i API jedním loginem |
| Garmin | `python-garminconnect` | Funguje hned, šifrované creds |
| DB | PostgreSQL | RRULE/JSONB queries, robustní |
| Recurrence | RRULE šablona + materializované occurrences | Per-výskyt stav |

## 12. Otevřené otázky

- **Push notifikace** — CF Pages umí Web Push, ale subscribe endpoint by musel
  existovat. Rozhodnout v M3.
- **Schema validace na hraně** — sdílet TS typy mezi api a hub? Buď OpenAPI
  schema → `openapi-typescript` v hub buildu, nebo ručně držet typy. Doporučuju
  OpenAPI generování.
- **Audit log akcí** — pro single-user není nutný, ale low-cost: tabulka
  `audit_events` s JSONB. Rozhodnout dle chuti.

## 13. Roadmap

**M0 — Skeleton (1 den)**
- Repo struktura, Docker Compose, Postgres, prázdné FastAPI s `/health`,
  základ CF Access middleware (čte header, validuje JWT)

**M1 — Tasks (3–5 dní)**
- Models, Alembic, CRUD endpointy, RRULE engine, occurrences worker,
  testy

**M2 — Garmin sleep (2–3 dny)**
- Adapter, šifrované creds, nightly sync, endpointy, error handling

**M3 — Produkce (1–2 dny)**
- Cloudflare Tunnel setup, Access aplikace, OpenAPI schema export pro hub,
  backupy, manuální resync endpoint
