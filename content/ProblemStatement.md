Problem Statement

Problem Statement: Mutual Fund FAQ Assistant (Facts-Only Q&A)

Overview

The objective of this project is to build a facts-only FAQ assistant for mutual fund schemes, using Groww as the reference product context. The assistant will answer objective, verifiable queries related to mutual funds by retrieving information exclusively from official public sources, such as AMC (Asset Management Company) websites, AMFI, and SEBI.

The system must strictly avoid providing investment advice, opinions, or recommendations. Every response must include a single, clear source link and adhere to defined constraints around clarity, accuracy, and compliance.



Objective

Design and implement a lightweight Retrieval-Augmented Generation (RAG)-based assistant that:

Answers factual queries about mutual fund schemes

Uses a curated corpus of official documents

Provides concise, source-backed responses



Target Users

Retail investors comparing mutual fund schemes

Customer support and content teams handling repetitive mutual fund queries



Scope of Work

1. Corpus Definition

Select one Asset Management Company (AMC): **HDFC Mutual Fund**

Limit the active corpus to **five Groww scheme detail pages** (reference product context):

| Scheme | URL |
|--------|-----|
| HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| HDFC Gold ETF Fund of Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| HDFC Defence Fund Direct Growth | https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth |

Content is ingested from these pages only. Official AMC documents (KIM, SID, factsheets), AMFI/SEBI guidance pages, and statement download guides are **out of scope** for this phase but may be added in a future corpus expansion.

**Ingestion & chunking approach:**

1. **Fetch** — download each Groww scheme page daily
2. **Parse** — extract structured sections from Groww `mfServerSideData` (expense ratio, exit load, fund management, benchmark, etc.)
3. **Chunk** — section-first strategy:
   - One chunk per factual section (expense ratio, exit load, minimum SIP, benchmark, riskometer, etc.)
   - `fund_management` split into **one chunk per fund manager** (names, tenure, bios kept intact)
   - Skip empty/noise sections (e.g. null lock-in)
4. **Index** — embed chunks locally with **BGE** (free; `bge-small` auto-selected for current chunk size) and store in LanceDB for scheme-filtered retrieval



2. FAQ Assistant Requirements

The assistant must:

Answer facts-only queries, such as:

Expense ratio of a scheme

Exit load details

Minimum SIP amount

ELSS lock-in period

Riskometer classification

Benchmark index

**Fund management details** — who manages the scheme, manager names, tenure, and profile information as published on the scheme page

Process to download statements or capital gains reports (out of scope unless added to corpus in a future phase)

Ensure:

Each response is limited to a maximum of 3 sentences

Each response includes exactly one citation link

Each response includes a footer:
 “Last updated from sources: <date>”



3. Refusal Handling

The assistant must refuse non-factual or advisory queries, such as:

“Should I invest in this fund?”

“Which fund is better?”

Refusal responses should:

Be polite and clearly worded

Reinforce the facts-only limitation

Provide a relevant educational link (e.g., AMFI or SEBI resource)



4. User Interface (Minimal)

The solution should include a simple interface with:

A welcome message

Three example questions (covering scheme facts and fund management, e.g. expense ratio, exit load, who manages the fund)

A visible disclaimer:
 “Facts-only. No investment advice.”



Constraints

Data and Sources

Use only the five defined Groww scheme pages as the answer corpus

Refusal responses may link to AMFI or SEBI educational resources

Do not use third-party blogs or other aggregator websites beyond the defined corpus

Privacy and Security

Do not collect, store, or process:

PAN or Aadhaar numbers

Account numbers

OTPs

Email addresses or phone numbers

Content Restrictions

No investment advice or recommendations

No performance comparisons or return calculations

For performance-related queries, provide a link to the official factsheet only

Transparency

Responses must be short, factual, and verifiable

Every answer must include a source link and last updated date



Expected Deliverables

README Document

Setup instructions

Selected AMC and schemes (HDFC — 5 Groww URLs listed in Scope)

Architecture overview (RAG approach)

Known limitations

Disclaimer Snippet

“Facts-only. No investment advice.”



Success Criteria

Accurate retrieval of factual mutual fund information, including fund management details

Strict adherence to facts-only responses

Consistent inclusion of valid source citations

Proper refusal of advisory queries

Clean, minimal, and user-friendly interface



Summary

The goal is to build a trustworthy, transparent, and compliant mutual fund FAQ assistant that prioritizes accuracy over intelligence. The system should ensure that users receive only verified, source-backed financial information, without any advisory bias or speculative content.



