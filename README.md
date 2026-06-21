# Mutual Fund FAQ Assistant

Facts-only RAG assistant for **five HDFC mutual fund schemes** on Groww. Answers objective queries (expense ratio, exit load, fund management, etc.) with a single source citation. No investment advice.

**LLM:** [Groq API](https://console.groq.com) (`llama-3.3-70b-versatile`)  
**Embeddings:** [BGE](https://huggingface.co/BAAI) local via `sentence-transformers`  
**Vector store:** LanceDB at `data/index/lancedb`  
**UI:** Dark trading-terminal chat at `GET /`

## Corpus (5 schemes)

| Scheme | URL |
|--------|-----|
| HDFC Mid Cap Fund Direct Growth | [Groww](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| HDFC Large Cap Fund Direct Growth | [Groww](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) |
| HDFC Small Cap Fund Direct Growth | [Groww](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth) |
| HDFC Gold ETF FoF Direct Plan Growth | [Groww](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth) |
| HDFC Defence Fund Direct Growth | [Groww](https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth) |

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # set GROQ_API_KEY

python -m ingestion.run   # first-time index build
uvicorn app.main:app --reload
```

Open **http://localhost:8000**

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Chat UI |
| GET | `/health` | Health + LLM status |
| GET | `/api/corpus` | Scheme list |
| POST | `/api/chat` | `{ "message": "..." }` |
| GET | `/api/scheduler/status` | Last ingestion run |

## Daily scheduler (10:00 AM IST)

Ingestion runs **daily at 10:00 AM Asia/Kolkata** (configurable).

```powershell
# One-shot manual run
python -m scheduler.daily --run-now

# Standalone scheduler daemon
python -m scheduler.daily --daemon

# Check last run
python -m scheduler.daily --status
```

**With API process** — set in `.env`:

```env
SCHEDULER_ENABLED=true
SCHEDULER_HOUR=10
SCHEDULER_MINUTE=0
SCHEDULER_TIMEZONE=Asia/Kolkata
```

On success, the scheduler clears retriever caches so the live API serves the new index (atomic swap during ingestion).

## Docker

```powershell
docker compose up --build
```

- `api` service: FastAPI on port 8000 (optional `SCHEDULER_ENABLED=true`)
- `scheduler` service: dedicated daemon at 10:00 AM IST
- `./data` volume persists LanceDB + raw/processed files

## Ingestion

```powershell
python -m ingestion.run              # full pipeline
python -m ingestion.run --skip-fetch   # re-chunk/re-index only
```

Pipeline: **fetch → parse → chunk → embed (BGE) → LanceDB** with atomic index swap.

## Tests

```powershell
pytest
```

## Known limitations

- **Corpus:** 5 HDFC Groww pages only (not official AMC primary docs)
- **Facts-only:** Advisory, comparison, and ranking queries are refused
- **No scheme disambiguation turn** — ambiguous queries may return insufficient context
- **English only** — no multilingual support
- **Stale data** until next daily ingestion (see `last_updated` in responses)
- **Decorative UI elements** (ticker % moves) are not live market data

## Documentation

- `content/Architecture.md` — system design
- `content/ImplementationPlan.md` — phased delivery
- `content/edge-case.md` — test scenarios
- `content/ProblemStatement.md` — scope

## Disclaimer

**Facts-only. No investment advice.**
