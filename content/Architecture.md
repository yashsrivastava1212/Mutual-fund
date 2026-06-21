Architecture 

Architecture: Mutual Fund FAQ Assistant

**LLM provider:** [Groq API](https://console.groq.com) for constrained text generation (default model `llama-3.3-70b-versatile`). **Embeddings:** local BGE via `sentence-transformers` — Groq is not used for vector search.



1. Design Goals



2. High-Level Architecture

Offline Pipeline

Generation Layer

Retrieval Layer

Application Layer

Presentation Layer

Daily trigger

Advisory / Comparison

Factual

Web UI
(Chat + Disclaimer)

API Gateway / Chat Controller

Query Classifier
(Factual vs Advisory)

Refusal Handler

RAG Orchestrator

Response Formatter

Retriever
(Vector + Metadata Filter)

Vector Store

Scheme Metadata Index

LLM / Groq
(Constrained Generation)

Output Validator

Daily Scheduler

Ingestion & Crawler

Cleaner / Section Parser

Chunker

Embedding Service

Index Builder

Request path (online): User question → classify → retrieve relevant chunks → generate grounded answer → validate → format → display.

Index path (offline): A daily scheduler triggers the ingestion pipeline → fetch 5 Groww pages → parse into structured sections → chunk → embed with BGE → persist to **LanceDB** (`data/index/lancedb`) and `scheme_metadata.json`.



3. System Components

3.1 Presentation Layer (Minimal UI)

**Status: Implemented** — `ui/index.html` + `ui/app.js`, served at `GET /` (FastAPI). Design system: **Premium Wealth** stitch pack (`content/stitch/.../premium_wealth/DESIGN.md`).

A lightweight single-page chat interface inspired by Groww's mutual fund detail pages as reference context, styled with the Premium Wealth corporate palette (navy primary `#0B1F3A`, secondary blue `#0051D5`, Plus Jakarta Sans + Inter).

Responsibilities:

Display welcome message and disclaimer: "Facts-only. No investment advice."

Show three clickable example questions (covering scheme facts and fund management)

Accept free-text user queries

Render assistant replies with citation link and last-updated footer

Never prompt for or accept PII (PAN, Aadhaar, account numbers, OTP, email, phone)

**UI behaviour (trading-terminal theme):**
- Ticker bar + scheme watchlist from `GET /api/corpus`
- Quick-action chips and free-text input (click/type → `POST /api/chat`)
- Dark terminal styling; short footer: "Facts-only. No investment advice."
- Citation link + `last_updated` from API response; loading/error states inline

Suggested example questions:

What is the expense ratio of HDFC Mid Cap Fund Direct Growth?

What is the exit load on HDFC Defence Fund Direct Growth?

Who manages HDFC Gold ETF Fund of Fund Direct Plan Growth?

Who is the fund manager of HDFC Large Cap Fund Direct Growth?



3.2 Application Layer

Chat Controller

**Status: Implemented** — `POST /api/chat` in `app/main.py`, orchestration in `app/chat.py`.

Exposes a single endpoint, e.g. POST /api/chat

Accepts { "message": string } only — no session identifiers tied to identity

Routes to classifier, then RAG or refusal path

Returns structured JSON for the UI to render

`GET /health` exposes `llm_configured`, `llm_provider` (`groq`), and `llm_model` for ops checks.

{

  "answer": "The expense ratio of HDFC Mid Cap Fund Direct Growth is 0.73%. Last updated from sources: 2026-05-29",

  "citation_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",

  "last_updated": "2026-05-29",

  "is_refusal": false,

  "disclaimer": "Facts-only. No investment advice."

}



Query Classifier

**Status: Implemented** in `app/classifier.py` — rule-based regex; comparison checked before advisory.

Runs before retrieval to enforce compliance.

Implementation options (in order of simplicity):

Rule-based keyword/pattern matcher for advisory and comparison phrases

Lightweight LLM classification with a fixed label set

Hybrid: rules first, LLM fallback for ambiguous cases

Refusal Handler

**Status: Implemented** in `app/refusal.py` — templated responses, AMFI link, no RAG.

Produces a polite, templated response when classification blocks RAG:

States the facts-only limitation

Does not retrieve or invent fund data

Includes one educational link (AMFI or SEBI), e.g.:

AMFI — Mutual Funds

SEBI — Investor Education

RAG Orchestrator

**Status: Implemented** in `app/generator.py` + `app/chat.py` (retrieve → generate → validate → format).

Coordinates retrieval, prompt assembly, generation, and validation for factual queries.

Response Formatter

**Status: Implemented** in `app/formatter.py` + `app/validator.py`.

Enforces output contract:

Maximum 3 sentences in the answer body

Exactly one citation_url (must match one of the 5 corpus URLs when answering from corpus)

Footer: Last updated from sources: <date> where <date> comes from chunk metadata (page fetch or parse timestamp), not model inference



3.3 Retrieval Layer

Corpus (Active)

The assistant answers only from these five Groww scheme pages:

| # | Scheme | URL |
|---|--------|-----|
| 1 | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| 2 | HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 3 | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| 4 | HDFC Gold ETF Fund of Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| 5 | HDFC Defence Fund Direct Growth | https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth |

Supported factual query types include scheme parameters (expense ratio, exit load, minimum SIP, riskometer, benchmark) and **fund management** (manager names, tenure, and profiles as shown on each scheme page).

Scheme Metadata Index

**Implemented** in `app/scheme_index.py` — loads `data/index/scheme_metadata.json` (cached) and exposes `resolve_scheme()` / `get_scheme_by_slug()`.

A small lookup table (JSON or embedded DB) keyed by scheme name / slug:

{

  "slug": "hdfc-mid-cap-fund-direct-growth",

  "scheme_name": "HDFC Mid Cap Fund Direct Growth",

  "category": "Equity — Mid Cap",

  "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",

  "last_fetched_at": "2026-05-29"

}



Used to:

Resolve which scheme the user is asking about

Pre-filter retrieval to a single scheme when detected

Attach the correct citation URL

Vector Store (LanceDB)

Stores embedded text chunks with rich metadata in a local LanceDB table (`chunks` at `data/index/lancedb`):

- **Engine:** LanceDB OSS (free, file-backed, local disk)
- **Table:** `chunks` with columns `id`, `slug`, `scheme_name`, `source_url`, `section`, `text`, `last_updated`, `chunk_index`, `vector`
- **Embeddings:** BGE-small (384-dim) stored in `vector`; must match `embedding_model` in `scheme_metadata.json`
- **Not used:** ChromaDB, FAISS, or LanceDB Cloud (no `LANCEDB_API_KEY` required for local dev)

Retriever

**Status: Implemented** in `app/retriever.py` with `app/scheme_index.py` and `app/section_intent.py`.

**Strategy:** Three-stage hybrid — scheme resolution → section intent → LanceDB BGE search (see ImplementationPlan §3.0).

Because the corpus is tiny (~51 chunks, ~10 per scheme), **always filter by `slug` first**, then vector search within that subset. Do not search the full table without a scheme filter.

**Stage 1 — Scheme resolution**

Match user query to one of five schemes via `scheme_metadata.json`: full name → slug → alias (e.g. "mid cap", "defence fund"). If no match, return empty retrieval.

**Stage 2 — Section intent (rules)**

Keyword map to `section` (expense_ratio, exit_load, fund_management, etc.). High confidence → optional LanceDB `section` filter; medium → re-rank boost only.

**Stage 3 — LanceDB vector search**

- Query: `embed_query()` with BGE instruction prefix (asymmetric vs document embeddings)
- Search: `table.search(vector).where("slug = '<resolved>'").limit(5)`; high-confidence section intent adds `AND section = '…'` with slug-only fallback
- Re-rank by section intent (+0.15 boost); return top-k=3 (up to 3 `fund_management` chunks for multi-manager queries)
- Citation: `source_url` from resolved scheme
- Entry point: `retrieve(message, top_k=3) -> list[dict]` in `app/retriever.py`



3.4 Generation Layer

LLM (Groq — Constrained Generation)

**Status: Implemented** in `app/llm.py` (`LLMClient`) and `app/generator.py`.

| Setting | Env var | Default |
|---------|---------|---------|
| API key | `GROQ_API_KEY` | — (required for live generation) |
| Model | `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| Max tokens | `GROQ_MAX_TOKENS` | `512` |
| Temperature | `GROQ_TEMPERATURE` | `0.1` |
| Timeout | `GROQ_TIMEOUT_SECONDS` | `120` |

Provider: [Groq API](https://console.groq.com) via official `groq` Python SDK. Embeddings remain local BGE — Groq is **not** used for vector search.

The model receives:

System prompt: facts-only, no advice, use only provided context, max 3 sentences

Retrieved chunks with source URLs and dates

User question

Hard rules in the prompt:

Answer only from retrieved context; if context is insufficient, say so and point to the scheme page

Do not compare funds or compute returns

Do not recommend buy/sell/hold

Include no more than one URL in the answer (formatter strips URLs; citation is separate)

Generation flow: `app/chat.py` → `generate_answer()` → `LLMClient.complete_with_retry()` → `app/validator.py` → `app/formatter.py`. If Groq is unavailable or validation fails, an extractive fallback or safe template is returned.

Output Validator

**Status: Implemented** in `app/validator.py`.

Post-generation checks before returning to the user:

- Max 3 sentences; no URLs in answer body
- No advisory/comparison language
- Numeric grounding (answer numbers must appear in retrieved context)
- `citation_url` must be one of the five corpus Groww URLs



3.5 Offline Ingestion Pipeline

Triggered once per day by the scheduler (see §3.6), or on manual CLI trigger — never on every user query.

Daily Scheduler

Fetch 5 Groww URLs

Parse HTML / Markdown

Extract Sections

Chunk Text

Generate Embeddings

Upsert Vector Store

Update Metadata Index

Ingestion steps

Fetch — HTTP GET each corpus URL; store raw HTML or converted markdown with fetch timestamp

Clean & parse — Remove navigation, footers, and duplicate chrome; retain scheme-specific sections

Section extraction — Map content into logical blocks aligned with FAQ query types, including `fund_management` (manager names, tenure, bios), expense ratio, exit load, minimum SIP, riskometer, benchmark, and other scheme facts on the page:

Chunking — Section-aware chunks (~200–400 tokens) with overlap only within the same section; keep fund manager bios intact in fund_management chunks

Embed — Use free local **BGE** embeddings via sentence-transformers (`BAAI/bge-small-en-v1.5` for the current small corpus; `bge-large-en-v1.5` optional). Groq is used for generation only, not embeddings. At query time, BGE uses a search instruction prefix on user questions.

Index — Upsert into LanceDB (`data/index/lancedb`); refresh `last_fetched_at` in `scheme_metadata.json`; atomic staging swap on re-ingest



3.6 Daily Ingestion Scheduler

**Status: Implemented** in `scheduler/daily.py` + `scheduler/status.py`.

Runs the full ingestion pipeline **daily at 10:00 AM IST** (`Asia/Kolkata`), configurable via env:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCHEDULER_HOUR` | `10` | Hour (24h) |
| `SCHEDULER_MINUTE` | `0` | Minute |
| `SCHEDULER_TIMEZONE` | `Asia/Kolkata` | IST |
| `SCHEDULER_ENABLED` | `false` | Start with FastAPI lifespan |
| `SCHEDULER_MAX_RETRIES` | `2` | Initial + one retry |
| `SCHEDULER_RETRY_DELAY_SECONDS` | `60` | Delay between retries |

**CLI:**
- `python -m scheduler.daily --daemon` — blocking scheduler
- `python -m scheduler.daily --run-now` — manual one-shot
- `python -m scheduler.daily --status` — print `scheduler_status.json`

**API:** `GET /api/scheduler/status` — last run, success/error, next schedule.

On success: atomic LanceDB swap (Phase 2) + clear retriever/scheme caches. The online API is not blocked during ingestion; it serves the previous index until swap completes.



4. End-to-End Request Flow

FormatterValidatorLLMRetrieverRAG OrchestratorRefusal HandlerQuery ClassifierChat ControllerWeb UIFormatterValidatorLLMRetrieverRAG OrchestratorRefusal HandlerQuery ClassifierChat ControllerWeb UIalt[Advisory or comparison][Factual]UserAsk questionPOST /api/chatClassify queryBlock RAGRefusal + AMFI/SEBI linkProceedResolve scheme + retrieve chunksTop-k chunks + metadataPrompt with contextDraft answerValidate grounding & complianceApproved text + citation + dateStructured responseAnswer + citation + footerUser



5. Data Model

Chunk record (LanceDB row in `chunks` table)

id: hdfc-mid-cap-fund-direct-growth#fund_management#0

text: |

  Chaitanya Choksi — Fund Manager, Feb 2023 - Present.

  Education: B.Com, CA. Experience: Prior to HDFC AMC...

scheme_name: HDFC Mid Cap Fund Direct Growth

source_url: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth

section: fund_management

last_updated: "2026-05-29"

embedding: [ ... ]



Chat request / response (API contract)

Request:

{ "message": "Who manages HDFC Defence Fund?" }



Response (factual):

{

  "answer": "HDFC Defence Fund Direct Growth is managed by Priya Ranjan (since Apr 2025), Dhruv Muchhal (since Jun 2023), and Rahul Baijal (since Apr 2025). Manager profiles and tenure are listed on the scheme page.",

  "citation_url": "https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",

  "last_updated": "2026-05-29",

  "is_refusal": false,

  "disclaimer": "Facts-only. No investment advice."

}



Response (refusal):

{

  "answer": "I can only answer factual questions about HDFC schemes in my corpus, such as expense ratio, exit load, or fund manager details. I cannot provide investment advice or recommend which fund to choose.",

  "citation_url": "https://www.amfiindia.com/investor/knowledge-center-info?faqs",

  "last_updated": "2026-05-29",

  "is_refusal": true,

  "disclaimer": "Facts-only. No investment advice."

}





6. Query Routing Matrix



7. Technology Stack (Recommended)

| Layer | Technology | Notes |
|-------|------------|-------|
| Web API | FastAPI + Uvicorn | `POST /api/chat`, `GET /health`, `GET /api/corpus`, `GET /api/scheduler/status` |
| LLM (generation) | **Groq API** (`groq` SDK) | Default `llama-3.3-70b-versatile`; facts-only RAG prompts |
| Embeddings | **BGE** via `sentence-transformers` | `BAAI/bge-small-en-v1.5` (384-dim); free, local |
| Vector store | **LanceDB** OSS | `data/index/lancedb`, table `chunks` |
| Ingestion | BeautifulSoup4, httpx | Groww HTML → parse → chunk → index |
| Scheduler | APScheduler 3.x | Daily 10:00 AM IST ingestion |
| Config | PyYAML, python-dotenv | `config/corpus.yaml`, `.env` |
| Tests | pytest | Unit + API integration |

Blocked / Not Stored

Allowed

Reject input patterns

Reject input patterns

Classifier

Anonymous factual questions

Corpus URLs only

PAN, Aadhaar, account #, OTP

Email, phone

Investment advice generation

RAG Pipeline

No processing

Refusal

Stateless API — No user accounts, chat history persistence, or analytics tied to identity (optional ephemeral in-memory UI history is acceptable)

Input sanitization — Reject or strip patterns resembling PII before LLM call

Allowlist citations — Validator ensures answer citations are corpus URLs (or fixed AMFI/SEBI URLs for refusals)

No training on user data — Queries are not used to fine-tune models in this phase

Rate limiting — Basic per-IP limits to prevent abuse and Groq API cost overrun



9. Deployment Topology

Development (local):

[Browser] → [Static UI at GET /] → [FastAPI :8000 /api/chat] → [LanceDB] → [Groq API]

                ↑

        [Daily Scheduler] → [Ingestion script (CLI)]



Production (Docker):

[Browser] → [FastAPI + UI container :8000] → [LanceDB volume data/index/lancedb] → [Groq API]

[scheduler container] → python -m scheduler.daily --daemon @ 10:00 AM IST

`docker compose up` — see README.md




Corpus refresh: Scheduler triggers ingestion **daily at 10:00 AM IST**, rebuilding LanceDB and `scheme_metadata.json` from live Groww URLs

Manual re-run: `python -m scheduler.daily --run-now` or `python -m ingestion.run`

**Scheduler env:** `SCHEDULER_*` — see `.env.example`

**LLM env (Groq):** `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_MAX_TOKENS`, `GROQ_TEMPERATURE`, `GROQ_TIMEOUT_SECONDS` — see `.env.example`



10. Non-Functional Requirements



11. Known Limitations

Corpus scope — Only five HDFC schemes on Groww; no AMFI/SEBI document ingestion in this phase

Source freshness — Answers reflect the last successful daily ingestion run; intra-day Groww updates are picked up on the next scheduled run

Third-party source — Groww is used as reference context, not HDFC AMC primary documents (KIM/SID/factsheets)

No performance analytics — Return comparisons and projections are explicitly out of scope

Scheme disambiguation — Ambiguous queries (e.g. "HDFC fund expense ratio" without naming the scheme) may require clarification or return the most similar scheme

Fund management completeness — Manager data is limited to what appears on each Groww scheme page

Document download guides — Not in current corpus unless added to a future URL list



12. Future Extensions (Out of Current Scope)

Expand corpus to 15–25 official AMC / AMFI / SEBI URLs

Add clarification turn: "Which scheme did you mean?"

Structured extraction cache (JSON facts per scheme) for numeric fields like expense ratio

Multilingual support (Hindi)

Admin dashboard for ingestion status and chunk inspection



13. Project Structure (Suggested)

m2_4/

├── docs/

│   ├── problemStatement.md

│   └── architecture.md          # this document

├── data/

│   ├── raw/                     # fetched HTML/markdown per URL

│   ├── processed/               # parsed sections & chunks

│   └── index/                   # LanceDB (lancedb/) + scheme_metadata.json

├── ingestion/

│   ├── fetch.py

│   ├── parse.py

│   ├── chunk.py

│   ├── index.py

│   └── run.py                   # ingestion entrypoint invoked by scheduler

├── scheduler/

│   └── daily.py                 # APScheduler cron @ 10:00 AM IST

│   └── status.py                # scheduler_status.json read/write

├── app/

│   ├── main.py                  # FastAPI entry

│   ├── scheme_index.py          # scheme_metadata loader + resolve_scheme()

│   ├── section_intent.py        # keyword section intent rules

│   ├── chat.py                  # handle_chat orchestration

│   ├── refusal.py               # templated refusals

│   ├── security.py              # PII detection + sanitization

│   ├── rate_limit.py            # per-IP rate limiter

│   ├── corpus_urls.py           # allowed citation URLs

│   ├── classifier.py

│   ├── retriever.py

│   ├── generator.py

│   ├── llm.py                   # Groq LLMClient

│   ├── validator.py

│   └── formatter.py

├── ui/

│   ├── index.html               # trading-terminal chat UI

│   └── app.js                   # chat client → POST /api/chat, GET /api/corpus


├── config/

│   └── corpus.yaml              # 5 URLs + scheme metadata

├── tests/

│   ├── test_classifier.py

│   ├── test_api_chat.py

│   ├── test_generator.py

│   ├── test_security.py

│   ├── test_retrieval.py

│   ├── test_refusal.py

│   ├── test_scheduler.py

│   ├── test_compliance.py

│   └── test_ui.py

└── README.md





14. Summary

The Mutual Fund FAQ Assistant is a small-corpus, compliance-first RAG system. A query classifier gates advisory and comparison questions before retrieval. Factual questions flow through scheme-aware retrieval over five indexed Groww pages in LanceDB, grounded Groq LLM generation, and a strict response formatter that enforces brevity, a single citation, and a last-updated footer. A daily scheduler triggers the offline ingestion pipeline **at 10:00 AM IST** to keep LanceDB embeddings and metadata in sync with the defined corpus. The architecture prioritizes verifiability and refusal correctness over open-ended conversational ability.



