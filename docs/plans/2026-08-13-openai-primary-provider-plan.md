---
date: 2026-08-13
author: gpt-5
topic: openai-primary-provider
stage: plan
status: complete
source: conversation
risk_profile: routine
readiness: ready
---

# OpenAI Primary Provider Plan

## Goal

Make OpenAI the installed and configured default provider for `feed`, using
`gpt-5.6-luna` with `xhigh` reasoning effort, while retaining Gemini and
Anthropic as optional providers with their existing provider-specific behavior.

## Scope

### In Scope

- Make the OpenAI SDK a base dependency and make Gemini optional.
- Default new and unqualified configurations to OpenAI, `gpt-5.6-luna`, and
  `xhigh` reasoning effort.
- Move the OpenAI provider from Chat Completions to Responses structured output.
- Preserve the provider-agnostic analysis, cache, retry, and output contracts.
- Update model pricing, setup tooling, user documentation, tests, and roadmap.

### Out of Scope

- Removing Gemini or Anthropic support.
- Prompt redesign, feed-data migration, cache clearing, or scheduler changes.
- Persisting, rotating, or creating an API key; live verification reuses the
  user-provided process environment only.

## Assumptions And Constraints

- The OpenAI API key is available in the current process environment and may be
  used only for a narrow, non-persisted live smoke test after deterministic
  verification passes.
- Gemini and Anthropic remain selectable through `LLM_PROVIDER` and retain their
  optional dependency extras.
- `OPENAI_API_KEY` is the preferred OpenAI credential; `LLM_API_KEY` remains the
  Gemini/Anthropic interface and a legacy OpenAI fallback. The Gemini-specific
  legacy aliases remain necessary only for `LLM_PROVIDER=gemini`.
- The model target is explicitly `gpt-5.6-luna`, not an alias or a newer model.

## Map Before You Cut

- `run_analysis()` obtains the resolved provider, key, and model from `Settings`,
  creates one retry-wrapped client, then passes it to summary and synthesis
  stages. `Summarizer` cache keys contain the model name, so the new default
  naturally creates isolated cache entries.
- The thinnest seam is the existing provider factory and `OpenAIClient`: add an
  OpenAI-only reasoning-effort argument through that seam without changing the
  common `LLMClient.generate()` output contract.
- Sibling routes: the setup wizard writes the initial configuration; setup
  verification imports a provider SDK; `list_models.py` currently has a
  Gemini-only implementation; docs and pricing enumerate provider defaults.
- OpenAI SDK 2.52.0 exposes `responses.parse()` with `reasoning`, `instructions`,
  `input`, `text_format`, and `timeout` support (verified 2026-08-13 with
  `uv run --extra openai python`).

## Task Breakdown

### Task 1: Establish primary-provider configuration and installation

**Objective**

Make a normal install capable of running the default OpenAI path and expose a
typed, validated OpenAI reasoning-effort setting.

