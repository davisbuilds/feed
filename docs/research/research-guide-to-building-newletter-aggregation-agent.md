# Building a Substack newsletter aggregation agent

**Substack has no public API**, but a robust ecosystem of RSS feeds, unofficial libraries, and proven architectural patterns makes building a newsletter aggregation and summarization agent highly feasible. The recommended approach combines RSS feeds for content ingestion, the Claude Agent SDK for intelligent summarization, and Resend for reliable email delivery—a stack that several open-source projects have already validated in production.

## Substack offers RSS but no official API

Substack explicitly does not provide a public API for developers. Their support documentation confirms there are "no public plans" to offer one. However, every Substack publication exposes an RSS feed at a predictable URL pattern: `https://{subdomain}.substack.com/feed`. For custom domains, the pattern is `https://newsletter.example.com/feed`.

**RSS feed characteristics** vary by content type. Free posts include full article content in the feed, while paywalled content only shows excerpts unless you authenticate with a valid `substack.sid` session cookie. The feeds follow RSS 2.0 format and include publication metadata, post titles, authors, and timestamps.

Two **unofficial API libraries** have emerged as community standards:

| Library | Language | Stars | Key Features |
|---------|----------|-------|--------------|
| **NHagar/substack_api** | Python | 145 | Newsletter/Post/User classes, paywalled content with auth |
| **substack-api** (npm) | TypeScript | Active | Entity-based API, async iterators, built-in caching |

Both require session cookies (`substack.sid` from browser DevTools) to access subscriber-only content. The Python library is particularly mature, offering `pip install substack-api` installation and object-oriented access to posts, podcasts, and recommendations.

## Four practical methods for programmatic access

Beyond RSS feeds, developers have successfully used several approaches depending on their requirements:

**Email parsing via IMAP** is the most ToS-compliant method for content you subscribe to. Substack newsletters arrive as standard HTML emails with RFC-2919 `List-Id` headers for easy filtering. This approach guarantees access to full content you've legitimately subscribed to, though it requires managing an inbox and parsing HTML.

**Browser automation** using Playwright, Puppeteer, or Selenium enables JavaScript rendering and authenticated sessions. The `timf34/Substack2Markdown` project (343 stars) demonstrates this approach, using Selenium with credential-based login to download premium content. Key considerations include Cloudflare protection on some pages and potential CAPTCHA challenges during automated login.

**Internal API endpoints** discovered through reverse engineering include `/api/v1/archive` for post listings and `/api/v1/posts/{slug}` for individual posts. These work but carry higher ToS risk and may break without notice.

**RSS feed aggregation** remains the cleanest solution for free content. The `feedparser` Python library handles Substack feeds reliably, and services like rss2json.com provide JSON conversion for JavaScript applications.

## Existing tools provide proven foundations

Several open-source projects directly address newsletter aggregation with LLM summarization:

**finaldie/auto-news** (800 stars) is the most comprehensive solution—a personal news aggregator supporting RSS, Reddit, YouTube, and Twitter sources with ChatGPT/Gemini/Ollama summarization. It outputs to Notion and deploys via Kubernetes/Helm, making it production-ready for self-hosting.

**piqoni/matcha** (660 stars) takes a minimalist approach, generating daily digests in Markdown format optimized for terminal reading or Obsidian integration. Its "LLM Analyst" feature provides deeper analysis beyond basic summaries.

**KarenSpinner/newsletter-digest-standalone** specifically targets Substack newsletters, using public RSS feeds to generate scored reading lists based on engagement metrics (comments, word count). It requires no authentication and outputs HTML ready for Substack's editor—ideal for building a curated digest.

For **Claude integration specifically**, the `mcp-substack` Model Context Protocol server enables Claude Desktop to fetch and parse Substack posts directly within conversations. The MCP architecture provides a standardized way to connect Claude with external data sources.

## Claude Agent SDK enables sophisticated summarization workflows

The Claude Agent SDK (formerly Claude Code SDK) provides the infrastructure for building intelligent content processing agents. Its **built-in web_fetch tool** retrieves full text content from URLs, extracts text from PDFs automatically, and supports domain restrictions for security.

For newsletter summarization, Anthropic recommends a **meta-summarization pattern** when dealing with multiple sources or long content:

1. Fetch each newsletter's content via web_fetch
2. Summarize each source individually (parallelizable with subagents)
3. Aggregate summaries identifying common themes
4. Generate final consolidated digest

