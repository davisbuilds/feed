# Session Summary: Substack Digest Agent Planning

**Date:** 2026-01-09  
**Session Focus:** Architecture and implementation planning for a personal newsletter intelligence agent

---

## 1. Primary Request and Intent

User wants to build a **Substack digest agent** that:
- Reads their Substack inbox (~50 newsletters)
- Uses Claude Code SDK for comprehension and analysis
- Summarizes content with **categorical breakdowns, key takeaways, and actionable insights**
- Delivers a daily email digest via **Resend**

**Constraints/Preferences:**
- Running locally on **Mac Mini M4**
- Primarily reads newsletters in Substack's web app/reader (not email inbox)
- Prioritize **simplicity, maintainability, and beautiful design**
- Follow best programming practices

**Desired End State:** One thoughtfully curated email each morning instead of 50+ unread newsletters.

---

## 2. Key Technical Concepts

**Core Stack Decided:**
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.12+ | Rich ecosystem for data processing |
| RSS Parsing | `feedparser` | Battle-tested, handles malformed feeds |
| AI | Claude Sonnet 4 | Best quality/speed/cost for summarization |
| SDK | `anthropic` | Official Python SDK |
| Email | Resend | Developer-friendly, great deliverability |
| Templates | `jinja2` | Powerful for HTML email |
| Storage | SQLite | Zero-config, portable |
| Config | YAML | Human-readable |
| CLI | `typer` + `rich` | Modern, type-safe CLI |

**Key Finding from Research:** Substack has **no public API**, but every publication exposes RSS feeds at `https://{subdomain}.substack.com/feed`. This is the recommended approach—no browser automation needed for free content.

**Existing Open Source References:**
- `finaldie/auto-news` (800 stars) - Multi-source aggregator with LLM summarization
- `piqoni/matcha` (660 stars) - Daily digest generator for terminals
- `KarenSpinner/substack-digest` - Substack-specific RSS digest generator
- `NHagar/substack_api` - Unofficial Python wrapper (needs auth for paywalled content)

---

## 3. Files and Code Sections

### Created Implementation Plan Documents

**Location:** `/mnt/user-data/outputs/substack-agent-plans/`

| File | Purpose | Size |
|------|---------|------|
| `00-PROJECT-OVERVIEW.md` | Architecture, design principles, project structure | 6.5K |
| `01-PHASE-SETUP.md` | Project scaffold, dependencies, config system, data models | 16K |
| `02-PHASE-INGEST.md` | RSS fetching, HTML parsing, SQLite storage, deduplication | 36K |
| `03-PHASE-ANALYZE.md` | Claude integration, prompts, summarization, digest building | 34K |
| `04-PHASE-DELIVER.md` | HTML/text email templates, Resend integration | 34K |
| `05-PHASE-ORCHESTRATE.md` | Typer CLI, cron/launchd scheduling, healthchecks | 24K |
| `06-PHASE-POLISH.md` | Error handling, retries, notifications, maintenance | 30K |
| `07-QUICK-REFERENCE.md` | Command cheatsheet, configs, troubleshooting | 6K |

### Key Code Components Planned

**Project Structure:**
```
substack-agent/
├── src/
│   ├── config.py           # Settings & feed config (Pydantic)
│   ├── models.py           # Article, Digest, Category models
│   ├── pipeline.py         # Main orchestration with error handling
│   ├── ingest/             # feedparser + BeautifulSoup
│   ├── analyze/            # Claude summarization + prompts
│   ├── deliver/            # Jinja2 templates + Resend
│   ├── storage/            # SQLite operations
│   └── utils/              # Retry, notifications, validators
├── config/feeds.yaml       # Newsletter subscriptions
├── scripts/run_digest.py   # CLI entry point
└── pyproject.toml
```

**CLI Commands Designed:**
```bash
digest run                  # Full pipeline
digest run --skip-send      # Dry run
digest ingest / analyze / send  # Individual phases
digest status / stats / config / validate  # Info commands
digest cleanup / backup     # Maintenance
```

