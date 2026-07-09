# Mutual Fund FAQ Assistant — Interview Preparation Guide

This document is based on the **actual implementation** in this repository (`yashsrivastava1212/Mutual-fund`). Every technical claim below maps to real code under `app/`, `ingestion/`, `scheduler/`, `ui/`, and `config/`.

---

## Table of Contents

1. [Problem Statement & Why We Built This](#1-problem-statement--why-we-built-this)
2. [Objective & Business Value](#2-objective--business-value)
3. [End-to-End: How the Project Works](#3-end-to-end-how-the-project-works)
4. [Architecture & Workflow](#4-architecture--workflow)
5. [Complete Data Flow (User Input → Final Output)](#5-complete-data-flow-user-input--final-output)
6. [Technology Choices & Alternatives](#6-technology-choices--alternatives)
7. [RAG Pipeline (This Project)](#7-rag-pipeline-this-project)
8. [Ingestion Process](#8-ingestion-process)
9. [Chunking Strategy](#9-chunking-strategy)
10. [Embedding Model](#10-embedding-model)
11. [Vector Database](#11-vector-database)
12. [LLM Integration](#12-llm-integration)
13. [Key Implementation Decisions, Trade-offs & Challenges](#13-key-implementation-decisions-trade-offs--challenges)
14. [Theoretical Concepts (Plain English)](#14-theoretical-concepts-plain-english)
15. [Interview Preparation — Questions & Answers](#15-interview-preparation--questions--answers)

---

## 1. Problem Statement & Why We Built This

### The problem

Retail investors and support teams repeatedly ask **objective, factual** questions about mutual fund schemes:

- What is the expense ratio?
- What is the exit load?
- Who manages the fund?
- What is the benchmark or riskometer?

These answers exist on public scheme pages, but:

- Users must navigate long HTML pages manually.
- Generic chatbots may **hallucinate** numbers or give **investment advice** (legally sensitive in finance).
- Compliance requires **source citations** and clear boundaries (facts-only, no buy/sell guidance).

### Why this project exists

We built a **compliance-first, small-corpus RAG assistant** that:

1. Answers only from **five curated HDFC scheme pages** on Groww (reference product context).
2. **Refuses** advisory and comparison queries before retrieval.
3. Returns **one citation URL**, a **last-updated date** from ingested metadata, and a short disclaimer.
4. Refreshes its knowledge **daily** via a scheduled ingestion pipeline.

**Source:** `content/ProblemStatement.md`, `config/corpus.yaml`

---

## 2. Objective & Business Value

### Technical objective

Design a lightweight **Retrieval-Augmented Generation (RAG)** system that:

- Retrieves grounded context from a fixed corpus.
- Generates concise answers via an LLM under strict prompts.
- Validates outputs programmatically (sentence limit, numeric grounding, citation allowlist).

### Business value

| Stakeholder | Value |
|-------------|-------|
| **Retail investors** | Fast, cited answers to factual scheme questions |
| **Customer support** | Deflects repetitive FAQ volume with consistent messaging |
| **Compliance / product** | Hard guardrails: no advice, no comparisons, PII rejection, corpus-only citations |
| **Engineering** | Small, testable system (128 pytest tests) suitable for demo and extension |

### Explicit non-goals (current phase)

- Investment recommendations, portfolio advice, return projections
- Multi-AMC or open-web crawling
- User accounts, chat history persistence, or analytics tied to identity
- Official AMC PDFs (KIM/SID/factsheets) — out of scope; Groww pages only

---

## 3. End-to-End: How the Project Works

### Two pipelines

```
OFFLINE (daily / on-demand)          ONLINE (per user question)
────────────────────────────         ────────────────────────────
Fetch 5 Groww HTML pages             User types question in UI
    ↓                                    ↓
Parse __NEXT_DATA__ sections         POST /api/chat
    ↓                                    ↓
Section-first chunking (51 chunks)   PII check + rate limit
    ↓                                    ↓
Embed with BGE (local)               Rule-based classifier
    ↓                                    ↓
Store in LanceDB + metadata          Advisory/Comparison → refusal (no RAG)
    ↓                                    ↓
Atomic index swap                    Factual → 3-stage retrieval
                                         ↓
                                     Groq LLM generation
                                         ↓
                                     Validator + formatter
                                         ↓
                                     JSON response to UI
```

### Scale (measured in this project)

- **5 schemes**, **51 chunks** after ingestion (typical run)
- **BGE-small**: 384-dimensional embeddings
- **top_k = 3** chunks sent to LLM (up to 3 for fund-management queries)
- **128 automated tests** (`pytest`)

---

## 4. Architecture & Workflow

### Layered architecture

| Layer | Components | Files |
|-------|------------|-------|
| **Presentation** | Trading-terminal chat UI | `ui/index.html`, `ui/app.js` |
| **Application** | FastAPI, chat orchestration, rate limit, security | `app/main.py`, `app/chat.py` |
| **Compliance gate** | Classifier, refusal handler | `app/classifier.py`, `app/refusal.py` |
| **Retrieval** | Scheme resolver, section intent, LanceDB search | `app/scheme_index.py`, `app/section_intent.py`, `app/retriever.py` |
| **Generation** | Groq client, prompts | `app/generator.py`, `app/llm.py` |
| **Validation** | Grounding + format checks | `app/validator.py`, `app/formatter.py` |
| **Offline** | Fetch, parse, chunk, index, scheduler | `ingestion/*`, `scheduler/daily.py` |
| **Storage** | LanceDB, JSON metadata, raw/processed files | `data/index/lancedb`, `data/index/scheme_metadata.json` |

### Deployment (as implemented)

- **Backend:** Railway — FastAPI + LanceDB volume at `/app/data`
- **Frontend:** Vercel — static `ui/` with API rewrites / `config.js` → Railway URL
- **Scheduler:** APScheduler cron at **10:00 AM IST** (`Asia/Kolkata`)
- **Optional:** `INGEST_ON_STARTUP=true` builds index on first Railway deploy without SSH

---

## 5. Complete Data Flow (User Input → Final Output)

### Step-by-step (factual query path)

**Example:** *"What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"*

| Step | What happens | Code |
|------|--------------|------|
| 1 | User submits message in browser | `ui/app.js` → `POST /api/chat` |
| 2 | FastAPI extracts client IP, checks rate limit (30 req / 60s) | `app/rate_limit.py` |
| 3 | Message sanitized; PII patterns rejected (PAN, Aadhaar, email, phone, OTP, account #) | `app/security.py` |
| 4 | Classifier runs regex rules → `FACTUAL` | `app/classifier.py` |
| 5 | **Scheme resolution:** match query to one of 5 schemes via name/slug/alias/distinctive tokens | `app/scheme_index.py` → `resolve_scheme()` |
| 6 | **Section intent:** keywords like "expense ratio" → `expense_ratio` section (high confidence) | `app/section_intent.py` |
| 7 | Query embedded with BGE query instruction prefix | `ingestion/embeddings.py` → `embed_query()` |
| 8 | LanceDB vector search with `slug` filter; optional `section` filter; fetch_k=5 | `app/retriever.py` |
| 9 | Re-rank: distance → score; +0.15 boost if section matches intent | `app/retriever.py` |
| 10 | Top 3 chunks assembled into context block | `app/generator.py` → `build_context_block()` |
| 11 | Groq `llama-3.3-70b-versatile` generates ≤3 sentences, context-only | `app/llm.py`, `app/generator.py` |
| 12 | Validator checks: sentence count, no advice phrases, no URLs in body, numbers ⊆ context, citation in allowlist | `app/validator.py` |
| 13 | Formatter adds footer `Last updated from sources: <date>` from chunk metadata | `app/formatter.py` |
| 14 | JSON returned to UI | `app/main.py` |

**Response shape:**

```json
{
  "answer": "The expense ratio of HDFC Mid Cap Fund Direct Growth is 0.73%. Last updated from sources: 2026-06-21",
  "citation_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
  "last_updated": "2026-06-21",
  "is_refusal": false,
  "disclaimer": "Facts-only. No investment advice."
}
```

### Advisory / comparison path (no RAG)

| Step | What happens |
|------|--------------|
| Classifier → `ADVISORY` or `COMPARISON` | `app/classifier.py` |
| Templated refusal returned immediately | `app/refusal.py` |
| Citation = AMFI education URL (fixed) | No LanceDB or Groq call for fund facts |
| `is_refusal: true` | |

### Empty retrieval path

If no scheme matches, LanceDB is missing, or embedding fails:

- Retriever returns `[]`
- User gets **insufficient-context template** (no Groq call if no chunks)
- If Groq is configured but generation/validation fails → **fallback answer** from chunk text or generic message

**Source:** `app/chat.py`, `app/retriever.py`

---

## 6. Technology Choices & Alternatives

| Technology | Why we chose it | Alternatives considered | Why not (in this project) |
|------------|-----------------|----------------------|---------------------------|
| **FastAPI** | Async-ready, automatic OpenAPI, Pydantic models, serves static UI | Flask, Django | Flask lacks built-in typed models; Django heavy for one endpoint |
| **Groq API** (`llama-3.3-70b-versatile`) | Fast inference, low cost for demo; official Python SDK | OpenAI GPT-4, Anthropic Claude, local Llama, xAI Grok | OpenAI adds cost; local LLM heavy on Railway; **xAI/Grok was replaced** after key format mismatch (`gsk_` = Groq) |
| **BGE-small** (`BAAI/bge-small-en-v1.5`) | Free, local, 384-dim; corpus is tiny (~51 chunks, ~30 avg tokens) | OpenAI `text-embedding-3-small`, BGE-large, Cohere embed | Paid API unnecessary; BGE-large overkill at this scale (`config/embedding_models.py` auto preset) |
| **LanceDB** | File-backed OSS vector store; prebuilt wheels on Windows | ChromaDB, Pinecone, FAISS-only, pgvector | **ChromaDB dropped** — Windows build issues; Pinecone adds hosted cost/complexity for 51 vectors |
| **sentence-transformers** | Standard wrapper for BGE models | Raw transformers + manual pooling | More boilerplate for same result |
| **BeautifulSoup4 + httpx** | Parse Groww `__NEXT_DATA__`; async-capable HTTP client | Scrapy, Playwright | Pages are SSR JSON-in-HTML; no browser needed |
| **APScheduler** | Simple cron for daily 10:00 AM IST ingestion | Celery, cron OS, GitHub Actions | Celery needs broker; OS cron harder in Railway container |
| **Rule-based classifier** | Deterministic, testable, zero latency, no extra LLM cost | LLM classifier, hybrid | Compliance path must be predictable; regex covers known advisory/comparison phrases |
| **pytest** | Fast unit + API integration tests | unittest | Team standard for Python ML apps |
| **Railway + Vercel** | Simple split deploy: API+volume vs static UI | Single Docker host, AWS ECS | Documented in `deployment.md` for low-ops demo |

---

## 7. RAG Pipeline (This Project)

### What “RAG” means here

**Retrieval-Augmented Generation** = retrieve relevant documents first, then ask the LLM to answer **only from those documents**.

We do **not** rely on the LLM’s parametric memory for fund facts.

### Our RAG stages

```
Query
  → [Gate] Classifier (advisory/comparison blocked)
  → [Retrieve] Scheme match + section intent + vector search
  → [Augment] Build prompt with top-k chunk texts + metadata
  → [Generate] Groq completion with strict system prompt
  → [Validate] Programmatic grounding checks
  → [Format] Citation, last_updated, disclaimer
```

### Prompt constraints (`app/generator.py`)

System prompt enforces:

- Context-only answers
- Max 3 short sentences
- No advice, comparisons, return projections
- No URLs in answer body (citation handled separately)

### Grounding validation (`app/validator.py`)

- Any **numeric value** in the answer must appear in the retrieved context
- Citation URL must be one of the **5 corpus Groww URLs**
- Banned advice keywords rejected post-generation

### When Groq is NOT called

- Advisory / comparison queries (refusal path)
- No chunks retrieved (insufficient-context message)
- Extractive fallback possible in tests when `GROQ_API_KEY` unset (`app/chat.py` → `_extractive_fallback`)

---

## 8. Ingestion Process

### Orchestration

Entry point: `ingestion/run.py` → `run_ingestion()`

```
Step 1/4: fetch   → ingestion/fetch.py     (httpx GET, 5 URLs, rate delay)
Step 2/4: parse   → ingestion/parse.py     (BeautifulSoup → mfServerSideData)
Step 3/4: chunk   → ingestion/chunk.py     (section-first chunking)
Step 4/4: index   → ingestion/index.py     (BGE embed → LanceDB + metadata)
```

### Fetch (`ingestion/fetch.py`)

- Reads URLs from `config/corpus.yaml`
- Saves raw HTML to `data/raw/<slug>.html`
- Fails pipeline if any of 5 fetches fail

### Parse (`ingestion/parse.py`)

- Extracts JSON from `<script id="__NEXT_DATA__">` → `props.pageProps.mfServerSideData`
- Builds structured sections: `expense_ratio`, `exit_load`, `minimum_sip`, `fund_management`, `benchmark`, `riskometer`, etc.
- Output: `data/processed/<slug>.json`

### Index (`ingestion/index.py`)

- Embeds all chunks with `embed_documents()` (no query instruction for documents)
- Writes LanceDB table `chunks` with vector column
- Builds `scheme_metadata.json` (scheme list + `last_fetched_at` per slug)
- **Atomic swap:** build in `data/index/staging/`, then rename into live `data/index/lancedb` so API never serves a half-written index

### Scheduling

- `scheduler/daily.py` — cron **10:00 AM IST**
- On success: clears retriever/scheme/corpus caches
- `INGEST_ON_STARTUP=true` — background thread runs ingestion if index missing (`app/main.py` lifespan)

---

## 9. Chunking Strategy

### Strategy: **section-first** (not fixed token windows across sections)

**File:** `ingestion/chunk.py`

| Rule | Implementation |
|------|----------------|
| One chunk per factual section | `expense_ratio`, `exit_load`, `minimum_sip`, etc. |
| `fund_management` split per manager | One chunk per manager with name, tenure, education, experience |
| Skip empty/noise | e.g. null `lock_in` section skipped |
| Long sections split | `MAX_SECTION_TOKENS = 400`, `OVERLAP_TOKENS = 50` word-based split |
| Chunk prefix | `"<Scheme Name> \| Section: <section>\n<body>"` for embedding context |
| Chunk ID format | `{slug}#{section}#{index}` e.g. `hdfc-mid-cap-fund-direct-growth#expense_ratio#0` |

### Why section-first (not naive 512-token sliding window)?

1. **Mutual fund pages are already sectional** — expense ratio and exit load are distinct facts; merging them hurts retrieval precision.
2. **Fund managers must stay intact** — splitting a manager bio mid-sentence would break “who manages” queries.
3. **Small corpus** — 51 chunks total; section boundaries give interpretable retrieval filters (`section = 'expense_ratio'`).
4. **Enables hybrid retrieval** — keyword section intent + vector search re-rank (`app/section_intent.py`).

### Typical result

- **51 chunks** across 5 schemes (~10 per scheme, + extra for multiple managers)

---

## 10. Embedding Model

### Model used

**`BAAI/bge-small-en-v1.5`** (default via `EMBEDDING_PRESET=auto`)

| Property | Value |
|----------|-------|
| Dimensions | 384 |
| Normalization | Yes |
| Query instruction | `"Represent this sentence for searching relevant passages: "` + query (BGE asymmetric search) |
| Library | `sentence-transformers` |

### Auto selection logic (`config/embedding_models.py`)

`EMBEDDING_PRESET=auto` picks:

- **BGE-small** when corpus is small (current: 51 chunks, ~30 avg tokens, 65 max)
- **BGE-large** only if chunk count ≥ 500, or max tokens ≥ 400, or avg tokens ≥ 150

At 51 chunks, **small is correctly auto-selected**.

### Why BGE over OpenAI embeddings?

- **Cost:** $0 per query at inference (model runs locally on API server)
- **Privacy:** Chunk text never sent to a third-party embed API
- **Latency trade-off:** First query loads model into memory (~10s on cold start on Railway) — acceptable for this demo scale

### Why small over large here?

- 51 chunks do not need 1024-dim large model capacity
- Faster embedding at ingest and query time
- Lower RAM on Railway

---

## 11. Vector Database

### Store: **LanceDB OSS**

| Property | Value |
|----------|-------|
| Path | `data/index/lancedb` |
| Table | `chunks` |
| Search | `table.search(query_vector).where("slug = '...'").limit(5)` |
| Distance | Converted to score: `max(0, 1 - distance)` |

### Three-stage retrieval (hybrid)

1. **Metadata filter — scheme:** `resolve_scheme()` narrows to one `slug` (or returns empty)
2. **Metadata boost — section:** `detect_section_intent()` → optional LanceDB `section` filter (high confidence) or +0.15 re-rank boost (medium)
3. **Semantic search:** BGE query embedding vs stored chunk vectors

### Why LanceDB over ChromaDB?

**Documented project decision:** ChromaDB caused **Windows build issues** during development. LanceDB provides:

- File-backed persistence (fits `data/` volume on Railway)
- Simple Python API
- Sufficient for **<100 vectors** without a dedicated vector DB server

### Why not Pinecone / Weaviate?

- Hosted cost and network hop unnecessary for 51 vectors
- Adds deployment secret management for marginal benefit at this scale

### Atomic index swap

Production safety: ingestion writes to **staging**, then atomically replaces live LanceDB directory. Online API continues serving old index until swap completes (`ingestion/index.py` → `_atomic_replace_dir`).

---

## 12. LLM Integration

### Provider: **Groq**

| Setting | Default |
|---------|---------|
| SDK | `groq` Python package |
| Model | `llama-3.3-70b-versatile` |
| Max tokens | 512 |
| Temperature | 0.1 |
| Retries | 3 with exponential backoff (`app/llm.py`) |

### Role in pipeline

Groq is used **only for answer generation** on the factual path — not for:

- Embeddings (BGE local)
- Classification (regex rules)
- Section intent (keyword rules)

### Why Groq?

- Fast inference for interactive chat demo
- Simple API key setup (`GROQ_API_KEY`)
- Good instruction-following on structured RAG prompts

### Migration note (actual project history)

Project initially referenced xAI/Grok; switched to **Groq** when API keys were `gsk_` format (Groq console). Code retains backward-compatible env fallbacks (`GROK_MODEL` → `GROQ_MODEL`) in `config/settings.py`.

### Failure handling

- Generation exception → `FALLBACK_ANSWER` string (`app/chat.py`)
- Validation failure → fallback or `format_from_chunks` extractive path
- Missing API key → extractive fallback from top chunk text (used in tests)

---

## 13. Key Implementation Decisions, Trade-offs & Challenges

### Decisions

| Decision | Rationale |
|----------|-----------|
| **Classifier before retrieval** | Prevents accidental RAG on “should I buy” queries — compliance priority |
| **Rule-based over LLM classifier** | Deterministic, 100% reproducible in tests |
| **Scheme resolution before vector search** | Prevents cross-scheme contamination (e.g. mid-cap answer for large-cap query) |
| **Stateless API** | No user accounts; `{ "message": string }` only |
| **Citation allowlist** | Validator rejects citations not in corpus URLs |
| **Number grounding check** | LLM cannot invent expense ratio not present in chunks |
| **Single AMC, 5 schemes** | Controlled demo corpus; simplifies evaluation |

### Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Local BGE embeddings | Free, private | RAM + cold-start latency on Railway |
| Small corpus on Groww | Fast to build, easy to cite | Not authoritative AMC primary source |
| No clarifying dialog | Simpler API | Ambiguous queries (“HDFC fund expense ratio”) may fail scheme tie-break → empty retrieval |
| In-memory rate limiter | Simple | Resets on redeploy; not shared across replicas |
| Regex classifier | Fast, testable | May miss paraphrased advisory language; new patterns need code updates |

### Challenges encountered (real)

1. **ChromaDB → LanceDB** — Windows native dependency pain
2. **xAI → Groq** — provider/key mismatch during integration
3. **British “defence” vs American “defense”** — normalized in `scheme_index.py` (`defense` → `defence`)
4. **Scheme tie resolution** — equal scores for generic queries return `None` (by design, per edge-case spec)
5. **Railway first deploy** — empty volume caused `FileNotFoundError` on `scheme_metadata.json`; fixed with graceful empty metadata + `INGEST_ON_STARTUP`
6. **Split deploy (Vercel + Railway)** — `vercel.json` rewrites + `config.js` `API_BASE` for cross-origin API
7. **UI script path** — `./app.js` on Vercel vs `/app.js` route on FastAPI for local dev

---

## 14. Theoretical Concepts (Plain English)

### RAG (Retrieval-Augmented Generation)

**What:** Combine a search step with an LLM so answers cite real documents.  
**Why:** LLMs hallucinate facts; retrieval grounds them.  
**Here:** We retrieve top 3 Groww-derived chunks, then Groq writes the answer.

### Embeddings

**What:** Convert text to a numeric vector capturing semantic meaning.  
**Why:** Lets us find “expense ratio” chunks even if user says “TER”.  
**Here:** BGE-small, 384 floats per chunk/query; cosine-style distance in LanceDB.

### Vector database

**What:** Stores embeddings and finds nearest neighbors quickly.  
**Why:** Linear scan over 51 chunks is fine, but LanceDB gives a standard search API + persistence.  
**Here:** LanceDB table `chunks` with `vector` column + metadata filters on `slug` and `section`.

### Semantic search

**What:** Search by meaning, not exact keywords.  
**Here:** Hybrid — keywords pick section; vectors pick best chunk within scheme.

### Chunking

**What:** Split large documents into retrieval units.  
**Why:** Entire HTML page is too big for LLM context and too noisy for precision.  
**Here:** Section-first + per-manager splits.

### LLM temperature

**What:** Controls randomness (0 = deterministic-ish, 1 = creative).  
**Here:** `0.1` for factual, repeatable answers.

### Grounding / validation

**What:** Check output against source text.  
**Here:** Numbers in answer must appear in retrieved context; max 3 sentences; no advice keywords.

### Compliance refusal

**What:** Refuse harmful or out-of-scope requests without invoking RAG.  
**Here:** Advisory/comparison templates with AMFI link — no fund data retrieved.

---

## 15. Interview Preparation — Questions & Answers

### A. Project overview

**Q1: Describe this project in 30 seconds.**

**A:** It is a compliance-first RAG chatbot for five HDFC mutual fund schemes on Groww. Offline, we fetch and parse scheme pages daily, chunk them section-wise, embed with BGE, and store in LanceDB. Online, user questions are classified — advisory and comparison queries are refused without retrieval. Factual queries go through scheme-aware hybrid retrieval, Groq generates a short grounded answer, a validator checks numbers and format, and the UI shows one citation plus a last-updated footer.

---

**Q2: Who are the target users and what problem does it solve?**

**A:** Retail investors and support teams who need quick factual answers (expense ratio, exit load, fund manager) without navigating long web pages. It solves repetitive FAQ handling while staying facts-only — no investment advice — with mandatory source citations.

**Follow-up: Why not use ChatGPT directly?**  
**A:** A generic LLM can hallucinate fund numbers, give buy/sell advice, and cannot guarantee citations from our approved corpus. RAG + classifier + validator enforces corpus-only facts and compliance boundaries.

---

### B. Architecture

**Q3: Walk me through the system architecture.**

**A:** Four layers: (1) Static UI on Vercel calling Railway API; (2) FastAPI application with security, rate limiting, and chat orchestration; (3) Retrieval layer — scheme index, section intent, LanceDB vector search; (4) Offline ingestion pipeline with daily scheduler. Groq is generation-only; BGE handles embeddings locally.

**Follow-up: Why split Vercel and Railway?**  
**A:** Frontend is static HTML/JS — cheap to host on Vercel CDN. Backend needs Python, LanceDB files on disk, embedding model RAM, and Groq API calls — fits a Railway container with a persistent volume at `/app/data`.

---

**Q4: What API endpoints exist and what do they do?**

**A:**

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat` | Main chat — classify, RAG or refuse, return JSON |
| `GET /health` | Ops check — `llm_configured`, `index_ready`, scheme count |
| `GET /api/corpus` | Public scheme list for UI watchlist |
| `GET /api/scheduler/status` | Last ingestion run metadata |
| `GET /` | Serves chat UI |

---

### C. RAG & retrieval

**Q5: Explain your RAG pipeline step by step.**

**A:** (1) Classify query — if advisory/comparison, refuse. (2) Resolve scheme from `scheme_metadata.json` using name, slug, alias, or distinctive token matching. (3) Detect section intent from keywords. (4) Embed query with BGE query instruction. (5) LanceDB search filtered by `slug`, optionally by `section`, fetch 5, re-rank with section boost, take top 3. (6) Build context block. (7) Groq generates answer. (8) Validate sentences, numbers, citation. (9) Format with last-updated footer.

---

**Q6: What is “hybrid retrieval” in your project?**

**A:** We combine **metadata filtering** (scheme slug, optional section), **keyword-based intent** (section_intent rules), and **dense vector search** (BGE embeddings). Pure vector search alone might return a semantically similar but wrong section; section intent boosts or filters the correct section (e.g. `expense_ratio` for “what is the TER”).

**Follow-up: What is `SECTION_SCORE_BOOST`?**  
**A:** `0.15` added to the re-rank score when the chunk’s `section` matches detected intent — implemented in `app/retriever.py` `_rerank()`.

---

**Q7: What happens if the user asks about a scheme not in the corpus?**

**A:** `resolve_scheme()` returns `None`, retriever returns `[]`, and `handle_factual_query` returns an insufficient-context message asking the user to name one of the five HDFC schemes. No Groq generation with empty context.

---

**Q8: How do you prevent cross-scheme contamination?**

**A:** Every LanceDB search includes `where slug = '<resolved_slug>'`. Scheme resolution must happen first. Tests verify mid-cap queries never return large-cap chunks (R-20, R-21 in edge-case matrix).

---

### D. Chunking & embeddings

**Q9: Why section-first chunking instead of fixed-size windows?**

**A:** Groww pages are structured by section. Section-first keeps expense ratio separate from exit load, and fund managers stay in dedicated chunks. With only 51 chunks, interpretable sections also enable metadata filters. Fixed windows would mix unrelated facts and hurt precision.

---

**Q10: Why BGE-small and not OpenAI embeddings?**

**A:** 51 chunks with ~30 average tokens — BGE-small is free, runs locally, and auto-selected by `EMBEDDING_PRESET=auto`. OpenAI embeddings add API cost and send corpus text externally with no meaningful accuracy gain at this scale.

**Follow-up: What is the BGE query instruction?**  
**A:** BGE is asymmetric — queries and documents embed differently. We prefix queries with `"Represent this sentence for searching relevant passages: "` (`BGE_QUERY_INSTRUCTION` in `config/embedding_models.py`); documents embed without that prefix.

---

### E. Vector DB & storage

**Q11: Why LanceDB over ChromaDB or Pinecone?**

**A:** LanceDB is file-backed, worked on Windows dev machines, and needs no separate server for 51 vectors. ChromaDB had build issues on Windows in this project. Pinecone is overkill for a demo corpus and adds hosted cost.

---

**Q12: How do you update the index without downtime?**

**A:** Ingestion writes to `data/index/staging/lancedb`, then `_atomic_replace_dir()` swaps staging into live `data/index/lancedb`. API keeps serving the old index until swap completes. Scheduler clears in-memory caches after success.

---

### F. LLM & compliance

**Q13: Why Groq and model `llama-3.3-70b-versatile`?**

**A:** Groq provides fast, cost-effective inference for a facts-only demo. Temperature 0.1, max 512 tokens, strict system prompt limits creativity. Project migrated from xAI/Grok to Groq based on actual API key format used.

---

**Q14: How do you enforce “facts-only, no investment advice”?**

**A:** Three layers: (1) **Pre-retrieval classifier** — regex blocks advisory/comparison. (2) **Prompt** — system instructions forbid advice. (3) **Post-generation validator** — banned keywords, max 3 sentences, numeric grounding. Refusals use fixed templates with AMFI link, not Groq fund facts.

**Follow-up: Can the classifier miss an advisory question?**  
**A:** Yes — regex is not exhaustive. New advisory phrasing may slip through to RAG. Mitigation: validator banned phrases and conservative system prompt. Production improvement would be hybrid LLM classifier with audit logging.

---

**Q15: Explain the validator’s number grounding check.**

**A:** We extract numbers (including percentages) from the LLM answer and from the retrieved context. Every answer number must be a subset of context numbers. If the model outputs `0.85%` but context only has `0.73%`, validation fails and we use a fallback answer.

---

**Q16: How do you handle PII?**

**A:** `app/security.py` regex-detects PAN, Aadhaar, email, phone, OTP, bank account patterns before any LLM call. API returns HTTP 400 with a clear error. UI never prompts for PII.

---

### G. Ingestion & scheduling

**Q17: How does ingestion work?**

**A:** Four steps: fetch HTML from 5 Groww URLs → parse `__NEXT_DATA__` JSON into sections → section-first chunking → BGE embed and LanceDB index with atomic swap. Entry: `python -m ingestion.run` or scheduler.

---

**Q18: How do you keep data fresh?**

**A:** APScheduler runs daily at **10:00 AM IST** (`scheduler/daily.py`). `SCHEDULER_ENABLED=true` starts cron inside FastAPI lifespan. `INGEST_ON_STARTUP=true` runs ingestion on first deploy if index is missing. `last_updated` in responses comes from chunk metadata, not the LLM.

---

**Q19: What is stored in `scheme_metadata.json`?**

**A:** Scheme list with slug, name, category, source URL, aliases, and `last_fetched_at` per scheme. Used by `resolve_scheme()` for query-to-scheme matching — separate from LanceDB vectors.

---

### H. Testing & quality

**Q20: How did you test this system?**

**A:** 128 pytest tests: classifier, retrieval, refusal, API chat, compliance, ingestion, scheduler, UI, security. Edge cases documented in `content/edge-case.md` (advisory refusal, PII, scheme ties, cross-scheme isolation).

---

**Q21: What are known limitations you would disclose in an interview?**

**A:** (1) Corpus is Groww pages only — not official AMC PDFs. (2) No clarifying dialog for ambiguous schemes. (3) English only. (4) Data stale until next ingestion. (5) In-memory rate limiter not multi-instance safe. (6) Regex classifier not semantically complete.

---

### I. Design & scalability

**Q22: How would you scale this to 500+ schemes?**

**A:** Would need: stronger scheme disambiguation (clarifying questions or embedding-based scheme resolver), possibly BGE-large or hybrid BM25 + vectors, managed vector DB with ANN indexing, async ingestion queue, Redis rate limiting, and caching hot embeddings. Current section-first chunking still applies but chunk count drives embedding model auto-selection thresholds in `embedding_models.py`.

---

**Q23: Why is the API stateless?**

**A:** Compliance and simplicity — no user accounts, no stored chat history tied to identity, no PII database. Each request is `{ "message": string }` only. Optional UI-side ephemeral display history is fine.

---

**Q24: What would you improve next?**

**A:** Based on actual gaps: (1) clarifying turn for ambiguous scheme queries; (2) expand corpus to official AMC docs; (3) hybrid BM25 + dense retrieval; (4) LLM classifier fallback with logging; (5) Redis rate limiter for multi-replica deploy; (6) observability (latency traces, retrieval scores in logs).

---

### J. Behavioral / ownership

**Q25: Tell me about a technical challenge you faced on this project.**

**A (example answer):** We initially chose ChromaDB but hit Windows native build failures during local development. I migrated the vector store to LanceDB with the same chunk schema, added atomic staging swap for safe re-ingestion, and updated 128 tests to pass. On deployment, Railway had an empty volume — factual queries crashed on missing `scheme_metadata.json`. I added graceful handling, `index_ready` on `/health`, and `INGEST_ON_STARTUP` so the first deploy builds the index without manual SSH.

---

**Q26: How do you explain RAG to a non-technical stakeholder?**

**A:** Instead of letting the AI guess from memory, we first look up the official scheme page text we downloaded yesterday, then the AI writes a short answer using only that text — like an open-book exam with one allowed textbook and a mandatory source link.

---

## Quick Reference Card (memorize before interview)

| Item | Value |
|------|-------|
| Corpus | 5 HDFC schemes on Groww |
| Chunks | ~51 |
| Embedding | BAAI/bge-small-en-v1.5, 384-dim |
| Vector DB | LanceDB, table `chunks` |
| LLM | Groq, llama-3.3-70b-versatile |
| Retrieval | Scheme → section intent → vector search → re-rank → top 3 |
| Classifier | Rule-based regex (comparison before advisory) |
| Max answer | 3 sentences |
| Rate limit | 30 requests / 60s per IP |
| Scheduler | 10:00 AM IST daily |
| Tests | 128 pytest |
| Deploy | Railway (API) + Vercel (UI) |

---

## Files to skim before interview

| Topic | File |
|-------|------|
| Chat orchestration | `app/chat.py` |
| Classifier | `app/classifier.py` |
| Retriever | `app/retriever.py` |
| Generator + prompts | `app/generator.py` |
| Validator | `app/validator.py` |
| Chunking | `ingestion/chunk.py` |
| Indexing | `ingestion/index.py` |
| Corpus config | `config/corpus.yaml` |
| Architecture doc | `content/Architecture.md` |
| Edge cases | `content/edge-case.md` |

---

*Disclaimer for interviews: This assistant is facts-only, uses Groww as reference context, and is not a substitute for official AMC disclosures or professional investment advice.*
