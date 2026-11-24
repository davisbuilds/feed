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

### Update virtualenv in the development extra

As of November 24, 2026, the lockfile pins `virtualenv` to 21.14.11 through
`pre-commit` in the optional `dev` extra. The advisory covers versions
`>=21.14.9,<21.14.13` and applies to Bash environment activation. Feed's base
CLI launches Python directly.
[CVE-2026-115586](https://github.com/advisories/GHSA-cx6f-vjhg-g3cc)

Qualify a patched release starting at 21.14.13, then update the lock and run
the locked development checks.

### Offer a sample feed list in wheel installs

- **What:** the wheel does not include `config/feeds.yaml`, so `feed init` offers
  the sample when run from a source checkout but has no bundled sample in a
  wheel installation.
- **Next:** decide whether to ship a sample as package data, and test the prompt
  and copy behavior from an installed wheel if it is included.
