# Project Implementation TODO

## Phase 0: Project Setup & Foundation

- [x] **0.1 Initialize Project**
  - [x] Initialize `uv` project (`uv init`)
  - [x] Create directory structure (`src/{ingest,analyze,deliver,storage}`, `config`, `tests`, `scripts`)
  - [x] Create `__init__.py` files

- [x] **0.2 Configure Dependencies**
  - [x] Update `pyproject.toml` with dependencies
  - [x] Run `uv sync` to install dependencies
  - [x] Run `uv sync --dev` to install dev dependencies

- [x] **0.3 Environment Configuration**
  - [x] Create `.env.example` template
  - [x] Create `.env` (user to fill in keys)
  - [x] Add `.env` to `.gitignore`

- [x] **0.4 Configuration System**
  - [x] Create `src/config.py`
  - [x] Test configuration loads correctly

- [x] **0.5 Data Models**
  - [x] Create `src/models.py`

- [x] **0.6 Sample Feed Configuration**
  - [x] Create `config/feeds.yaml`

- [x] **0.7 Logging Setup**
  - [x] Create `src/logging_config.py`

- [x] **0.8 Git Setup**
  - [x] Create `.gitignore`
  - [x] (Skip `git init` as already in a repo)

- [x] **0.9 Verify Setup**
  - [x] Create `scripts/verify_setup.py`
  - [x] Run `uv run python scripts/verify_setup.py`

## Phase 1: Ingest (Completed)

- [x] **1.1 Database Schema**
  - [x] Create `src/storage/db.py`
  - [x] Test database creation
- [x] **1.2 Feed Fetcher**
  - [x] Create `src/ingest/feeds.py`
  - [x] Test with single feed
- [x] **1.3 Content Parser**
  - [x] Create `src/ingest/parser.py`
  - [x] Test content extraction
- [x] **1.4 Ingestion Orchestrator**
  - [x] Create `src/ingest/__init__.py`
- [x] **1.5 Verification**
  - [x] Create `scripts/test_ingest.py`
  - [x] Run manual ingestion test
  - [x] Create `tests/test_ingest.py`
  - [x] Run unit tests

## Phase 2: Analyze (Completed)

- [x] **2.1 Prompt Engineering**
  - [x] Create `src/analyze/prompts.py`
- [x] **2.2 Summarizer Engine**
  - [x] Create `src/analyze/summarizer.py`
  - [x] Implement robust JSON parsing
- [x] **2.3 Digest Builder**
  - [x] Create `src/analyze/digest_builder.py`
  - [x] Implement synthesis logic
- [x] **2.4 Orchestration**
  - [x] Create `src/analyze/__init__.py`
- [x] **2.5 Analysis Verification**
  - [x] Create `scripts/test_analyze.py`
  - [x] Run manual analysis test
  - [x] Create `tests/test_analyze.py`
  - [x] Run unit tests

## Phase 3: Deliver (Completed)

- [x] **3.1 Templates**
  - [x] Create `src/deliver/templates/base.html`
  - [x] Create `src/deliver/templates/digest.html`
  - [x] Create `src/deliver/templates/digest.txt`
- [x] **3.2 Renderer**
  - [x] Create `src/deliver/renderer.py`
  - [x] Test local rendering
- [x] **3.3 Email Sender**
  - [x] Create `src/deliver/email.py`
  - [x] Integration with Resend
- [x] **3.4 Delivery Verification**
  - [x] Create `scripts/preview_email.py`
  - [x] Create `scripts/test_email.py`
  - [x] verify visual layout
  - [x] verify actual delivery

## Phase 4: Orchestrate (Completed)

- [x] **4.1 CLI Interface**
  - [x] Create `src/cli.py` (Typer/Rich)
  - [x] Configure `pyproject.toml` entry point
- [x] **4.2 Scheduling**
  - [x] Create `scripts/setup_cron.py`
  - [x] Create `scripts/setup_launchd.py`
- [x] **4.3 Operations**
  - [x] Create `scripts/healthcheck.py`
  - [x] Verify `digest` command functionality

## Phase 6: Refactor (Current)

- [ ] **6.1 Switch to Gemini**
  - [ ] Update dependencies (`google-generativeai`)
  - [ ] Update `src/config.py`
  - [ ] Rewrite `src/analyze/summarizer.py`
  - [x] Update CLI and Healthchecks
- [ ] **6.2 Migrate SDK**
  - [ ] Switch to `google-genai`
  - [ ] Refactor summarizer/digest builder
  - [ ] Reset failed articles
