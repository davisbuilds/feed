# Roadmap

feed is a CLI for turning subscribed feeds into digests delivered to the terminal
or email. The current product path remains ingest → analyze → deliver, with local
configuration, caching, and optional scheduling. [Features](../system/FEATURES.md)
and [Operations](../system/OPERATIONS.md) own the current command and provider
contracts.

## Current Direction

Keep the pipeline usable from any working directory and preserve the provider
abstraction: OpenAI is the configured default, with Gemini and Anthropic optional.
Changes to provider behavior or delivery should preserve the shared analysis/output
contract and be verified at the relevant stage. The completed OpenAI-primary plan
is retained for its decision context, not an active work queue.

No next feature is selected in this Roadmap. [Backlog](BACKLOG.md) holds durable
unresolved gaps when discovered. Released consumer changes and compatibility live
in [CHANGELOG.md](../../CHANGELOG.md); Git and PRs retain routine delivery history.
