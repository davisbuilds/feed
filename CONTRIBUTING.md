# Contributing

Bug reports, focused fixes, documentation improvements, and supported proposals
are welcome. Discuss substantial changes to the provider abstraction, delivery
pipeline, dependencies, or public CLI/configuration before major implementation.
This is a solo-maintained project; contributions do not imply a support or
response-time promise.

Agent-assisted work is welcome. Submitters should understand the change's intent,
important behavior, tradeoffs, and verification, and explain limitations in the
PR. No prompt transcript or manual rewrite is required. A clear
[Backlog](docs/project/BACKLOG.md) entry can go directly to a PR; use an issue
when persistent discussion or coordination helps.

Work on a focused branch from `main`. [Operations](docs/system/OPERATIONS.md)
explains setup and checks. [Git policy](docs/project/GIT_HISTORY_POLICY.md)
owns the merge/rebase policy: squash merging is disabled, and each retained
non-merge commit needs a Conventional Commit subject. Use `!` or a
`BREAKING CHANGE:` footer for incompatible CLI/configuration/output changes
and describe migration. Include relevant test evidence in the PR.

Release Please drafts `CHANGELOG.md`; review consumer meaning, compatibility,
and migration steps in the release PR and its body rather than editing a
parallel log for ordinary PRs. GitHub releases do not publish to PyPI.
