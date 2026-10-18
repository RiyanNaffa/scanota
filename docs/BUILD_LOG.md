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

## LLM efficiency, retry and OCR hint – 2026-10-17

**What was done**
- `app/config.py`: settings for reasoning effort and max tokens (SQL: medium/2048, answer: low/1024, restock rephrase: low/512), retry policy, OCR
- `app/llm.py`: shared client factory, `completion_kwargs`, `call_with_retry` (429, 5xx and connection errors; `Retry-After` honoured, cap 65 s because Tokenfactory sends 60 s; timeouts not retried), `message_text` warns when `max_tokens` cuts a reply. SDK retries are off so the waits do not stack
- `app/chat/service.py`, `app/api/restock.py`: Qwen calls use the token budget and the retry wrapper; restock rephrasing gives up at the first long 429
- `app/extraction/ocr.py`: MinerU2.5-Pro OCR client (`POST {LLM_BASE_URL}/ocr`, `document_url` request, `pages[].markdown` response per the Token Factory docs); its text is a hint in the vision prompt, any OCR failure falls back to the vision model alone
- `app/extraction/client.py`: retry wrapper, OCR hint, and a transport error no longer triggers the parse-feedback retry
- `app/ingest/offline.py`: extraction runs in a worker thread so retry sleeps do not block the event loop
- `dashboard/api_client.py`: 150 s timeout for LLM-backed calls so a 60 s Retry-After wait fits
- `infra/amd/README.md`: vLLM compose is self-hosting only; Tokenfactory needs no compose
- `.env.example`: Tokenfactory URL as a comment, new settings
- `app/db/url.py`: bare `postgresql://` URLs are rewritten to `postgresql+psycopg://`. SQLAlchemy defaulted to psycopg2, which is not installed (only psycopg 3), so the api container crash-looped on start; `.env` keeps the plain libpq form
- `dashboard/Dockerfile`: code now lives at `/app/dashboard` with `PYTHONPATH=/app`. It was copied to `/app`, so every `import dashboard.*` raised ModuleNotFoundError and no page loaded
- `app/db/repository.py`: `get_summary` rendered `WHERE AND t.status = ...` in the top-products query, so `GET /summary` always returned 500; the stray `.replace()` is gone
- `docker-compose.yml`: `./data` mounted read-only into the api container. `data/` was not in the image, so `python -m app.db.seed` would have logged "products.csv not found" and seeded nothing
- `app/validation/confidence.py`: any `ITEM_UNMATCHED` now forces `needs_review`. One unmatched item scores exactly 0.85, equal to the threshold, so it used to be auto-confirmed without an SKU
- `app/extraction/client.py`, `app/config.py`: optional `LLM_MODEL_VISION_FALLBACK`, used per receipt when the vision model fails with 5xx or a timeout after retries (MiniCPM-V-4.7-35B-A3B had no healthy workers on Tokenfactory; DeepSeek-V4.1-Flash read two sample receipts exactly)
- Timeouts: the fallback model timed out at 60 s on a real receipt. Measured on Tokenfactory: the first request to an idle model takes 35-65 s (DeepSeek-V4.1-Flash: 35.7 s then 1.5 s for a 5-token ping; 65 s for a 84-token receipt), later ones 1-3 s. `LLM_TIMEOUT_SECONDS` default 60 -> 120, and `ExtractionClient` now reads it instead of a hardcoded 60. Dashboard LLM timeout 150 -> 300 s (worst case OCR + main + fallback)
- `app/api/ingest.py`: `ExtractionError` -> HTTP 502 with a plain Indonesian message (provider details only in the log); `dashboard/api_client.py` shows the API's `detail` instead of the raw httpx text
- `app/db/init/02-roles.sh` + `.gitattributes`: the script had CRLF endings from the Windows checkout, so the container failed with `env: 'bash\r': No such file or directory` and `scanota_ro` was never created (Postgres skips init scripts once the data volume exists). Script converted to LF, `*.sh text eol=lf` added; role created on the existing volume by running the script (idempotent, no data loss). Verified: login as `scanota_ro`, SELECT on the two views only, raw tables and writes blocked, `POST /chat` answers in 24 s with `reasoning_effort` medium/low accepted by Qwen3.8-27B and no max_tokens warning
- Tests: `test_llm.py`, `test_ocr.py`, `test_extraction_client.py`, `test_chat_budget.py`, `test_db_url.py`, `test_summary.py`, `test_dashboard_client.py`, `test_ingest_receipt_errors.py`

