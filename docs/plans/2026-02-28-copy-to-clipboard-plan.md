---
date: 2026-02-28
topic: copy-to-clipboard
stage: brainstorm
---

# Copy Digest to Clipboard

## What We Are Building
A `--copy` flag on `feed run` and `feed analyze` that copies the digest as **markdown** to the system clipboard. This works independently of other flags — including `--send` — so the user always gets clipboard content when requested.

## Why This Direction
- Clipboard copy is the primary need: run the digest, paste it into Slack/docs/notes.
- Markdown is the most versatile format for paste targets (GitHub, Obsidian, editors, Slack).
- A `--copy` flag is simpler than a standalone `feed copy` command, which would require persisting rendered output and managing staleness. Can be added later if needed.

## Key Decisions
- **Format**: Markdown (not plain text, HTML, or format-dependent).
- **Trigger**: `--copy` flag on `run` and `analyze` commands (opt-in per invocation).
- **Interaction with `--send`**: Independent — `--copy --send` both emails and copies to clipboard.
- **Terminal output**: Still prints to terminal as normal; clipboard copy is additive.
- **No standalone command**: No `feed copy` command for now (YAGNI).

## Constraints
- macOS clipboard via `pbcopy`. Cross-platform support (e.g., `xclip`, `xsel`) is not required unless desired later.
- Digest must already be rendered as markdown before copying — reuse or adapt existing rendering.

## Success Criteria
- `feed run --copy` prints digest to terminal AND copies markdown to clipboard.
- `feed analyze --copy` does the same for analyze-only flow.
- `feed run --copy --send` sends email AND copies markdown to clipboard.
- Clipboard content is clean markdown (no ANSI codes, no Rich markup).

## Open Questions
- Should there be a visible confirmation message (e.g., "Copied to clipboard") after copy succeeds?
- File output (`--output <path>`) as a future extension — not in scope for this iteration.

## Next Step
Proceed to planning.
