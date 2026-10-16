# scanota

**Paper receipts and online invoices in one clean sales database, plus a weekly restock list.**

Small merchants (building supply stores, warungs, market stalls) keep their sales in paper receipt books. That data is locked away, so nobody can see what sells, what is running out, or what to reorder. scanota reads those receipts, merges them with online orders, and tells the owner what to restock.

Built for the AMD Act II Hackathon, track **Reinvent Commerce** (and the Evolus Business Agents track).

<!-- Add demo GIF or screenshot here -->

## How it works

```
Paper receipt photo ─► Vision model (AMD) ─► Validation ─┐
                                                         ├─► PostgreSQL ─► Dashboard + restock list
Online invoice / CSV ─► POST /ingest/online ─────────────┘
```

1. **Read.** A vision model served with vLLM on AMD ROCm turns a receipt photo into structured JSON.
2. **Validate (no LLM).** `sum(qty x price) == total`, date and price-range checks, fuzzy matching of item names to the product master (e.g. "SMN 3R" and "semen tiga roda 50kg" become one SKU). Low-confidence receipts go to a "Needs review" screen; corrections become new aliases.
3. **Merge.** Online and offline transactions share one canonical schema.
4. **Act.** Per-SKU demand forecast, safety stock and reorder point produce a weekly restock list with reasons.
5. **Ask.** Chat in Indonesian is translated to read-only SQL. The LLM never answers sales numbers from memory.

## How the forecast is calculated

The forecast is statistical. The LLM only explains it.

- **Model:** Croston / TSB for intermittent demand (via `statsforecast`)
- **Baseline:** 4-week moving average
- **Safety stock:** from the distribution of forecast errors
- **Metric:** WAPE on a held-out backtest

| Metric | scanota | Baseline |
|---|---|---|
| WAPE | TBD | TBD |
| Stockout rate (simulated) | TBD | TBD |

## OCR evaluation

| Metric | Result |
|---|---|
| Field accuracy (date, total) | TBD |
| Item-level F1 | TBD |
| Errors caught by total check | TBD |

Evaluated on synthetic receipts with ground truth in `data/sample_receipts/`.

## Run it

Requirements: Docker and Docker Compose.

```bash
git clone https://github.com/RiyanNaffa/scanota.git
cd scanota
cp .env.example .env        # fill in LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
make up                     # or: docker compose up --build
make demo-data              # loads sample receipts and online orders
```

Open the dashboard at http://localhost:8501.

Never commit `.env`. All keys are read from environment variables.

## Runs on AMD

- For the final demo, models are served with **vLLM on ROCm** (AMD Developer Cloud / Instinct). That setup is only for self-hosting; see `infra/amd/README.md`.
- The app talks to any OpenAI-compatible endpoint, so `LLM_BASE_URL` can point to the AMD Tokenfactory during development (no vLLM needed) and to your own vLLM endpoint for the final demo. Tokenfactory also offers an OCR endpoint (MinerU2.5-Pro) that scanota uses as a hint for receipt reading; a self-hosted vLLM has no such route, so set `OCR_ENABLED=false` there.
- Proof (`rocm-smi`, vLLM logs, latency and throughput): `docs/amd-proof.md`.

## Evolus building blocks

Document extractor, workflow, and AI Tools, driven through the Evolus REST API from `app/evolus/`. Configuration details are in `evolus/`.

## Repository layout

```
app/         FastAPI backend (ingest, extraction, validation, forecast, chat, evolus)
dashboard/   Streamlit UI
infra/amd/   vLLM ROCm setup
evolus/      Workflow and extractor documentation
data/        Synthetic sample receipts and transactions
notebooks/   OCR evaluation and forecast backtest
tests/       Validation, matching, forecast tests
docs/        Architecture, AMD proof, demo script
```

## Limitations

- Very poor handwriting still needs human review; that is by design.
- Demo data is synthetic. No real customer data is included.
- Online ingestion is simulated through webhook and CSV, not live marketplace APIs.

## License

MIT