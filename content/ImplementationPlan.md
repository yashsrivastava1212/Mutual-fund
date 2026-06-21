# Implementation Plan: Mutual Fund FAQ Assistant

**LLM provider:** [Groq API](https://console.groq.com) (`groq` SDK) for generation; local **BGE** for embeddings.

## Phase 1: Project Setup & Infrastructure (Week 1)

### 1.1 Project Structure
- Create directory structure as per Architecture.md §13
- Set up Python virtual environment
- Initialize git repository
- Create README.md with project overview

### 1.2 Dependencies & Configuration
- Install core dependencies:
  - FastAPI + Uvicorn (web framework)
  - LanceDB (vector store; file-backed, Windows-friendly)
  - **Groq SDK** (`groq`) — LLM for constrained text generation
  - APScheduler (scheduler)
  - BeautifulSoup4 (HTML parsing)
  - sentence-transformers + **BGE** (`BAAI/bge-small-en-v1.5` or `bge-large-en-v1.5`) — free local embeddings; Groq is not used for embeddings
  - PyYAML, python-dotenv, httpx
- Create `config/corpus.yaml` with the 5 Groww URLs and scheme metadata:
  - https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth
  - https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth
- Set up environment variables:
  - `GROQ_API_KEY` — Groq API key from [console.groq.com](https://console.groq.com)
  - `GROQ_MODEL` (optional, default `llama-3.3-70b-versatile`)
  - `GROQ_TIMEOUT_SECONDS` (optional, default `120`)
  - `GROQ_MAX_TOKENS` (optional, default `512`)
  - `GROQ_TEMPERATURE` (optional, default `0.1`)
  - Legacy `XAI_API_KEY` / `GROK_*` env vars are read as fallbacks only during migration

### 1.3 Development Environment
- Configure local development setup
- Set up linting (black, flake8)
- Create requirements.txt with pinned versions

---

## Phase 2: Offline Ingestion Pipeline (Week 2)

### 2.1 Fetch Module (`ingestion/fetch.py`)
- Implement HTTP client to fetch URLs from corpus.yaml
- Handle rate limiting and retries
- Store raw HTML/markdown with fetch timestamp
- Add error handling for failed fetches

### 2.2 Parse Module (`ingestion/parse.py`)
- Implement HTML/markdown cleaner
- Remove navigation, footers, duplicate chrome
- Extract scheme-specific sections
- Map content to logical blocks (fund_management, returns, risk, expense_ratio, exit_load, etc.)
- Ensure fund_management sections (manager names, tenure, bios) are extracted completely

### 2.3 Chunk Module (`ingestion/chunk.py`)

**Chunking strategy (section-first, manager-split):**

| Rule | Behavior |
|------|----------|
| Default | **One chunk per section** — each parsed section (`expense_ratio`, `exit_load`, `benchmark`, etc.) becomes a single retrieval unit |
| `fund_management` | **One chunk per manager** — split using `facts.managers[]`; keep each bio intact (name, tenure, education, experience) |
| Skip | Omit `lock_in` when all values are null; omit sections with empty text |
| Overlap | **None** for current corpus (all sections &lt; 200 tokens); if a section exceeds 400 tokens, split within that section only with ~50-token overlap |
| Context prefix | Prepend `{scheme_name} \| Section: {section}` to chunk text before embedding |

**Output:** `data/processed/chunks/{slug}.json` with chunk records and metadata (`id`, `slug`, `scheme_name`, `source_url`, `section`, `last_updated`, `text`).

**Expected size:** ~9–11 chunks per scheme, ~45–55 chunks total across 5 schemes.

### 2.4 Index Module (`ingestion/index.py`)
- Load chunk JSON files from `data/processed/chunks/`
- Generate embeddings via **BGE** (`BAAI/bge-small-en-v1.5` default for ~51 short chunks; `bge-large-en-v1.5` when `EMBEDDING_PRESET=large` or auto thresholds exceeded)
- Store `embedding_model` and dimensions in `scheme_metadata.json`
- Upsert into LanceDB table at `data/index/lancedb`
- Create/update scheme metadata index at `data/index/scheme_metadata.json` (`slug`, `scheme_name`, `category`, `source_url`, `last_fetched_at`)
- Build to staging path first; atomic swap on success

### 2.5 Run Module (`ingestion/run.py`)
- Create orchestration script: `fetch → parse → chunk → embed → index`
- Add logging for each step (URLs fetched, schemes parsed, chunk count, index rows)
- Implement atomic index swap (staging → live) so failed runs do not corrupt the live index

### 2.6 Manual Testing
- Run `python -m ingestion.run` on all 5 URLs
- Verify chunk quality: one chunk per section, per-manager `fund_management` chunks
- Check LanceDB population (~45–55 rows)
- Validate `scheme_metadata.json` has all 5 schemes with `last_fetched_at`

---

## Phase 3: Retrieval Layer (Week 3)

**Status: Complete** — `app/scheme_index.py`, `app/section_intent.py`, `app/retriever.py`; 33 tests in `tests/test_retrieval.py` (67 total).

### 3.0 Retrieval Strategy (decided from chunk + embedding design)

**Corpus profile (indexed):**

| Metric | Value |
|--------|-------|
| Total chunks | 51 |
| Chunks per scheme | 10–11 (Defence has 3 fund-manager chunks) |
| Sections indexed | `scheme_overview`, `expense_ratio`, `exit_load`, `minimum_sip`, `minimum_investment`, `riskometer`, `benchmark`, `stamp_duty`, `fund_management` |
| Avg chunk size | ~30 tokens (max ~65) |
| Embedding model | `BAAI/bge-small-en-v1.5` (384-dim, normalized) |
| Vector store | LanceDB OSS — `data/index/lancedb`, table `chunks` |

**Why this drives retrieval:** Chunks are **section-aligned and tiny** (~9–11 per scheme). Pure global vector search risks wrong-scheme matches; pure keyword lookup misses natural phrasing. Use **metadata-first, BGE-asymmetric search within scheme**.

#### Strategy: Three-stage hybrid (filter → search → re-rank)

```
User query
    → [1] Scheme resolution (rules, scheme_metadata.json)
    → [2] Section intent detection (optional keyword map)
    → [3] LanceDB vector search (slug-filtered, BGE query embedding)
    → [4] Section re-rank / high-confidence section filter
    → top-k=3 chunks → Groq LLM
```

**Stage 1 — Scheme resolution (required before vector search)**

Load `data/index/scheme_metadata.json`. Match query (lowercased) against:

1. Full `scheme_name` (highest priority)
2. `slug` tokens (e.g. `hdfc-mid-cap-fund-direct-growth`)
3. `aliases` (e.g. "mid cap", "defence fund", "gold etf")

| Outcome | Action |
|---------|--------|
| One scheme matched | Proceed with `slug` filter |
| No scheme matched | Return empty retrieval → insufficient-context template (no Groq call) / point to corpus list |
| Multiple schemes | Handled upstream by classifier (comparison refusal), not retrieval |

**Stage 2 — Section intent (keyword rules, no LLM)**

| Query signals | Target `section` |
|---------------|------------------|
| expense ratio, ter | `expense_ratio` |
| exit load, redemption charge | `exit_load` |
| minimum sip, sip amount | `minimum_sip` |
| lumpsum, minimum investment | `minimum_investment` |
| risk, riskometer | `riskometer` |
| benchmark, index | `benchmark` |
| fund manager, who manages, tenure, manager | `fund_management` |
| stamp duty | `stamp_duty` |
| objective, launch, category, overview | `scheme_overview` |

**Stage 3 — LanceDB vector search (BGE asymmetric)**

- **Query embedding:** `embed_query(message)` — applies BGE instruction prefix (`Represent this sentence for searching relevant passages: …`)
- **Document embedding:** already stored at index time via `embed_documents()` (no prefix on chunk text)
- **Search:** `table.search(query_vector).where("slug = '<resolved_slug>'").limit(5)`
- **High-confidence section intent:** optionally tighten filter: `.where("slug = '…' AND section = '…'")` with fallback to slug-only search if zero rows

**Stage 4 — Re-rank and select**

- If section intent detected (medium confidence): boost chunks matching target section (+0.15 score or move to top)
- **`fund_management` queries:** allow up to **3 chunks** (multiple managers per scheme)
- **All other queries:** return **top-k = 3** (default), dedupe by `id`
- Attach `source_url`, `last_updated`, `section` for citation + footer

**What we are NOT using (and why)**

| Approach | Reason to skip |
|----------|----------------|
| Global vector search (no slug filter) | Cross-scheme leakage (mid vs small cap) |
| BM25 / sparse hybrid | 51 chunks; sections already structured |
| Cross-encoder reranker | Corpus too small; latency not justified |
| MMR diversification | Chunks are non-overlapping sections |
| Query expansion / HyDE | Overkill; risks hallucinated retrieval terms |

**Default parameters**

| Parameter | Value |
|-----------|-------|
| `fetch_k` (LanceDB limit) | 5 |
| `top_k` (to Groq LLM) | 3 (up to 3 for multi-manager `fund_management`) |
| Similarity metric | cosine (BGE vectors normalized) |
| Min scheme match | 1 alias or name hit required |

**Retrieved chunk contract (to Phase 4 generator)**

```json
{
  "id": "hdfc-defence-fund-direct-growth#expense_ratio#0",
  "slug": "hdfc-defence-fund-direct-growth",
  "scheme_name": "HDFC Defence Fund Direct Growth",
  "source_url": "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
  "section": "expense_ratio",
  "text": "...",
  "last_updated": "2026-06-09",
  "score": 0.87
}
```

Citation URL = `source_url` from resolved scheme (single URL per answer).

---

### 3.1 LanceDB Vector Store Setup ✅
- ✅ Connect to local LanceDB at `data/index/lancedb` (OSS, free, file-backed)
- ✅ Open `chunks` table; verify row count (~51) and `vector` column (384-dim BGE-small)
- ✅ Confirm `embedding_model` in `scheme_metadata.json` matches indexed vectors
- ✅ Test metadata filtering: `table.search(vector).where("slug = '...'")`

### 3.2 Scheme Metadata Loader (`app/scheme_index.py`) ✅
- ✅ Load `data/index/scheme_metadata.json` at startup (cached)
- ✅ Expose `resolve_scheme(query: str) -> SchemeMatch | None` (name / slug / alias / distinctive-token scoring; tie → None)
- ✅ Expose `get_scheme_by_slug(slug) -> scheme dict` for citation URL
- ✅ Normalizes `defense`/`defence` spelling; rejects ambiguous generic queries (R-06, R-07)

### 3.3 Section Intent (`app/section_intent.py`) ✅
- ✅ Rule-based keyword map (see §3.0 table)
- ✅ Return `SectionIntent | None` with `section` name and confidence (`high` | `medium`)
- ✅ High confidence → LanceDB `section` filter (with slug-only fallback); medium → re-rank boost (+0.15)

### 3.4 Retriever Implementation (`app/retriever.py`) ✅
- ✅ Implement three-stage hybrid per §3.0:
  1. `resolve_scheme(message)` — if None, return `[]`
  2. `detect_section_intent(message)` — optional filter/boost
  3. LanceDB: `embed_query(message)` → `table.search(...).where(slug=…)` → re-rank → top-k
- ✅ Use `ingestion/embeddings.embed_query()` for BGE asymmetric encoding
- ✅ Open LanceDB table `chunks` from `settings.lance_db_uri`
- ✅ Return list of chunk dicts with `score`, `source_url`, `last_updated` (default `top_k=3`; up to 3 for `fund_management`)

### 3.5 Retrieval Testing ✅
- ✅ Test scheme resolution: R-01–R-11 from `edge-case.md`
- ✅ Test section intent → correct section in top-1 (expense, exit load, fund_management)
- ✅ Test LanceDB slug filter: no cross-scheme chunks (R-20, R-21)
- ✅ Test BGE query prefix used via `embed_query()` mock
- ✅ Live-index integration tests; latency verified on warm embed

---

## Phase 4: Application Layer - Core Logic (Week 4)

**Status: Complete** — classifier, refusal, generator, validator, formatter, chat orchestration; 45+ unit tests.

### 4.1 Query Classifier (`app/classifier.py`) ✅
- ✅ Rule-based regex matcher for advisory and comparison phrases
- ✅ Returns `QueryType`: FACTUAL, ADVISORY, COMPARISON (comparison checked first)
- ⏭ LLM fallback deferred (rules sufficient for current scope)

### 4.2 Refusal Handler (`app/refusal.py`) ✅
- ✅ Templated refusal responses for advisory and comparison
- ✅ Facts-only limitation statement + AMFI educational link
- ✅ No retrieval or LLM call on refusal path

### 4.3 RAG Orchestrator (`app/generator.py`) ✅
- ✅ System prompt with facts-only rules and max 3 sentences
- ✅ Context block from retrieved chunks (scheme, section, URL, date, text)
- ✅ Hard rules: no advice, comparisons, return math, or URLs in answer body

### 4.4 LLM Integration (Groq) (`app/llm.py`) ✅
- ✅ Groq client via official `groq` Python SDK with `GROQ_API_KEY`
- ✅ Default model: `llama-3.3-70b-versatile` (override via `GROQ_MODEL`)
- ✅ `max_tokens`, `temperature` (default 0.1), timeout from settings
- ✅ `LLMClient.complete_with_retry()` — up to 3 attempts with exponential backoff
- ✅ Extractive fallback in `app/chat.py` when `GROQ_API_KEY` is unset (tests/offline)

### 4.5 Output Validator (`app/validator.py`) ✅
- ✅ Sentence count (max 3), banned advice/comparison phrases, no URLs in body
- ✅ Numeric grounding check (answer numbers must appear in context)
- ✅ Citation URL must be a corpus Groww URL
- ✅ Graceful fallback answer when validation fails

### 4.6 Response Formatter (`app/formatter.py`) ✅
- ✅ Truncate to 3 sentences, strip inline URLs
- ✅ Footer: `Last updated from sources: <date>` appended to answer
- ✅ Structured JSON: `answer`, `citation_url`, `last_updated`, `is_refusal`, `disclaimer`

### 4.7 Chat Orchestration (`app/chat.py`) ✅
- ✅ `handle_chat()` routes classifier → refusal or retrieval → generate → validate → format
- ✅ Insufficient-context template when no scheme/chunks match
- ✅ Extractive fallback when Groq is not configured (tests/offline)

### 4.8 Unit Testing ✅
- ✅ `tests/test_classifier.py`, `tests/test_refusal.py`, `tests/test_generator.py`, `tests/test_security.py`

---

## Phase 5: Application Layer - API (Week 5)

**Status: Complete** — `POST /api/chat` with security, rate limiting, and integration tests.

### 5.1 Chat Controller (`app/main.py`) ✅
- ✅ `POST /api/chat` accepts `{ "message": string }`
- ✅ `GET /health` reports `llm_configured`, `llm_provider` (`groq`), `llm_model`
- ✅ Routes via `app/chat.py`: classifier → RAG or refusal
- ✅ Returns structured `ChatResponse` JSON
- ✅ Logging for request IP and message length

### 5.2 API Contract Validation ✅
- ✅ Pydantic models for request/response
- ✅ Tests verify citation URL, `last_updated`, `is_refusal`, `disclaimer`
- ✅ 422 for missing/invalid body; 400 for empty/PII messages

### 5.3 Security & Privacy ✅
- ✅ PII rejection in `app/security.py` (PAN, Aadhaar, account #, OTP, email, phone)
- ✅ Input sanitization (whitespace normalize, control-char strip)
- ✅ Per-IP rate limiting in `app/rate_limit.py` (default 30 req/min)
- ✅ Stateless API — no session storage

### 5.4 Integration Testing ✅
- ✅ `tests/test_api_chat.py` — refusal path, factual path (mocked), PII, rate limit, insufficient context

---

## Phase 6: Presentation Layer (Week 6)

**Status: Complete** — Premium Wealth stitch design; `ui/index.html` + `ui/app.js`; served at `GET /`.

### 6.1 Web UI (`ui/index.html`) ✅
- ✅ Single-page chat interface using **Premium Wealth** design tokens from `content/stitch/stitch_packswipe_swipe_based_packing_assistant/premium_wealth/DESIGN.md`
- ✅ Plus Jakarta Sans + Inter typography, navy/blue palette, card elevation, 12px radii
- ✅ Welcome message and disclaimer: "Facts-only. No investment advice."
- ✅ Three clickable example questions (expense ratio, exit load, fund management)
- ✅ Free-text query input (max 2000 chars) with PII warning in disclaimer
- ✅ Assistant replies with citation link, last-updated date, refusal styling

### 6.2 UI Integration ✅
- ✅ `ui/app.js` → `POST /api/chat` with JSON `{ "message": string }`
- ✅ Loading state (typing indicator + disabled send)
- ✅ Error handling for 400, 429, and network failures
- ✅ FastAPI serves `GET /` (index) and `/ui/*` static assets

### 6.3 UI Testing ✅
- ✅ `tests/test_ui.py` — index HTML, static JS, disclaimer, examples, form elements

---

## Phase 7: Daily Scheduler (Week 7)

**Status: Complete** — daily ingestion at **10:00 AM IST** (`Asia/Kolkata`).

### 7.1 Scheduler Implementation (`scheduler/daily.py`) ✅
- ✅ APScheduler cron trigger: `SCHEDULER_HOUR=10`, `SCHEDULER_MINUTE=0`, `SCHEDULER_TIMEZONE=Asia/Kolkata`
- ✅ Invokes `ingestion.run.run_ingestion()` as atomic job
- ✅ CLI: `python -m scheduler.daily --daemon | --run-now | --status`
- ✅ Optional background scheduler via `SCHEDULER_ENABLED=true` in FastAPI lifespan
- ✅ Logging: attempt count, success/failure, chunk counts in `scheduler_status.json`

### 7.2 Error Handling ✅
- ✅ One retry on failure (`SCHEDULER_MAX_RETRIES=2`, delay configurable)
- ✅ Errors recorded in `data/index/scheduler_status.json`
- ✅ Alerting via structured logs (no email in v1)

### 7.3 Index Swapping ✅
- ✅ Ingestion uses staging + atomic swap (Phase 2); API serves previous index until success
- ✅ Post-success cache clear: retriever, scheme metadata, corpus URLs

### 7.4 Scheduler Testing ✅
- ✅ `tests/test_scheduler.py` — status persistence, retry, `/api/scheduler/status`

---

## Phase 8: Testing & Quality Assurance (Week 8)

**Status: Complete** — 128 tests across unit, integration, compliance, UI.

### 8.1 Unit Tests ✅
- ✅ `test_classifier.py`, `test_retrieval.py`, `test_refusal.py`, `test_generator.py` (validator/formatter), `test_security.py`

### 8.2 Integration Tests ✅
- ✅ `test_api_chat.py`, `test_compliance.py`, `test_ingestion_run.py`, `test_scheduler.py`

### 8.3 Compliance Testing ✅
- ✅ Advisory/comparison refusal without retrieval (`test_compliance.py`)
- ✅ PII rejection, citation URL, `last_updated`, footer on factual path

### 8.4 Performance Testing ✅
- ✅ Retrieval latency test in `test_retrieval.py` (<5s warm embed budget)

### 8.5 User Acceptance Testing ✅
- ✅ Example questions covered in UI + API tests; edge cases in `content/edge-case.md`

---

## Phase 9: Deployment (Week 9)

**Status: Complete** — Docker + docker-compose for API and scheduler.

### 9.1 Development Deployment ✅
- ✅ `uvicorn app.main:app` on `:8000`, LanceDB at `data/index/lancedb`
- ✅ Manual trigger: `python -m scheduler.daily --run-now`

### 9.2 Production Preparation ✅
- ✅ `Dockerfile` (Python 3.12-slim)
- ✅ `docker-compose.yml` — `api` + `scheduler` services, `./data` volume
- ✅ `.dockerignore`, env via `.env`

### 9.3 Production Deployment ✅
- ✅ Documented in README: `docker compose up --build`
- ✅ Scheduler service runs `--daemon` at 10:00 AM IST
- ✅ Rate limiting + stateless API (Phase 5)

### 9.4 Production Validation ✅
- ✅ Smoke tests via `pytest` + `/health`, `/api/scheduler/status`

---

## Phase 10: Documentation & Handoff (Week 10)

**Status: Complete**

### 10.1 Documentation ✅
- ✅ `README.md` — setup, API, scheduler, Docker, limitations
- ✅ `content/Architecture.md`, `content/ImplementationPlan.md` updated
- ✅ `content/edge-case.md` — test matrix reference

### 10.2 Known Limitations ✅
- ✅ Documented in README and Architecture §11

### 10.3 Future Extensions ✅
- ✅ Listed in ImplementationPlan (corpus expansion, clarification turns, multilingual, admin dashboard)

---

## Success Criteria Verification

By the end of Phase 10, verify:

- ✅ Accurate retrieval of factual mutual fund information
- ✅ Strict adherence to facts-only responses
- ✅ Consistent inclusion of valid source citations
- ✅ Proper refusal of advisory queries
- ✅ Clean, minimal, and user-friendly interface
- ✅ Daily ingestion pipeline working reliably
- ✅ No PII collection or storage
- ✅ Stateless API with rate limiting
- ✅ All responses include last-updated footer
- ✅ Maximum 3 sentences per response

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| 1 | Week 1 | Project structure, dependencies, config |
| 2 | Week 2 | Ingestion pipeline (fetch, parse, chunk, index) |
| 3 | Week 3 | Retrieval layer (LanceDB + retriever) ✅ |
| 4 | Week 4 | Core logic (classifier, RAG, validator, formatter) ✅ |
| 5 | Week 5 | API implementation (chat controller, security) ✅ |
| 6 | Week 6 | Web UI implementation ✅ |
| 7 | Week 7 | Daily scheduler (10:00 AM IST) ✅ |
| 8 | Week 8 | Testing & QA ✅ |
| 9 | Week 9 | Deployment (Docker) ✅ |
| 10 | Week 10 | Documentation & handoff ✅ |

**Total Duration: 10 weeks**
