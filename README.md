# Mikos

Headless backend pro osobní OS — tasky (pravidelné i nepravidelné) a Garmin
sleep data. Frontend žije v [`MikiMaly/hub`](https://github.com/MikiMaly/hub)
(mmaly.cz, privátní sekce).

## Status

**M0 — Skeleton hotový.** Dál: M1 (tasky), M2 (Garmin sleep), M3 (CF Tunnel).
Viz [`docs/architecture.md`](docs/architecture.md) sekce 13 — Roadmap.

## Stack

- **Backend:** FastAPI (Python 3.12) + PostgreSQL 16 + SQLAlchemy 2 + Alembic
- **Worker:** APScheduler — RRULE materializace + nightly Garmin sync
- **Garmin:** `python-garminconnect` (M2)
- **Deploy:** Docker Compose, self-hosted doma
- **Edge:** Cloudflare Tunnel (M3, bez veřejného portu)
- **Auth:** Cloudflare Access (SSO, chrání hub i API jedním loginem)

## Lokální dev

```bash
cd infra
cp .env.example .env       # DEV_MODE=1 přeskočí JWT validaci
docker compose up --build
```

Smoke test:
```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/api/whoami
# {"email":"dev@local"}
```

## Struktura

```
mikos/
├── docs/architecture.md       Návrh architektury
├── api/                       FastAPI + worker
│   ├── app/
│   │   ├── auth/cf_access.py  CF Access JWT validace
│   │   ├── api/health.py      /health + /api/whoami
│   │   ├── db/                SQLAlchemy base, session, modely
│   │   └── scheduler/main.py  APScheduler worker entrypoint
│   ├── alembic/               DB migrace
│   ├── pyproject.toml
│   └── Dockerfile
└── infra/
    ├── docker-compose.yml
    └── .env.example
```
