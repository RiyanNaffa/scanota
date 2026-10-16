# scanota Build Log

> Append-only. One entry per phase. Format: `## Phase N – YYYY-MM-DD`.

---

## Phase 0 – 2025-07-14

**Environment facts**

| Item | Value |
|---|---|
| OS | Microsoft Windows NT 10.0.26200.0 |
| Python | 3.12.4 (spec asks 3.11; 3.12 is a strict superset — all code will be written for 3.11 compat syntax; noted as deviation) |
| Docker | 29.8.2, build 7fc2dff |
| Docker Compose | v5.5.1 |
| Git branch | main |
| Last commit | eba1588 Initial commit |

**What was done**
- Read all protected files: README.md, .env.example, .gitignore, .editorconfig, LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md.
- Created the full directory skeleton from Section 4 of INITIAL_BUILD_PROMPT.md.
- Added `__init__.py` to every Python package dir: `app/`, `app/ingest/`, `app/extraction/`, `app/validation/`, `app/forecast/`, `app/chat/`, `app/evolus/`, `app/db/`, `app/api/`, `app/eval/`, `app/synth/`, `tests/`, `tests/unit/`, `tests/integration/`.
- Added `.gitkeep` to empty dirs: `data/sample_receipts/`, `data/sample_transactions/`, `data/fonts/`, `notebooks/`, `evolus/`, `infra/amd/`, `docs/results/`.
- Created this file.

**Decisions**
- Python 3.12.4 used on the host (not 3.11). The app Dockerfile will use `python:3.11-slim` as specified to keep production consistent.

**Deviations**
- Python 3.12.4 on host vs spec 3.11. All code will remain compatible with 3.11 syntax.

**UNVERIFIED items (this phase)**
- None.

**Open questions**
- None.

---

## Phase 1 – 2025-07-14

**What was done**
- Wrote `app/db/schema.sql` (4 tables, 2 views, indexes per spec)
- Wrote `app/db/init/02-roles.sh` (idempotent, creates `scanota_ro`)
- Wrote `docker-compose.yml` (db service, api, dashboard stubs)
- Wrote `Makefile` with all required targets
- Appended `POSTGRES_RO_PASSWORD` to `.env.example`
- Ran all Phase 1 acceptance checks: 4 tables, 2 views, RO role blocks writes

**Decisions**
- Removed obsolete `version: "3.9"` from compose (Docker Compose v5 warns)
- Port 5432 not published by default (controlled via `POSTGRES_PORT` env var)

**UNVERIFIED**: None

---

## Phase 2 – 2025-07-14

**What was done**
- `app/config.py`: pydantic-settings with all env vars
- `app/db/session.py`: dual engines (owner + read-only)
- `app/main.py`: FastAPI factory with incremental router loading
- `app/api/health.py`: GET /health with real DB check
- `app/requirements.txt`, `app/requirements-dev.txt`: pinned versions
- `app/Dockerfile`: python:3.11-slim, non-root user
- `pyproject.toml`: ruff config and pytest markers
- `tests/unit/test_config.py` (4 tests), `tests/integration/test_health.py`

**Results**: 4 unit tests pass, lint clean

---

## Phase 3 – 2025-07-14

**What was done**
- `app/validation/money.py`: parse_rupiah (Indonesian Rupiah formats)
- `app/validation/rules.py`: 6 rule functions with Issue dataclass
- `app/validation/matching.py`: normalize + fuzzy match via rapidfuzz
- `app/validation/confidence.py`: deterministic confidence scoring
- `app/validation/pipeline.py`: orchestrates all validation
- `tests/unit/test_validation.py`: 68 test cases (all green)

**Results**: 68 tests pass, lint clean

---

## Phase 4 – 2025-07-14

**What was done**
- `app/db/repository.py`: all DB access functions
- `app/ingest/online.py`: webhook + CSV ingestion
- API routers: ingest, transactions, review, products, summary

**UNVERIFIED**: Integration tests require running DB+API containers

---

## Phase 5 – 2025-07-14

