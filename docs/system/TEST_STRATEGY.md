# Test Plan & Strategy

## Overview

This document outlines the testing strategy for the Substack Digest Agent. It covers edge cases, security validation, and performance benchmarks to ensure the system is robust enough for daily unattended operation.

## 1. Ingestion Layer Testing

### 1.1 RSS Feed Edge Cases

- **Malformed XML**: Feed returns 200 OK but contains invalid XML structure.
  - _Expected_: Parser catches `feedparser.bozo` exception, logs warning, returns failure result without crashing.
- **Empty Feeds**: Valid XML but no `<item>` or `<entry>` elements.
  - _Expected_: Returns success with 0 articles.
- **Future Dates**: Articles with published dates in the future (e.g., timezone bugs).
  - _Expected_: Accepted but logged; ensure timezone normalization converts everything to UTC.
- **Ancient Dates**: Articles from 1970 or missing dates.
  - _Expected_: `_parse_entry_date` handles missing/invalid dates gracefully (skips or defaults to now depending on policy).

### 1.2 Content Extraction & Security

- **Malicious Content (XSS)**: Feeds containing `<script>`, `<iframe>`, or `javascript:` links.
  - _Expected_: `clean_text` and `BeautifulSoup` sanitization successfully strip all executable content.
- **Huge Payloads**: Feeds serving multi-megabyte content blobs.
  - _Expected_: `httpx` timeout limits prevents hanging; massive text blobs are truncated or handled by DB limits.
- **Reflected Content**: Links that redirect to localhost or internal network IPs (SSRF).
  - _Expected_: Not strictly critical for local CLI app, but `httpx` should ideally follow redirects safely.

### 1.3 Network Resilience

- **Partial Outages**: Network drops mid-fetch.
  - _Expected_: `fetch_all_feeds` continues processing other feeds; failed feed is reported in `IngestResult.errors`.
- **Rate Limiting**: Substack returns 429 Too Many Requests.
  - _Expected_: Backoff or failure logged.

## 2. Storage Layer Testing

### 2.1 Database Integrity

- **Concurrent Access**: Run ingestion while a user queries the DB (simulated).
  - _Expected_: WAL mode handles concurrency without `database is locked` errors.
- **Schema Migration**: (Future) adding columns for vector embeddings.
  - _Expected_: Migration script runs non-destructively.

### 2.2 Performance

- **Volume Test**: Insert 10,000 articles.
  - _Expected_: `get_articles_since` returns sub-100ms response thanks to indexes.

## 3. Analysis Layer Testing (Phase 2)

### 3.1 LLM Failure Modes

- **Context Window Exceeded**: Article text larger than Claude's token limit.
  - _Expected_: Truncate content intelligently before sending to API to avoid 400 errors.
- **API Outages**: 5xx errors from Anthropic.
  - _Expected_: Retry with exponential backoff; mark article as 'pending_retry' rather than 'failed'.
- **Hallucination Checks**: (Manual) Verify summaries don't invent facts.

### 3.2 Summarization Quality

- **Empty Content**: Article with only an image or title.
  - _Expected_: Skip summarization or generate "Image only post" note.
- **Non-English Content**: Feeds in other languages.
  - _Expected_: Claude typically handles this, but prompt should enforce English output.

## 4. Delivery Layer Testing (Phase 3)

### 4.1 Email Rendering

- **Client Compatibility**: Render HTML in Gmail, Apple Mail, Outlook.
  - _Expected_: Layout doesn't break; dark mode is readable.
- **Truncation**: Email size > 102KB (Gmail clipping limit).
  - _Expected_: warning or strict size limits on digest.

## 5. Automated Test Suite Plan

We will expand `tests/` to include:

- `tests/test_ingest_edge_cases.py`: Mocks for malformed feeds.
- `tests/test_storage_performance.py`: Benchmarks for DB.
- `tests/test_analyze_mock.py`: Mocked LLM responses to test pipeline logic without API costs.