---

## 4. Errors and Fixes

**None** - This was a planning session, no code execution yet.

---

## 5. Problem Solving Approach

**Why RSS over Browser Automation:**
- Substack exposes full article content in RSS for free posts
- No Cloudflare/CAPTCHA challenges
- Much simpler, more reliable architecture
- For paywalled content, could add `substack.sid` cookie auth later

**Why SQLite over PostgreSQL:**
- Single-user local deployment on Mac Mini
- Zero configuration required
- Easily portable/backupable
- Can migrate to Postgres if multi-user needed later

**Why Jinja2 over React Email:**
- Simpler for HTML email (no build step)
- Python-native integration
- Email templates don't need React's component model

**Cost Estimation:**
- ~50 newsletters × ~5 articles = 250 summaries/day
- ~125K tokens for summaries + 10K for synthesis
- ~$0.50/day with Claude Sonnet (~$15/month)

---

## 6. User Messages

1. > "i want to build a substack agent that leverages claude code sdk to read my substack inbox, comprehend, analyze, and summarize the content to me in a daily email using resend. Is there a substack API we can use or does the agent need to run a browser to view the content? Are there any other open source projects out there that do similar things? Devise an implementation plan for going about this project and feel free to ask any design questions up front"

2. (Response to design questions about deployment, inbox source, summary depth):
   > "running locally on my mac mini (m4) should be fine for now. i'm subscribed to about 50 newsletters currently and mostly read in the web app/reader. for the daily digest i want a categorical breakdown with the key takeaways and actionable insights across all articles analyzed that day"

3. > "Now craft a series of phased implementation plans in a series of markdown documents, each with its own todos. Prioritize simplicity, maintainability, and beautiful design, adhering to best programming practices. Think hard and do your best work to get this project off to a great start!"

4. > "continue" (after Phase 5 was created)

5. > "/compact-session"

---

## 7. Pending Tasks

**Implementation not started.** All 6 phases are documented and ready for execution:

| Phase | Status | Est. Time |
|-------|--------|-----------|
| 0 - Setup | Not started | 2-3 hrs |
| 1 - Ingest | Not started | 3-4 hrs |
| 2 - Analyze | Not started | 4-5 hrs |
| 3 - Deliver | Not started | 3-4 hrs |
| 4 - Orchestrate | Not started | 2-3 hrs |
| 5 - Polish | Not started | 3-4 hrs |

**Total estimated time:** 15-20 hours

---

## 8. Current Work State

- **Completed:** Research phase and full implementation planning
- **Deliverables:** 8 markdown documents with copy-pasteable code
- **Files location:** `/mnt/user-data/outputs/substack-agent-plans/`
- **No code executed yet** - all documents are plans/templates

---

## 9. Suggested Next Step

**Begin Phase 0 implementation:**

```bash
# Create project directory
mkdir substack-agent && cd substack-agent

# Initialize with uv
uv init --name substack-agent --python 3.12

# Create directory structure
mkdir -p src/{ingest,analyze,deliver,storage}
mkdir -p config tests scripts
```

Then follow `01-PHASE-SETUP.md` to:
1. Configure `pyproject.toml` with dependencies
2. Create `.env` with API keys (ANTHROPIC_API_KEY, RESEND_API_KEY)
3. Implement `src/config.py` and `src/models.py`
4. Create `config/feeds.yaml` with 3-5 test newsletter feeds
5. Run `scripts/verify_setup.py` to validate

---

## Additional Context

**Research artifact created:** Extended search was performed covering:
- Substack API availability (none official, but RSS works)
- Unofficial libraries (`substack_api` Python, `substack-api` npm)
- Browser automation alternatives (Playwright, Selenium)
- Existing open source solutions (auto-news, matcha, substack-digest)
- Claude Agent SDK patterns
- Resend email setup and pricing

**User preferences inferred:**
- Values clean architecture and separation of concerns
- Prefers comprehensive documentation
- Wants production-ready code, not prototypes
- Appreciates beautiful design (email templates matter)