**UNVERIFIED**: whether `/ocr` accepts a base64 data URL as `document_url` (docs only show an https URL), token budgets against the live Qwen3.8-27B endpoint, real 429 behaviour. `MiniCPM-V-4.7-35B-A3B` is kept as the vision model on request, but it is not in the Token Factory doc's model table: check `GET /v1/models`

---

## statsforecast was not running – 2026-10-17

**What was found**
- `import statsforecast` failed in the api image: unpinned `pyarrow` (pulled in via fugue) now needs NumPy 2, while `numpy==1.26.4` is pinned. `_try_import_statsforecast` swallowed the ImportError, so all 38 SKUs silently used the 4-week moving average, labelled `insufficient_history`, and `/restock` never ran TSB or Croston. The same mismatch also crashes pytest at startup in that environment (fugue ships a pytest plugin)

**What was done**
- `app/requirements.txt`: `pyarrow==17.0.0`. After the rebuild `/restock` uses TSB for 23 SKUs and CrostonOptimized for 15, in about 3 s
- `app/forecast/models.py`: the import failure is logged once as a warning; fallbacks carry a `fallback_reason` and a distinct `model_used`; `NIXTLA_ID_AS_COL=1` silences a FutureWarning that fired on every fit
- `app/forecast/service.py`: `data_quality` is `model_unavailable` when the model did not run, `insufficient_history` only for short history
- `tests/unit/test_forecast_models.py`: 8 tests; the real-model test is skipped only when statsforecast is absent and fails when it is installed but broken
- Sigma for safety stock was `std(abs(error))`, the spread of the error sizes, not the size of the errors: on the seeded data it was a median 0.44x of the RMSE (25 of 38 SKUs under half). Now `rmse()` of the signed one-step errors (`app/forecast/metrics.py`, `app/forecast/models.py`). Reorder points rose for all 38 SKUs (median x1.49, max x2.75); no action changed because the seeded stock is far above every reorder point. Tests: `TestRMSE` in `test_forecast.py`, `test_sigma_is_the_rmse_of_one_step_errors` in `test_forecast_models.py` (runs where statsforecast is installed)

**UNVERIFIED / open**
- All 38 SKUs come out `ok` because the seeded stock is well above every reorder point; lower a stock level to see `order_now`

---

## Forecast backtest, sigma window, z calibration – 2026-10-17

**What was done**
- `app/eval/backtest.py` (new; `make backtest` pointed at a module that did not exist): for each SKU and each of the last 26 weeks, using only earlier data, forecast, size a reorder point and compare it with the demand that really arrived during the lead time (daily dates). Scores the 4-week moving-average baseline, the old sigma and RMSE sigma over 8, 13 and 26 weeks. Cross-check: the backtest's sigma equals `forecast_sku`'s (gap 0)
- `app/forecast/models.py`: `make_model`, `predict`, `one_step_forecasts` shared by production and the backtest; `SIGMA_LOOKBACK_WEEKS` 8 -> 26
- README WAPE / stockout table filled from the run; `SAFETY_STOCK_Z` documented in `.env.example`

**Results** (synthetic data, 38 SKUs x 26 weeks, z = 1.65, target about 5% stockouts)

