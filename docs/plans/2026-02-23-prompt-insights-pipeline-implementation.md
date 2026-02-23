---
date: 2026-02-23
topic: prompt-insights-pipeline
stage: implementation-plan
status: draft
source: conversation
---

# Prompt Insights Pipeline Implementation Plan

## Goal

Integrate selective non-obvious insight reporting into the feed analysis pipeline while aligning prompt outputs with persisted/rendered digest fields and preventing output bloat.

## Scope

### In Scope

- Align analysis prompts with actual downstream usage to remove unused prompt-only fields.
- Add optional non-obvious insight structures to category and overall synthesis outputs.
- Add confidence- and source-based gating for insight inclusion.
- Add configurable controls for insight behavior (`off|auto|always`, confidence threshold, max insights).
- Render approved insights compactly in digest text/html/terminal output.
- Add tests for gating, caps, config defaults/overrides, and prompt/schema alignment behavior.

### Out of Scope

- Additional LLM passes solely for insight extraction.
- UI redesign of email templates beyond compact insight insertion.
- Historical data migrations or backfilling existing digest records.

## Assumptions And Constraints

- The current pipeline remains single-pass for category/overall synthesis to control latency and token cost.
- Insight claims must be grounded to URLs present in the provided article/category input.
- Existing fallback behavior (when synthesis fails) should remain resilient and deterministic.
- Ruff and existing typing/style conventions must continue to pass.

## Task Breakdown

### Task 1: Align prompt contracts with runtime usage

**Objective**

Remove prompt/schema drift so each requested output field is either used downstream or intentionally excluded.

**Files**

- Modify: `src/analyze/prompts.py`
- Modify: `src/analyze/summarizer.py`
- Modify: `tests/test_analyze.py`

**Dependencies**

None

**Implementation Steps**

1. Update article summary prompts to emphasize grounded summaries and explicit output bounds.
2. Remove unused summary fields (`topics`, `sentiment`, `importance`) from the summary response schema and related parsing assumptions.
3. Update tests and mock LLM payloads to match the adjusted schema.

**Verification**

- Run: `uv run python -m pytest tests/test_analyze.py -k summarize`
- Expect: summarizer-related tests pass with revised schema payloads.

**Done When**

- Summary prompts and schema fields are aligned with persisted `Article` summary artifacts.
- No code path expects removed fields.

### Task 2: Add structured non-obvious insights with gating

**Objective**

Introduce optional insight structures in category/overall synthesis and filter them using deterministic gate rules.

**Files**

- Modify: `src/analyze/prompts.py`
- Modify: `src/analyze/digest_builder.py`
- Modify: `src/models.py`
- Modify: `tests/test_analyze.py`

**Dependencies**

- Task 1

**Implementation Steps**

1. Extend synthesis prompts with optional insight objects and compact explanation fields.
2. Add corresponding pydantic response models for structured parsing.
3. Implement gating in digest builder: confidence threshold, source URL membership, dedupe against existing takeaways/themes, and per-scope caps.
4. Store only approved insights in digest models.

**Verification**

- Run: `uv run python -m pytest tests/test_analyze.py -k "insight or digest"`
- Expect: tests confirm low-confidence/invalid-source insights are dropped and caps are enforced.

**Done When**

- Category scope yields at most one approved non-obvious insight.
- Overall scope yields at most configured maximum approved insights.
- Unsupported insights are excluded without breaking digest generation.

### Task 3: Add configuration controls and compact rendering

**Objective**

Make insight behavior configurable and visible in output channels without bloating digest body content.

**Files**

- Modify: `src/config.py`
- Modify: `src/deliver/templates/digest.txt`
- Modify: `src/deliver/templates/digest.html`
- Modify: `src/cli.py`
- Modify: `tests/test_config.py`

**Dependencies**

- Task 2

**Implementation Steps**

1. Add settings: `insights_mode`, `insight_min_confidence`, `max_insights_per_digest`.
2. Wire digest builder behavior to settings.
3. Render insights in concise 1-2 line blocks only when present.
4. Add config tests for defaults and env overrides.

**Verification**

- Run: `uv run python -m pytest tests/test_config.py`
- Expect: defaults and env overrides validate for new settings.

**Done When**

- Insights can be disabled or forced via configuration.
- Output channels only show insight blocks when approved insights exist.

### Task 4: End-to-end verification and clean commit

**Objective**

Verify integrated behavior and produce a single coherent commit.

**Files**

- Modify: `tests/test_deliver_renderer.py` (if output expectations change)
- Verify: repository test/lint state for changed modules

**Dependencies**

- Tasks 1-3

**Implementation Steps**

1. Run targeted tests for changed modules.
2. Run project lint checks.
3. Run broader test suite relevant to analysis + delivery paths.
4. Review diff for scope cleanliness and commit once.

**Verification**

- Run: `uv run ruff check .`
- Expect: zero lint violations.
- Run: `uv run python -m pytest tests/test_analyze.py tests/test_config.py tests/test_deliver_renderer.py`
- Expect: all selected tests pass.

**Done When**

- Verification commands pass after final edits.
- Single commit contains only planned prompt/insight/config/render/test changes.

## Risks And Mitigations

- Risk: Prompt changes reduce synthesis quality.
  Mitigation: Keep fallback logic unchanged and preserve concise narrative guidance.
- Risk: Insight gate removes too much signal.
  Mitigation: configurable threshold and `always` mode to force inclusion for tuning.
- Risk: New fields break renderer expectations.
  Mitigation: use optional fields with default factories and conditional rendering.
- Risk: Test brittleness from expanded schemas.
  Mitigation: keep mock responses minimal and schema-focused.

## Verification Matrix

| Requirement | Proof command | Expected signal |
| --- | --- | --- |
| Summary prompt/schema alignment | `uv run python -m pytest tests/test_analyze.py -k summarize` | Summarizer tests pass with revised schema |
| Insight gating + cap behavior | `uv run python -m pytest tests/test_analyze.py -k "insight or digest"` | Deterministic pass on drop/include/cap cases |
| Config controls validate | `uv run python -m pytest tests/test_config.py` | New defaults/overrides pass |
| Render path remains valid | `uv run python -m pytest tests/test_deliver_renderer.py` | Template rendering tests pass |
| Lint baseline preserved | `uv run ruff check .` | Exit 0, no violations |

## Handoff

1. Execute in this session, task by task.
2. Open a separate execution session.
3. Refine this plan before implementation.

Plan complete and saved to docs/plans/2026-02-23-prompt-insights-pipeline-implementation.md.