**Context window management** is critical when processing multiple newsletters. Claude supports **200K tokens** standard (500K enterprise, 1M beta), but efficient architectures use subagents with isolated context windows, returning only relevant excerpts to the orchestrator. The SDK's automatic compaction feature summarizes previous messages when approaching limits.

For **prompt engineering**, Anthropic's testing shows placing long-form content above queries improves accuracy by up to 30%. Structure prompts with XML tags (`<document>`, `<instructions>`) and instruct Claude to extract relevant quotes before summarizing for better focus on key points.

A typical prompt chaining workflow separates concerns: Chain 1 extracts main articles as structured JSON, Chain 2 identifies themes across sources, Chain 3 assembles the final digest, and an optional Chain 4 performs self-review for quality.

## Resend provides developer-friendly email delivery

Resend offers a clean REST API specifically designed for transactional email, with strong deliverability and native React Email support—particularly relevant for building styled digest emails.

**Setup requires three steps**: create an account (free tier available), generate an API key, and verify your sending domain via DNS records (SPF, DKIM, DMARC). Domain verification typically completes within 24 hours.

**Pricing for daily digests** scales predictably:

| Tier | Price | Monthly Emails | Daily Limit |
|------|-------|----------------|-------------|
| Free | $0 | 3,000 | 100/day |
| Pro | $20 | 50,000 | Unlimited |
| Scale | $90 | 100,000 | Unlimited |

The **batch API** sends up to 100 emails per request, essential for staying within the **2 requests/second rate limit**. For a 500-subscriber digest, batch into 5 requests with small delays. Resend doesn't auto-charge for overages—you'll be prompted to upgrade.

```python
import resend

resend.api_key = "re_yourkey"
resend.Emails.send({
    "from": "Daily Digest <digest@yourdomain.com>",
    "to": ["user@example.com"],
    "subject": "Your Daily Digest - January 9, 2026",
    "html": digest_html,
    "tags": [{"name": "type", "value": "daily_digest"}]
})
```

**React Email integration** lets you build digest templates as React components with Tailwind CSS support, type safety, and cross-client compatibility. This separates content generation from presentation elegantly.

## Recommended architecture and implementation patterns

Production implementations consistently follow a **RSS → Filter → LLM → Email pipeline** with these key components:

**Content ingestion layer** uses `feedparser` (Python) or `rss-parser` (Node.js) to poll RSS feeds on a schedule. Filter articles by publication date (last 24-48 hours) and apply quality scoring based on word count and engagement metrics before LLM processing—this significantly reduces API costs.

**Deduplication is essential** since the same story often appears across multiple feeds. Simple URL-based tracking works for most cases; semantic deduplication using embeddings catches rephrased content. The `xxhash` library provides fast content fingerprinting.

**LLM summarization** should use a two-tier approach: cheaper models (GPT-3.5, Claude Haiku) for initial filtering and ranking, premium models (GPT-4, Claude Sonnet) only for final summaries. Cache summaries to avoid reprocessing unchanged content.

**Scheduling options** range from simple cron jobs to sophisticated orchestration:

- **Cron/systemd**: Traditional, reliable, requires always-on server
- **GitHub Actions**: Free, works well for weekly digests, limited to 5-minute minimum intervals
- **Vercel Cron**: Serverless, integrates with Next.js applications
- **n8n/Make.com**: Visual workflow builders with built-in scheduling

**Data storage patterns** depend on scale. File-based JSON works for personal projects; SQLite suits single-user applications; Notion provides both storage and reading interface (popular in the auto-news project); PostgreSQL plus a vector database like FAISS enables semantic search and advanced deduplication.

## Putting it together into a working system

A practical **minimum viable implementation** combines:

1. **feedparser** to fetch RSS feeds from subscribed Substacks
2. **Claude API** (via Claude Agent SDK or direct API) for summarization
3. **SQLite** for tracking processed articles and preventing duplicates
4. **Resend** for email delivery with React Email templates
5. **GitHub Actions** for daily scheduled execution

The workflow runs daily: fetch new articles from configured feeds, filter by date and deduplicate against the database, summarize with Claude using a structured prompt, generate HTML digest using a React Email template, and send via Resend's batch API.

For **more sophisticated needs**, fork `finaldie/auto-news` as a starting point—it handles multi-source ingestion, LLM integration, and Notion output, with Docker deployment ready for production. Alternatively, the `newsletter-digest-standalone` project provides Substack-specific scoring algorithms that could be combined with custom LLM summarization.

The ecosystem is mature enough that building a functional Substack aggregation agent requires primarily integration work rather than novel development—the core patterns are proven and the tooling is available.