# Backlog

Future-only gaps and opportunities worth revisiting. Capture recurring friction,
meaningful risk or cost, unresolved decisions, or concrete revisit triggers.
Fix simple, quick, or blocking issues inline when within the active task's scope.

## Conventions

- **Entry:** state **What** and **Why or evidence**. Add **Next** (a useful first
  action) or **Revisit when** (a concrete gate) where helpful; no fixed template
  is required.
- **Evidence:** date and source volatile claims. Support causal or performance
  claims with measurements, or label them **hypothesis, unmeasured**.
- **Delegation:** agents can execute entries directly. Recording a candidate does
  not expand the active task or select a roadmap priority. Use an issue when
  persistent discussion or coordination helps; no mandatory graduation step.
- **Ownership:** keep cross-repository work with the capability-owning repository.
  If an issue owns the details, retain only a useful linked summary here; avoid
  parallel checklists. Keep private evidence out of public entries and issues.
- **Closure:** reconcile affected entries as work lands. Remove resolved concerns,
  retain unresolved remainders, and preserve durable rationale in its owning
  reference. Roadmap records selected direction; Git and PRs hold routine shipped
  history. Revisit the broader list during prioritization or when stale entries
  impede work.

## Open

### Remove the certifi release-quarantine exception (revisit 2026-10-28)

- **What:** `pyproject.toml` sets `exclude-newer-package = { certifi = "2026-10-21T00:00:00Z" }` so certifi
  2026.10.19 (GHSA-6q48-6c7w-9gw2, emSign CA distrust) could be adopted inside the 7-day quarantine.
- **Why:** the absolute cutoff never advances. Once 2026.10.19 is older than the window it only blocks
  later certifi releases, including future security fixes, for manual and Dependabot upgrades.
- **Next:** on or after 2026-10-28, delete the `exclude-newer-package` line and its comment, run
  `uv lock`, and confirm only the lock's `[options.exclude-newer-package]` entry changes.
