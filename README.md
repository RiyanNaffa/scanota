# scanota

**Paper receipts and online invoices in one clean sales database, plus a weekly restock list.**

Small merchants (building supply stores, warungs, market stalls) keep their sales in paper receipt books. That data is locked away, so nobody can see what sells, what is running out, or what to reorder. scanota reads those receipts, merges them with online orders, and tells the owner what to restock.

Built for the AMD Act III Hackathon, track **Reinvent Commerce**.

<!-- Add demo GIF or screenshot here -->

## How it works

```
Paper receipt photo ─► Vision model (AMD) ─► Validation ─┐
                                                         ├─► PostgreSQL ─► Dashboard + restock list
Online invoice / CSV ─► POST /ingest/online ─────────────┘
```

1. **Read.** A vision model on AMD Token Factory (AMD GPUs), helped by an OCR model, turns a receipt photo into structured JSON.
2. **Validate (no LLM).** `sum(qty x price) == total`, date and price-range checks, fuzzy matching of item names to the product master (e.g. "SMN 3R" and "semen tiga roda 50kg" become one SKU). Low-confidence receipts go to a "Needs review" screen; corrections become new aliases.
3. **Merge.** Online and offline transactions share one canonical schema.
4. **Act.** Per-SKU demand forecast, safety stock and reorder point produce a weekly restock list with reasons.
5. **Ask.** A question in Indonesian or English is translated to read-only SQL. The LLM never answers sales numbers from memory.

## How the forecast is calculated

The forecast is statistical. The LLM only explains it.

- **Model:** Croston / TSB for intermittent demand (via `statsforecast`)
- **Baseline:** 4-week moving average
- **Safety stock:** `z x sigma x sqrt(lead time)`, with sigma the RMSE of the last 26 weeks of one-step forecast errors and z set per product category (2.2 for goods that keep, 1.8 for cement, paint and waterproofing, which have a shelf life)
- **Shelf life:** for categories with a shelf life, stock that would take longer to sell than it keeps is flagged, and suggested orders are capped to what can sell in time
- **Metric:** WAPE on a held-out backtest

| Metric | scanota | Baseline |
|---|---|---|
| WAPE (next week) | 0.77 | 0.82 |
| Stockout rate (simulated) | 6.2% | 9.8% |

Measured with `make backtest` on the synthetic data: 38 SKUs, the last 26 weeks, the same per-category z for both columns. A stockout is demand during the lead time above the reorder point. The targets are 5% for goods that keep and 10% for goods with a shelf life; z comes from the backtest and was checked on weeks it was not calibrated on (`docs/BUILD_LOG.md`). The synthetic demand is cleaner than a real shop's, so read these as a check of the method, not as a promise.

## OCR evaluation

| Metric | With OCR hint (default) | Vision model only |
|---|---|---|
| Field accuracy (date, total both correct) | 100% | 100% |
| Item-level F1 (name + qty + line total) | 0.975 | 0.875 |
| Matched to the right SKU | 100% | 100% |
| Wrong printed totals caught by the total check | 5 of 5 | 5 of 5 |
| Correct receipts flagged by mistake | 0 of 35 | 0 of 35 |

Measured with `make eval` on the 40 synthetic receipts in `data/sample_receipts/` (one item each, clean printed text, five with a deliberately wrong total), reading with MiniCPM-V-4.7-35B-A3B and, in the first column, the MinerU2.5-Pro OCR text as a hint. The expected total is the one printed on the receipt, because the model is told to copy what is written and the total check is what catches a wrong one.

- The OCR hint fixed four misread item names (for example "krem 30x30" for "krm 30x30", "SMM HLC" for "SMN HLC"). The SKU match was already 100% without it, because fuzzy matching absorbs small spelling errors, so the end result is the same on these clean receipts. Both variants misread "60x120" as "50x120" on one receipt.
- Forty receipts is a small sample: four receipts separate the two columns. Handwriting and crumpled paper are not covered, which is where an OCR hint should matter most.
- In the first run five vision-only calls hit endpoint timeouts and were read again; a call that fails says nothing about accuracy, so the evaluation now retries failed receipts itself.

## Run it

Requirements: Docker and Docker Compose.

```bash
git clone https://github.com/RiyanNaffa/scanota.git
cd scanota
cp .env.example .env        # fill in LLM_BASE_URL and LLM_API_KEY (the model names have defaults)
make up                     # or: docker compose up --build
make demo-data              # loads the synthetic demo data (see Demo data below)
```