**What was done**
- `app/extraction/schema.py`: Pydantic models for LLM output
- `app/extraction/preprocess.py`: OpenCV deskew/CLAHE/resize
- `app/extraction/prompts.py`: system and user prompts (Appendix A)
- `app/extraction/client.py`: ExtractionClient with retry
- `app/extraction/service.py`: orchestrates preprocess+extract+validate
- `app/ingest/offline.py`: save image, extract, persist
- Receipt endpoint in `app/api/ingest.py`

**UNVERIFIED**: Live LLM endpoint (LLM_BASE_URL not set)

---

## Phase 6 – 2025-07-14

**What was done**
- `app/synth/catalog.py`: 40 SKUs across 9 categories
- `app/synth/generate.py`: deterministic 78-week CSV generation (SEED=42)
- `app/synth/render_receipts.py`: 40 PNG receipts with ground_truth.json
- `app/db/seed.py`: idempotent seed loader

**Results**:
- Generated 3034 offline rows, 510 online rows (78 weeks)
- Rendered 40 receipts (5 with intentional errors)
- Files in data/sample_receipts/ and data/sample_transactions/

---

## Phase 7 – 2025-07-14

**What was done**
- `app/forecast/metrics.py`: wape, bias
- `app/forecast/policy.py`: all policy functions
- `app/forecast/models.py`: statsforecast wrapper (TSB/Croston/WindowAverage)
- `app/forecast/service.py`: builds restock list
- `app/api/restock.py`: GET /restock, GET /restock/{sku_id}/series
- `tests/unit/test_forecast.py`: 20 policy/metrics tests

**UNVERIFIED**: statsforecast install (timed out locally; present in app/requirements.txt for Docker)

---

## Phase 8 – 2025-07-14

**What was done**
- `app/chat/sql_guard.py`: sqlglot-based SQL guard (30+ test cases)
- `app/chat/prompts.py`: Indonesian-aware system prompts
- `app/chat/service.py`: question→SQL→execute→answer pipeline
- `app/api/chat.py`: POST /chat endpoint
- `tests/unit/test_sql_guard.py`: 33 guard test cases (all green)

**Results**: 121 unit tests total (all green)

---

## Phase 9 – 2025-07-14

**What was done**
- `evolus/endpoints.yaml`: TO_CONFIRM placeholders
- `app/evolus/client.py`: httpx client with retry and call counter
- `app/evolus/mapper.py`: field-mapping driven response mapper
- `app/api/evolus.py`: GET /evolus/stats
- `evolus/README.md`: setup guide

**UNVERIFIED**: All Evolus live endpoints (TO_CONFIRM)

---

## Phase 10 – 2025-07-14

**What was done**
- `dashboard/.streamlit/config.toml`: dark green theme
- `dashboard/theme.py`: CSS injection, fmt_rupiah, badges
- `dashboard/api_client.py`: HTTP client wrapping all API endpoints
- `dashboard/app.py`: Ringkasan page (KPIs, chart, top products, restock)
- `dashboard/pages/1_Scan_Nota.py`
- `dashboard/pages/2_Perlu_Dicek.py`
- `dashboard/pages/3_Restock.py`
- `dashboard/pages/4_Tanya_Data.py`
- `dashboard/pages/5_Transaksi.py`
- `dashboard/Dockerfile` + `dashboard/requirements.txt`

**UNVERIFIED**: Visual review in browser; requires `make up && make demo-data`

---

## Phase 11 – 2025-07-14

**What was done**
- `infra/amd/docker-compose.vllm.yml`: ROCm vLLM overlay compose
- Compose config validates: `docker compose -f docker-compose.yml -f infra/amd/docker-compose.vllm.yml config`

**UNVERIFIED**: AMD GPU hardware run, ROCm version, actual vLLM image tag

---

## Phases 12-13 – 2025-07-14

**What was done**
- `docs/architecture.md`: Mermaid diagram, component table, security layers
- `.github/workflows/ci.yml`: push/PR CI on Python 3.11
- Total unit tests: 121 (all green)
- Lint: ruff check — all checks passed

**UNVERIFIED**: OCR evaluation (needs live LLM), backtest (needs statsforecast in Docker), browser visual review

---
