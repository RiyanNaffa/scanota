# Contributing to scanota

Thanks for helping out. This guide keeps the team fast and the repo clean.

## Getting started

```bash
git clone https://github.com/RiyanNaffa/scanota.git
cd scanota
cp .env.example .env     # fill in your own keys, never commit this file
make up                  # or: docker compose up --build
make demo-data           # load synthetic sample data
```

Run tests before opening a pull request:

```bash
make test                # or: pytest tests/unit
```

The dashboard view tests need Streamlit, which is not in `app/requirements-dev.txt`, so `make test`
and CI skip them. Run them in the dashboard image after changing anything in `dashboard/`:

```bash
docker compose build dashboard
docker compose run --rm --no-deps --entrypoint "" \
  -v "$(pwd)/tests:/app/tests:ro" -v "$(pwd)/app:/app/app:ro" dashboard \
  sh -c "pip install -q pytest && cd /app && python -m pytest tests/unit/test_dashboard_views.py tests/unit/test_dashboard_i18n.py tests/unit/test_dashboard_client.py -q"
```

`make lint` and CI check `app` and `tests` only; run `ruff check dashboard` and `ruff format dashboard` yourself.

## Workflow

1. Pull the latest `main`: `git pull origin main`
2. Create a branch from `main`:
   - `feat/<short-name>` for new features
   - `fix/<short-name>` for bug fixes
   - `docs/<short-name>` for documentation
   - `exp/<short-name>` for experiments and notebooks
3. Make small, focused commits.
4. Push and open a pull request into `main`.
5. Get at least one teammate to review before merging. Do not push directly to `main`.

## Commit messages

Use short, imperative messages with a prefix:

```
feat: add Croston forecast for intermittent demand
fix: handle receipts with missing date
docs: explain forecast backtest in README
test: add total-mismatch validation cases
chore: update docker base image
```

## Code style

- Python 3.11+, formatted with `ruff format`, linted with `ruff check`.
- Type hints on public functions. Use Pydantic models for data crossing a boundary (LLM output, API requests).
- Keep the **LLM and the math separate**: LLMs read and explain; validation, forecasting and reorder logic must be deterministic and tested.
- Text-to-SQL must only ever run through the read-only database user.

## Rules for data and secrets

- **Never commit** API keys, tokens, `.env` files, or model weights.
- **Never commit real receipts** or anything with real customer names or phone numbers. Use synthetic or fully anonymized samples in `data/`.
- If a secret is committed by mistake, rotate it immediately. Deleting the file is not enough because it remains in git history.
- Keep notebooks clean: clear cell outputs before committing.

## Adding or changing things

| Change | Also update |
|---|---|
| New env variable | `.env.example` and the README |
| New forecast method or metric | `app/eval/backtest.py` and the README results table |
| New dashboard text | `dashboard/strings.py` in both languages (a test fails if they differ) |
| New slow API call in a dashboard page | Wrap it in `st.spinner` with its own `*.loading` message, so the page is never empty while it waits |

## Pull request checklist

- [ ] Tests pass locally
- [ ] No secrets or real data in the diff
- [ ] README or docs updated if behavior changed
- [ ] `docker compose up` still works from a clean clone

## Questions

Open a GitHub issue or ask in the team chat.