**Files**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/feed/config.py`
- Modify: `src/feed/llm/__init__.py`
- Modify: `src/feed/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_llm.py`

**Dependencies**

None

**Assumptions Verified**

- `pyproject.toml` currently places `google-genai` in base dependencies and
  `openai` behind an extra; CI installs only `--extra dev`.
- `Settings.apply_llm_defaults()` at `src/feed/config.py` resolves defaults from
  `PROVIDER_DEFAULTS`; the factory in `src/feed/llm/__init__.py` owns client
  construction.
- `cli.init()` in `src/feed/cli.py` prompts for a provider and writes generic
  `LLM_*` variables.

**Implementation Steps**

1. Move OpenAI to base dependencies and Gemini to its optional extra, then
   refresh the lockfile.
2. Change the default provider/model to OpenAI/`gpt-5.6-luna`; add validated
   `LLM_REASONING_EFFORT` with an `xhigh` default and provider-aware API-key
   resolution.
3. Carry reasoning effort through the provider factory only for OpenAI and make
   the wizard default to OpenAI.
4. Replace tests that presume an uninstalled OpenAI SDK with deterministic
   import-failure simulation.

**Verification**

- Run: `uv sync --extra dev --frozen`
- Expect: the OpenAI package imports without selecting an optional extra.
- Run: `uv run python -m pytest tests/test_config.py tests/test_llm.py`
- Expect: default configuration resolves to OpenAI, Luna, and `xhigh`; both
  optional providers remain selectable.

**Test Discovery Verified**

- `pyproject.toml` configures pytest with `pythonpath = ["src"]`; CI invokes
  `uv run python -m pytest -q`, which discovers both named test files.
- Literal proof: `uv run python -m pytest tests/test_config.py tests/test_llm.py`.

**Done When**

- A fresh CI-equivalent install contains OpenAI, and omitted LLM configuration
  resolves to exactly `openai/gpt-5.6-luna/xhigh`.
- Explicit Gemini and Anthropic provider selections still resolve their existing
  defaults without receiving an OpenAI-only request setting.

### Task 2: Implement the GPT-5.6 Responses client

**Objective**

Use OpenAI Responses structured parsing with the requested reasoning effort
while preserving parsed JSON, raw text, and input/output token accounting.

**Files**

- Modify: `src/feed/llm/openai.py`
- Modify: `src/feed/llm/base.py`
- Modify: `src/feed/analyze/__init__.py`
- Test: `tests/test_llm_provider_normalization.py`

**Dependencies**

Task 1

**Assumptions Verified**

- `OpenAIClient.generate()` at `src/feed/llm/openai.py` currently makes a Chat
  Completions request and returns the shared `LLMResponse` shape.
- `run_analysis()` at `src/feed/analyze/__init__.py` creates the factory client;
  summary and digest stages consume only `LLMResponse` fields.

**Implementation Steps**

1. Construct the OpenAI SDK with the configured timeout and call
   `responses.parse()` with `instructions`, `input`, `text_format`, model, and
   `reasoning.effort`.
2. Normalize parsed Pydantic output, output text, total input/output usage, and
   optional reasoning-token detail into the shared response type.
3. Treat a missing parsed result, refusal, or malformed response as a shared
   `LLMError` so existing retries and per-article error handling remain effective.
4. Add response fixtures that prove the request carries `gpt-5.6-luna` and
   `xhigh`, and that usage and negative paths normalize correctly.

**Verification**

- Run: `uv run python -m pytest tests/test_llm_provider_normalization.py`
- Expect: all structured-output, usage, and malformed-response cases pass with
  no network access.
- Run: `uv run python -m pytest tests/test_analyze.py tests/test_cache.py`
- Expect: existing analysis/cache contracts remain green.

**Test Discovery Verified**

- The same pytest configuration and CI command discover
  `tests/test_llm_provider_normalization.py`.
- Literal proof: `uv run python -m pytest tests/test_llm_provider_normalization.py`.

**Done When**

- Every OpenAI request uses Responses structured output and includes the exact
  configured reasoning effort.
- A successful parsed response yields all four previously observable values:
  parsed content, raw text, input tokens, and output tokens.

### Task 3: Align tooling, pricing, and documentation

**Objective**

Make every user-facing setup and accounting surface describe the actual default
and optional-provider topology.

**Files**

- Modify: `.env.example`
- Modify: `scripts/list_models.py`
- Modify: `scripts/verify_setup.py`
- Modify: `src/feed/pricing/data/openai.json`
- Modify: `tests/test_pricing.py`
- Modify: `README.md`
- Modify: `docs/system/ARCHITECTURE.md`
- Modify: `docs/system/FEATURES.md`
- Modify: `docs/system/OPERATIONS.md`
- Modify: `docs/system/TEST_STRATEGY.md`
- Modify: `docs/project/ROADMAP.md`

**Dependencies**

Tasks 1-2

**Assumptions Verified**

- `.env.example`, README, operations documentation, and the wizard describe
  Gemini as the default.
- `scripts/list_models.py` rejects all providers except Gemini.
- `src/feed/pricing/data/openai.json` contains no `gpt-5.6-luna` entry; pricing
  currently returns `None` for that model.

**Implementation Steps**

1. Document OpenAI/Luna/xhigh as the default and Gemini/Anthropic as optional;
   document `OPENAI_API_KEY` as the preferred primary credential and
   `LLM_API_KEY` as the optional-provider and legacy fallback.
2. Adapt model listing to OpenAI's model-list API while retaining the Gemini
   path and a clear Anthropic unsupported message.
3. Add Luna's current official token pricing to the registry and exercise its
   cost estimate with a deterministic test.
4. Update the system docs and roadmap to reflect the completed provider shift.

**Verification**

- Run: `uv run python -m pytest tests/test_pricing.py tests/test_dead_code.py`
- Expect: pricing recognizes Luna and static checks find no removed or orphaned
  provider surface.
- Run: `uv run python scripts/verify_setup.py`
- Expect: setup verifier imports the active provider SDK or reports only missing
  user configuration, never a stale Gemini-only dependency instruction.

**Test Discovery Verified**

- `tests/test_pricing.py` is discovered by the repository pytest configuration.
- Literal proof: `uv run python -m pytest tests/test_pricing.py`.

**Done When**

- All documented defaults match the executable defaults and the price estimator
  returns a numeric Luna estimate for 1,000,000 input plus 1,000,000 output
  tokens.

### Task 4: Verify the migration and record the result

**Objective**

Prove the source and the actual OpenAI access path work, without persisting or
exposing credentials.

**Files**

- Modify: `docs/plans/2026-08-13-openai-primary-provider-plan.md`

**Dependencies**

Tasks 1-3

**Assumptions Verified**

- The user explicitly authorized reuse of an available `OPENAI_API_KEY`; the
  credential was detected in process environment only on 2026-08-13.

**Behavior Measured**

- Run: `LLM_PROVIDER=openai uv run python - <<'PY' ... PY`
- Observed 2026-08-13: the project factory and Responses client completed one
  `gpt-5.6-luna` / `xhigh` Pydantic structured-output request using the existing
  process-environment key, with positive input and output usage and no persisted
  credential.

**Implementation Steps**

1. Run the full CI-equivalent lint, formatting, dead-code, and pytest gates.
2. Make one real, minimal Responses structured-output request using the process
   environment key and confirm the model, parsed output, and nonzero usage are
   reported without printing credential material.
3. Update this plan's status and handoff with the exact verification evidence.

**Verification**

- Run: `uv run ruff check . && uv run ruff format --check . && uv run python -m pytest`
- Expect: all local CI gates pass.
- Run: a one-request OpenAI smoke probe with `gpt-5.6-luna`, `xhigh`, and a
  minimal Pydantic schema.
- Expect: parsed response with at least one nonempty schema field and positive
  input/output usage; no key output.

**Done When**

- Automated checks are green and the live response proves the configured account
  can run the exact selected model and effort.

## Risks And Mitigations

- Risk: `xhigh` increases response latency or cost for short summarization work.
  Signal: live smoke or representative run reports unexpectedly large usage or
  slow requests. Mitigation: preserve configurable `LLM_REASONING_EFFORT`, ship
  the requested `xhigh` default, and measure before changing it.
- Risk: provider-specific response objects expose incomplete/refusal outputs.
  Signal: parsed structured content is absent despite a successful HTTP response.
  Mitigation: explicit normalization tests and shared retryable errors.
- Risk: a user retains an old Gemini configuration after installing the change.
  Signal: `feed config --json` shows `gemini` explicitly. Mitigation: preserve
  Gemini as an optional valid configuration and make generated/new config OpenAI.

## Verification Matrix

| Requirement | Proof command | Expected signal |
| --- | --- | --- |
| Default install contains OpenAI | `uv sync --extra dev --frozen && uv run python -c 'import openai'` | exits 0 |
| Default resolves target | `uv run python -m pytest tests/test_config.py` | OpenAI/Luna/xhigh defaults pass |
| OpenAI preserves structured contract | `uv run python -m pytest tests/test_llm_provider_normalization.py` | Responses request and usage fixtures pass |
| Gemini/Anthropic remain optional | `uv run python -m pytest tests/test_llm.py` | explicit provider factory cases pass |
| Luna cost is tracked | `uv run python -m pytest tests/test_pricing.py` | numeric known-model estimate passes |
| Source quality | `uv run ruff check . && uv run ruff format --check . && uv run python -m pytest` | all gates pass |
| Account/model capability | minimal live Responses smoke probe | parsed response and positive usage |

## Handoff

Completed in this session. Source and documentation verification passed, and a
single live Responses smoke test proved the selected account can run the exact
model, reasoning effort, structured output, and usage path without persisting a
credential.

Plan complete and saved to docs/plans/2026-08-13-openai-primary-provider-plan.md.
