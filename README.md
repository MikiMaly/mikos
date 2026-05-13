# Mikos

Personal OS — single-user dashboard pro správu tasků (pravidelných i nepravidelných)
a vizualizaci zdravotních dat z Garminu.

## Status

Návrh architektury. Viz [`docs/architecture.md`](docs/architecture.md).

## Stack (plánovaný)

- **Frontend:** Next.js + Tailwind + shadcn/ui (responsive web + PWA)
- **Backend:** FastAPI (Python 3.12) + PostgreSQL 16
- **Worker:** APScheduler — RRULE materializace + nightly Garmin sync
- **Garmin:** `python-garminconnect` (neoficiální)
- **Deploy:** Docker Compose, self-hosted, přístup přes Tailscale

## MVP scope

- Tasky: one-off i recurring (RFC 5545 RRULE)
- Garmin sleep: noční sync, dashboard card, 7d/30d trendy