| method | stockout | unmet demand | avg safety stock | z needed for 5% | sigma CV |
|---|---|---|---|---|---|
| 4-week moving average (baseline) | 12.9% | 21.8% | 2.88 | 3.09 | 0.34 |
| old sigma (std of abs errors, 8 wk) | 18.3% | 34.6% | 1.67 | 5.89 | 0.25 |
| RMSE, 8 weeks | 10.0% | 14.0% | 3.51 | 2.37 | 0.17 |
| RMSE, 13 weeks | 9.5% | 13.8% | 3.52 | 2.27 | 0.12 |
| RMSE, 26 weeks (now) | 9.2% | 14.0% | 3.50 | 2.31 | 0.06 |

- Next-week WAPE: 0.765 (statsforecast) vs 0.823 (moving average)
- The sigma fix is what matters: stockouts 18.3% -> 10.0%, unmet demand 34.6% -> 14.0%, for about 2 more units of safety stock per SKU
- Window length barely changes outcomes (differences are inside the noise of 988 overlapping cases), but 26 weeks is about 3x steadier than 8 (CV 0.06 vs 0.17) at the same safety stock, so the window was moved to 26. Cost: `/restock` 3 s -> 6 s
- At z = 1.65 the stockout rate is about 9-10%, not 5%: reaching 5% takes z of about 2.3. Not changed in code because it is a cost / service-level choice (`SAFETY_STOCK_Z`)
- Sparse SKUs (more than 40% zero weeks) are only 3 SKUs, too few to conclude anything

**UNVERIFIED / open**
- Synthetic demand (30% zero weeks, 30% noise, uniform random days) is cleaner than a real shop; the numbers check the method, not real-world accuracy
- The lumpy-arrival effect on short lead times (most SKUs have 1-3 days) is not modelled by `z x sigma x sqrt(lead time)`; the lead<=3d split shows 9.7% vs 7.1% for longer lead times

---


## Per-category z and shelf-life warnings – 2026-10-17

**What was done**
- `app/forecast/category_policy.py` (new): z and `shelf_life_days` per category; `SAFETY_STOCK_Z` (now 2.2) is the fallback for unlisted categories. A test fails if a catalog category has no entry
- `/restock` uses the category z and returns `z`, `shelf_life_days`, `shelf_life_risk` (`watch` above 70% of the shelf life, `high` above 100%), `shelf_life_note` and `order_capped_by_shelf_life`. The suggested order is capped to what can sell before the stock spoils. `data_quality` is unchanged
- Restock page: "Berisiko Kedaluwarsa" metric and warning, shelf-life and risk columns, z in the detail caption
- `app/eval/backtest.py`: per-category table, z needed for 5% / 10% per category, shrinkage toward the pooled z (`suggest_z`, k = 150), per-tier z, and an out-of-sample check (calibrate on the earlier half of the origins, score on the later half)

**Why two tiers and not 13 numbers** (45 origins, 1,710 cases; calibrated on 836, scored on the other 874)

| policy | stockouts overall | goods that keep (target 5%) | shelf life (target 10%) | avg safety stock |
|---|---|---|---|---|
| flat z = 1.65 | 9.6% | 8.5% | 13.0% | 3.51 |
| flat z = 2.14 (pooled 5%) | 6.2% | 5.5% | 8.2% | 4.55 |
| per tier (2.12 / 1.81) | 6.9% | 5.7% | 10.6% | 4.33 |
| per category (shrunk) | 7.7% | 5.8% | 13.5% | 4.23 |

- Per-category estimates rest on 45-225 cases (1-5 SKUs) and did not generalise: the shelf-life goods came out at 13.5% against a 10% target. One z per tier did (5.7% / 10.6%), with 5% less safety stock than a flat 2.14, which over-stocks the goods that spoil (8.2% against 10%)
- Values used on the full period: 2.17 -> 2.2 (keeps), 1.81 -> 1.8 (shelf life). Every category has its own entry so it can be tuned once a real shop has more data
- With these z, the production estimator on the last 26 weeks: 6.2% stockouts and 9.1% unmet demand, against 9.8% and 16.2% for the 4-week moving average at the same z (README table)

**Per category at the configured z** (in-sample, 45 origins): most are at or under target. Semen is the outlier: 14.1% stockouts against 10% (15.6% at z = 1.65), Pipa & Fitting 8.9%, Alat and Kabel & Listrik 6.1% against 5%. Kayu, Keramik and Pasir & Batu are at 1.5-2.2%, i.e. over-stocked relative to target