Open the dashboard at http://localhost:8501. The language (Indonesian or English) is switched in the sidebar, and receipts can be uploaded from files or captured with the device camera on the Scan Receipt page.

Never commit `.env`. All keys are read from environment variables.

## Demo data

The demo, including a deployment, runs on **synthetic data**. Nothing in it is a real customer or a real sale. The database starts empty, so load it once after the first start:

```bash
make demo-data
```

Where `make` is not installed (a fresh VM, for example) run what it runs: `docker compose exec api python -m app.db.seed`. It needs the stack to be up, and it reads `./data`, which `docker-compose.yml` mounts into the API container. It is safe to run again: orders that already exist are skipped.

| What | Where | How it gets in |
|---|---|---|
| 38 products with their aliases, 510 online orders and 3,034 offline sales over about 78 weeks, stored as confirmed transactions | `data/sample_transactions/` | `make demo-data` |
| 40 sample receipt photos with their ground truth (five have a deliberately wrong total) | `data/sample_receipts/` | Not loaded: scan them on the Scan Receipt page. Uploads come from the visitor's device, so download the images from the repository to it first |

With this data every product starts well above its reorder point, so the Restock page shows no order to place. Lower a stock level there to see one.

## Deploying on a VM

- **HTTPS is required for the camera.** Browsers only allow camera access on HTTPS or on `localhost`. Over plain `http://<vm-ip>:8501` the Camera option cannot work, so put a reverse proxy with a TLS certificate (Caddy or nginx) in front of the dashboard.
- **Uploads and photos come from the visitor's device.** The file picker and the camera run in the visitor's browser and send the image to the server. Nothing is read from the VM's file system. Scanned receipts are stored in the `storage` Docker volume.
- **Expose only the proxy.** `docker-compose.yml` publishes the API (8000) and the dashboard (8501) on the host; open only 443 in the firewall or network security group. Postgres is bound to `127.0.0.1` in `docker-compose.yml`, so it is never reachable from the network; the API and the dashboard reach it as `db:5432` inside the compose network. For `psql` on the VM or over an SSH tunnel, set `POSTGRES_PORT` in `.env` to fix its local port (empty lets Docker pick one; `docker compose ps` shows it).
- **Receipt photos are limited to 10 MB each.** The dashboard (`server.maxUploadSize` in `dashboard/.streamlit/config.toml`) and the API (`MAX_UPLOAD_MB`) enforce 10 MB, and a test checks the two agree. Set the proxy limit a little higher, 12 MB, so a 10 MB photo is not cut off by the proxy before the dashboard can answer with its own message.
- **There is no login in the app.** Anyone who can open the dashboard can read sales data, confirm receipts and ask questions, so add authentication at the proxy. A minimal Caddyfile with TLS, a password and the size limit (make the hash with `caddy hash-password`):

```
scanota.example.com {
	basic_auth {
		admin <hash>
	}
	request_body {
		max_size 12MB
	}
	reverse_proxy localhost:8501
}
```

## Runs on AMD

- The models run on **AMD Token Factory** (AMD Radeon Cloud): the vision and text models and the MinerU2.5-Pro OCR endpoint, all through an OpenAI-compatible API. Put `LLM_BASE_URL` and `LLM_API_KEY` in `.env`.
- Token Factory limits are shared by the whole team key (about 30 requests per minute, 8 at once); the app retries 429 and 5xx responses and can fall back to a second vision model.
- `infra/amd/` holds an optional vLLM-on-ROCm overlay for self-hosting. The current setup does not use it. A self-hosted vLLM has no OCR route, so set `OCR_ENABLED=false` there.

## Repository layout

```
app/         FastAPI backend (ingest, extraction, validation, forecast, chat) and app/eval (OCR evaluation, forecast backtest)
dashboard/   Streamlit UI: pages in views/, Indonesian and English text in strings.py
infra/amd/   Optional vLLM ROCm self-hosting overlay (not used by default)
data/        Synthetic sample receipts and transactions
tests/       Unit tests (validation, matching, forecast, SQL guard, LLM retry, OCR, dashboard) and a health check
docs/        Architecture and build log
```

## Limitations

- Very poor handwriting still needs human review; that is by design.
- Shelf-life warnings compare days of cover with the shelf life. Stock age is not tracked (no receiving dates per batch), so a shop selling fresh food needs batch and expiry tracking first.
- Demo data is synthetic. No real customer data is included.
- Online ingestion is simulated through webhook and CSV, not live marketplace APIs.

## License

MIT