# scanota Architecture

## System Overview

```mermaid
graph TD
    A[Paper Receipt Photo] -->|POST /ingest/receipt| B[FastAPI Backend]
    C[Online Order JSON/CSV] -->|POST /ingest/online| B
    B -->|preprocess + vision LLM| D[Extraction]
    D -->|deterministic rules| E[Validation]
    E --> F[(PostgreSQL)]
    F -->|SQLAlchemy| G[API Routers]
    G -->|HTTP JSON| H[Streamlit Dashboard]
    G -->|read-only SQL| I[Chat LLM]
    F -->|statsforecast| J[Forecast Engine]
    J --> G
    I --> G
```

## Components

| Component | Technology | Purpose |
|---|---|---|
| Backend | FastAPI + Uvicorn | REST API, business logic |
| Database | PostgreSQL 16 | Transactions, products, aliases |
| Extraction | Vision LLM (OpenAI-compat) | Receipt OCR |
| Preprocessing | OpenCV | Deskew, CLAHE, resize |
| Validation | Pure Python (rules.py) | Math checks, fuzzy matching |
| Forecast | statsforecast (Croston/TSB) | Demand forecast |
| Chat | Text LLM + sqlglot | Read-only text-to-SQL |
| Dashboard | Streamlit | Indonesian dark-green UI |
| Inference | AMD Token Factory (OpenAI-compatible API) | Vision, text and OCR models |

## LLM vs Math Boundary

**LLMs read and explain. Math validates and predicts.**

- LLMs: extract text from receipt images, translate questions to SQL, rephrase explanations
- Math/deterministic: ALL validation rules, fuzzy matching scores, confidence scoring, forecasting, safety stock, reorder point calculations

## Security Layers

1. **SQL Guard** (`sqlglot` AST): blocks DML/DDL, restricts to 2 allowed views, deny-lists dangerous functions
2. **DB Read-only Role** (`scanota_ro`): `default_transaction_read_only=on`, SELECT only on `sales_flat` and `products_public`, `statement_timeout=5s`
3. **No secrets in repo**: all keys via env vars

## AMD Deployment

```
AMD Token Factory (AMD Radeon Cloud, AMD GPUs)
  ├── vision model (MiniCPM-V-4.7-35B-A3B, optional fallback DeepSeek-V4.1-Flash)
  ├── text model (Qwen3.8-27B)
  └── OCR model (MinerU2.5-Pro, POST /ocr)
        ↑ OpenAI-compatible HTTP API (LLM_BASE_URL, LLM_API_KEY)
scanota backend
```

`infra/amd/` holds an optional vLLM-on-ROCm overlay for self-hosting. The current setup does not
use it. To switch to your own vLLM, change `LLM_BASE_URL` (and the model names) in `.env` and set
`OCR_ENABLED=false`, because vLLM has no `/ocr` route. See `infra/amd/README.md`.

## Dashboard

- Streamlit multipage app: `dashboard/app.py` sets up the page and `st.navigation`; the pages are in `dashboard/views/`. Navigation is `st.navigation(position="hidden")` plus `st.page_link` buttons in the sidebar, rather than the `pages/` folder, so titles and icons follow the chosen language and the sidebar order is ours (brand, pages, language card, API status).
- **Language:** all text is in `dashboard/strings.py` (Indonesian default, English). The sidebar switch keeps the choice in the session and in `?lang=`. The API gets the language too: `/restock?lang=` returns the reason and shelf-life note in that language and `/chat` answers in it. Validation issues are shown with a translated label plus the engine's English detail. A test checks that both languages have the same keys and placeholders and that every validation issue code has a label.
- **Scan page:** upload files or use the device camera. The camera widget is created only when "Camera" is selected, so no permission prompt appears for visitors who upload. Both read from the visitor's browser, never from the server's disk. Each image is scanned once (results are kept by image hash), so a rerun caused by anything else cannot re-send a receipt to the model.
- **Theme:** `dashboard/.streamlit/config.toml` and `dashboard/theme.py`. The sidebar has the same black as the page with a hairline border; containers are border-only (no fill) and only metrics, inputs and the active link have a fill, always padded and rounded. The brand is drawn in the sidebar header with CSS, not `st.logo`, which adds a second copy in the page header that overlaps the sidebar. Palette `#000000`, `#3e432e`, `#616f39`, `#a7d129`, plus amber and red used only to mean "watch" and "act now". No animations; the Deploy button is hidden with `toolbarMode = "viewer"`.

## Forecast Policy

- `statsforecast` (TSB / CrostonOptimized, chosen per SKU on a 4-week hold-out) forecasts weekly demand; short histories fall back to a 4-week moving average and `data_quality` says so.
- Safety stock is `z x sigma x sqrt(lead time weeks)`. Sigma is the RMSE of one-step forecast errors over the last 26 weeks (`SIGMA_LOOKBACK_WEEKS`). `python -m app.eval.backtest` (`make backtest`) scores this against alternatives on the history.
- z and shelf life are per category in `app/forecast/category_policy.py`: 2.2 for goods that keep (5% stockout target) and 1.8 for cement, paint and waterproofing (10% target). Categories not listed use `SAFETY_STOCK_Z` (2.2).
- Shelf life: if today's stock would take longer to sell than the shelf life, `/restock` returns `shelf_life_risk` (`watch` above 70% of it, `high` above 100%) with a note, and caps the suggested order to what can sell before it spoils. This uses days of cover from the forecast; stock age is unknown because receiving dates are not recorded.

## LLM Call Policy

- **Token budget:** Qwen3.8-27B thinks at `xhigh` unless told otherwise. SQL generation uses
  `reasoning_effort=medium` with `max_tokens=2048`; answer phrasing and restock rephrasing use
  `low` with 1024 / 512 tokens (`LLM_*` in `.env`). Thinking counts toward `max_tokens`, so a
  reply cut off by the budget is logged as a warning. Qwen3.8-27B rejects `high` (400).
- **Retry:** 429, 5xx and connection errors are retried with exponential backoff and jitter
  (`app/llm.py`); a `Retry-After` header wins over the backoff. Tokenfactory answers its
  per-minute limits with `Retry-After: 60`, so `LLM_RETRY_MAX_SECONDS` must stay above 60.
  Timeouts are not retried. The optional restock rephrasing gives up at the first long 429
  instead of waiting. The dashboard's LLM-backed calls have a 150 s timeout to fit the waits.
- **Vision fallback:** if `LLM_MODEL_VISION` stays down (5xx after retries, or a timeout), the
  receipt is read by `LLM_MODEL_VISION_FALLBACK` instead (empty = off). 429s and connection
  errors do not switch models. The switch lasts for that receipt only; the next one tries the
  main model first.
- **Shared limits:** the whole team shares one key: 30 RPM per key, 20 RPM per account, 8
  concurrent. A receipt scan costs at least 2 requests (OCR + vision), a chat question at least 2.
- **OCR hint:** on Tokenfactory, `app/extraction/ocr.py` sends the receipt to the MinerU2.5-Pro
  OCR endpoint and passes its text to the vision model as a hint. The image stays the source of
  truth, and any OCR failure falls back to the vision model alone.