**UNVERIFIED / open**
- Shelf lives (Semen 90 d, Semen & Plester 180 d, Cat and Waterproofing 365 d) are my rough defaults for sealed stock in a dry store, not supplier data. Confirm them
- The warning compares days of cover with the shelf life. It cannot see how old the stock already is: receiving dates per batch are not recorded, so "nearly expired" in the strict sense is not detectable yet. A stock-receipts table would fix that
- On the seeded stock no product is at risk (cover 38-123 days; the closest, Sika Plafon at 123 of 180 days, is just under the 70% mark). The warning path was run with in-memory stock levels (Semen Holcim 70 -> high, Sika Plafon 30 -> watch); the order cap has unit tests but never bound on real data
- Semen could take a z above its tier value: its 90-day shelf life is about twice its ~45 days of cover, so the shelf-life limit is not what binds there. Not changed because it was not validated out of sample
- Synthetic data, so the stockout rates check the method rather than a real shop

---


## Dashboard redesign, i18n, camera, Evolus removed, OCR evaluation – 2026-10-18

**What was done**
- Evolus removed: `app/evolus/`, `evolus/`, `app/api/evolus.py`, its settings and `.env.example` block, doc rows, `.gitignore` lines. The local `.env` lost its `EVOLUS_*` lines
- `app/main.py`: the routers are imported without `try/except ImportError: pass`, so a broken router stops startup instead of disappearing behind a healthy `/health`. `tests/unit/test_app_routes.py` checks every endpoint is mounted and that a broken import raises
- Chat retry: the rejected SQL is sent back as the assistant turn (it was an empty message, so the model could not see its mistake); when nothing usable came back, no empty assistant turn is sent. `/chat` takes `lang` (id or en) for the answer language
- Shelf lives checked against sources (see `app/forecast/category_policy.py`): cement 90 d (EUROSAC: typically 2-3 months in bags), mortar and tile adhesive 180 d (INSEE and Cement Australia data sheets: 6 months), paint 365 d (PPG about 2 years, Sherwin-Williams about 1 year for some lines: the shorter), waterproofing 365 d (Sika data sheets: 12 months). The values did not change; they now have sources. No Indonesian data sheet was found for cement or paint
- Dashboard rebuilt: `st.navigation` with pages in `dashboard/views/`, Material icons instead of emoji, palette `#000000 / #3e432e / #616f39 / #a7d129` (amber and red only for watch / act now), no animations, `toolbarMode = "viewer"` so there is no Deploy button. The restock page now shows the action, the shelf-life risk and a per-product detail with a sales and forecast chart; the receipt photo on the Needs Review page was requested from the wrong path (`/receipts/..`, the API serves `/transactions/receipts/..`) and never showed, now fixed
- Language switch in the sidebar (flag + ID / EN, flags are inline SVG because Windows browsers draw flag emoji as letters). All text is in `dashboard/strings.py`; `/restock?lang=` returns the reason and shelf-life note in that language. A test checks both languages have the same keys and placeholders and that every validation issue code has a label
- Scan page: upload files or camera. A rerun used to send every uploaded receipt to the model again (and create a duplicate transaction); each image is now scanned once, by hash. The camera widget is created only after choosing "Camera", because Streamlit tabs render all tabs and the browser asked for camera permission on page load
- `app/eval/ocr_eval.py` (`make eval`): scores the 40 sample receipts through the production steps, with and without the OCR hint (README table). 3 receipts are read at once; failed reads are retried
- `tests/unit/test_dashboard_views.py` renders every page in both languages with a fake API (needs Streamlit, so it skips in the API's CI install and runs in the dashboard image)

**OCR evaluation results** (40 synthetic single-item receipts, MiniCPM-V-4.7-35B-A3B)

| | with OCR hint | vision only |
|---|---|---|
| date, total correct | 100% | 100% |
| item F1 (name + qty + line total) | 0.975 | 0.875 |
| right SKU | 100% | 100% |
| wrong printed totals caught | 5 of 5 | 5 of 5 |
| correct receipts flagged | 0 of 35 | 0 of 35 |

- The OCR hint fixed four misread names; the SKU match was 100% either way (fuzzy matching). One receipt (60x120 read as 50x120) is wrong in both
- The first full run was killed halfway: `docker compose up --build dashboard` also rebuilt and recreated `api`, its dependency, and the evaluation was running inside it. Use `--no-deps` for dashboard-only rebuilds. The second run had 5 vision-only calls fail on timeouts and rate limits (the team key is shared); they were re-run and `ocr_eval` now retries failed receipts itself

**UNVERIFIED / open**
- The new look was checked through the DOM (colours, no Deploy button, icons, flags, language switch, camera mode) but not by eye: the browser pane could not take screenshots while the Claude window was minimized
- The camera cannot be tried from here (blocked in the browser pane). On a VM it needs HTTPS; README has a deployment section
- The Needs Review page can only confirm a receipt as it is. It cannot assign a SKU to an unmatched item, so the "corrections become aliases" loop is incomplete
- The API has no authentication and CORS is `*`

---


## Dashboard layout fixes – 2026-10-18

**Reported and fixed**
- The logo overlapped the sidebar toggle: `st.logo` adds a second copy of the image in the page header, which sits on top of the sidebar header when the sidebar is open. The brand is now drawn in the sidebar header with CSS (`::before`, left of the collapse button), and navigation is `st.navigation(position="hidden")` plus `st.page_link` buttons so the order is ours
- Square dark-olive patches (`#191b12` is the card colour at 40% opacity): the card rule was applied to every `stVerticalBlockBorderWrapper`, which Streamlit puts around every block, including the whole page area and the language row. Containers are now border-only (hairline, rounded); only metrics, inputs and the active link have a fill, all padded and rounded. The sidebar is the same black as the page, with a hairline border
- The language card now sits in a bordered, padded, rounded container on the sidebar's own background, and the API status has 20 px of room above it
- Also: icons in the sidebar links (`st.page_link` does not take the page icon by itself), the active page is marked in the palette, Streamlit's blue/green/yellow alerts are restyled in the palette, long metric values wrap instead of being cut with an ellipsis, a missing shelf life is a dash instead of the word None
- Docs: `docs/amd-proof.md` is no longer promised (the project uses AMD Token Factory, which is hosted; there is no AMD machine to take `rocm-smi` or vLLM logs from). README, architecture and the contributing guide now describe Token Factory as the setup and `infra/amd/` as an optional overlay that is not used

**Checked** in the browser pane with screenshots this time (sidebar open and collapsed, hover on the header) and a DOM audit that lists every filled element with its corner radius: no square fills remain apart from the inner field of the date inputs, which sits inside a rounded box

---


## Dashboard: menu, upload limit, loading, demo data, language switch – 2026-10-18

**What was done**
- The three-dot menu (Rerun, Settings, Print, Record a screencast, About) is gone: `toolbarMode = "minimal"` (it was "viewer", which still shows it). The element is absent from the page
- 10 MB per photo: `server.maxUploadSize = 10` (the uploader now says "Limit 10MB per file"), `MAX_UPLOAD_MB` in the API settings and `.env.example`, a note under the uploader, and a test that the dashboard config, the dashboard constant and the API setting agree. The Caddy limit is 12 MB so a 10 MB photo plus the multipart envelope is not cut off before the dashboard can answer
- Loading feedback: the Restock and Overview pages show a spinner with a message while the forecast runs (it takes 5-10 s). Cause of the blank page: the sidebar waited for the API health check before the page started, and the page itself showed nothing until the forecast returned. The health check is now bounded (2 s, kept for 10 s). `restock_cached` keeps the forecast for a minute, cleared after a stock update, a scan or a confirm (a stock update now also reloads the page, so the table shows the new stock)
- README: a "Demo data" section (the deployment runs on synthetic data; `make demo-data`, or `docker compose exec api python -m app.db.seed` where make is missing; what is loaded and what is not; safe to run twice) and the Caddy example with basic auth and the 12 MB limit. The old line "loads sample receipts and online orders" was wrong: the seed loads products, online orders and offline sales, while the receipt photos are for scanning
- Language switch: on a phone the flags sat above full-width buttons (Streamlit stacks columns below 640 px) and on desktop the flags sat low. Now two equal buttons forced into one row, with the flag drawn inside each button, so it is centred with the label. A segmented control was tried first and dropped: its button sizes are locked by Streamlit's generated classes

**Found while checking**
- The `api` and `db` containers had exited (code 0) about 13 minutes before: the dashboard then showed "API tidak terhubung". Started again with `docker compose up -d db api`; the data was intact (38 products, 3,546 transactions)

**Checked** in the browser pane: menu absent, "Limit 10MB per file" in the uploader, the spinner on Restock, the language card on desktop (two 110 px buttons, 8 px apart, flag and label centred) and at 375 px (same row, 92 px each). The sidebar would not open in the emulated phone view, so that last check forced it open with CSS

**UNVERIFIED**
- A 10 MB+ upload was not tried through Caddy; the limit is checked by configuration and tests, not by an upload
- `st.cache_data` is per server process: with several Streamlit workers each keeps its own copy for a minute

---


## Dashboard: loading on every page, scan buttons – 2026-10-18

**What was done**
- Loading: no page is empty while it waits any more. `st.spinner` with a message now wraps the Review list, the receipt and the confirm call, and the Transactions list (Overview, Restock, Ask and the scan itself already had one). `app.py` shows "Memuat halaman..." while it checks the API, which covers the pages that load nothing themselves (Scan, Ask). A test lists every message and checks it is wired into its page
- Photo source switch ("Unggah berkas" / "Kamera"): the two buttons were as wide as their content, anchored left and uneven (137 and 95 px), with the icon touching the label. Streamlit gives the group `max-width: fit-content` and its flex children stayed icon-wide, so the group is a two-column grid now: equal buttons, 10 px between icon and label, full width on a phone, 520 px at most on a desktop. The label also sat 8 px below the icon, because its markdown container has a -1rem bottom margin; that is reset
- "Scan N nota" and "Mulai ulang": they were the first two of `st.columns([2, 2, 5])`, so they shrank with the window (about 100 px at an 830 px window with the menu open) until Streamlit stacked them at 640 px. They now sit in an `actions_*` container: 220 px each, never narrower than 190 px, wrapping onto a second line when the row is too narrow, full width on a phone. The Review page's "Konfirmasi tanpa perubahan" and "Lewati" row had the same problem and uses the same container, with a wider first button because that label is longer than 220 px

**Checked** in the browser pane with the API container paused: the "Memuat riwayat transaksi...", "Memuat nota yang perlu dicek..." and "Loading the page..." messages appear under the title while the API does not answer. Layout measured at 1100 and 760 px (two 256 px source buttons, two 220 px action buttons), 830 px with the menu open (227 px and 220 px) and 375 px (two 165 px source buttons 8 px apart, full-width stacked actions); icon, label and button centres are on the same line

**Found while checking**
- The first visit to a deep link (for example `/scan`) after the dashboard container starts shows Streamlit's "Page not found ... Running the app's main page" dialog, while the right page is rendered behind it; a second load is clean. Seen twice, right after a restart. It looks like Streamlit not knowing the `st.navigation` paths until one session has run, so it only affects the first visitor after a restart. Not changed

**UNVERIFIED**
- The Review page could not be seen with data: the demo data has no receipt waiting for review, so its spinners were checked by the test that wires them in and its button row only by the CSS rule, not on screen
- The `actions_*` wrap was checked down to a main column of about 430 px; a window narrower than that with the menu open was not tried

---


## Documentation review – 2026-10-18

Every Markdown file was read against the code, the compose file, the Makefile, CI and the running stack. This log is append-only, so the old entries that are no longer true (Phase 1 "Port 5432 not published by default", Phase 9 Evolus) are left as history and corrected here.

**Changed**
- `README.md`: the setup line named `LLM_MODEL`, which no longer exists (the names are `LLM_MODEL_VISION` and `LLM_MODEL_TEXT`, with defaults); the chat is described as Indonesian or English; the test row of the layout lists what is tested now; the "Postgres is not published" claim is replaced by what the compose file now does (see below)
- `docs/architecture.md`: the diagram and component table show the OCR hint; the dashboard is Indonesian and English; the dashboard's LLM timeout is 300 s (it said 150 s); a leftover sentence said the Deploy button is hidden with `toolbarMode = "viewer"` while the file says `"minimal"`
- `infra/amd/README.md`, `.env.example`: still called Token Factory "development" and a self-hosted vLLM the "final demo"; it is the current setup and the vLLM overlay is optional
- `CONTRIBUTING.md`: how to run the dashboard tests (below), that lint covers `app` and `tests` only, and a row for the loading message of a new slow call
- `SECURITY.md`: the dashboard has no login of its own

**Found while checking**
- `docker-compose.yml` has `ports: "${POSTGRES_PORT:-}:5432"` for `db`. With the variable empty Docker publishes Postgres on a random host port on all interfaces (it showed as `0.0.0.0:56948->5432`), so the README claim that it is not published was wrong. Fixed: the mapping is now `127.0.0.1:${POSTGRES_PORT:-}:5432`, so Postgres is reachable from the machine only (checked: `docker compose ps` shows `127.0.0.1:51208->5432` and the API still answers, with the data intact). `POSTGRES_PORT` now fixes the local port instead of exposing it; the README and `.env.example` say so. The API (8000) and the dashboard (8501) are still published on all interfaces, as the README says
- The dashboard view tests are skipped by `make test` and by CI, because Streamlit is not in `app/requirements-dev.txt`; they only run in the dashboard image. CI also lints `app` and `tests` but not `dashboard`
- An empty directory `tests;C` had been created in the repository root by a Docker mount whose Windows path was cut at the colon. Removed
- `CONTRIBUTING.md` says not to push to `main` directly, while the work so far went straight to `main`

**UNVERIFIED**
- The `$(pwd)` form of the dashboard test command in `CONTRIBUTING.md` was not run; the run used the same command with explicit Windows paths and `MSYS_NO_PATHCONV=1`

---


## API and dashboard bound to 127.0.0.1 – 2026-10-18

**What was done**
- `docker-compose.yml`: the API and the dashboard are published as `127.0.0.1:8000:8000` and `127.0.0.1:8501:8501`, like Postgres, so only a reverse proxy on the VM (or an SSH tunnel) reaches them. Before, `8000:8000` and `8501:8501` listened on every interface, and the README only asked for a closed firewall
- README: "Only the proxy faces the network" replaces "Expose only the proxy": what is bound where, the SSH tunnel for use without the proxy, and that a proxy in a container must join the compose network and use `dashboard:8501`. The camera note no longer names `http://<vm-ip>:8501`, which is no longer reachable

**Checked** after recreating the two containers: `docker compose ps` shows `127.0.0.1:8000`, `127.0.0.1:8501` and `127.0.0.1:51208` (db); `/health` answers on `127.0.0.1`, the dashboard answers on `localhost`, and its Overview page loads with the API status "API terhubung", so the dashboard still reaches the API as `api:8000` inside the network. A request to this machine's `172.31.192.1` address on both ports got no answer, but that is a virtual adapter, not necessarily the LAN address, so the binding shown by `docker compose ps` is the real evidence

**UNVERIFIED**
- Not tried from another machine, and not with Caddy on the VM: the Caddyfile in the README still points at `localhost:8501`, which a loopback binding serves, but that was reasoned, not run
- `localhost` in a browser can resolve to `[::1]`; the dashboard answered on `localhost` here (Docker Desktop on Windows), and a Linux VM was not tried

---
