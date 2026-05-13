# Mikos

Headless backend pro osobní OS — tasky (pravidelné i nepravidelné) a Garmin
sleep data. Frontend žije v [`MikiMaly/hub`](https://github.com/MikiMaly/hub)
(mmaly.cz, privátní sekce).

## Status

Návrh architektury. Viz [`docs/architecture.md`](docs/architecture.md).

## Stack (plánovaný)

- **Backend:** FastAPI (Python 3.12) + PostgreSQL 16
- **Worker:** APScheduler — RRULE materializace + nightly Garmin sync
- **Garmin:** `python-garminconnect` (neoficiální)
- **Deploy:** Docker Compose, self-hosted doma
- **Edge:** Cloudflare Tunnel (bez veřejného portu)
- **Auth:** Cloudflare Access (SSO, chrání hub i API jedním loginem)

## MVP scope

- Tasky: one-off i recurring (RFC 5545 RRULE)
- Garmin sleep: noční sync, REST endpointy pro hub dashboard
