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

### Source-relative paths resolve to `src/`, not the project root

- **What:** two `src/feed/cli.py` sites assume `Path(__file__).parent.parent` is the
  repository root. From `src/feed/cli.py` it is `src/`.
  - `init` (the "Offer to copy sample feeds.yaml" step) looks for
    `src/config/feeds.yaml`, which doesn't exist, so it always prints "No sample
    feeds.yaml found to copy" and never offers the sample in `config/feeds.yaml`.
  - `DEFAULT_PROJECT_ROOT` (the `--project-root` default for `feed schedule`) is
    `<repo>/src`. Because `src/feed` is a directory, `resolve_runner` picks `./feed`,
    so the generated cron entry runs `cd <repo>/src && ./feed run --send` and logs to
    `src/logs/scheduler.log`. The job fails unless `--project-root` is passed.
- **Why or evidence:** found in the 2026-11 comment sweep. On 2026-11-21,
  `feed schedule --backend cron` from an editable install printed
  `Project root <repo>/src` and the entry above. `scripts/setup_cron.py` and
  `scripts/setup_launchd.py` use the same expression correctly, since they sit one
  level below the root.
- **Next:** use `Path(__file__).resolve().parents[2]` at both sites and add a test
  that pins each default to the directory holding `pyproject.toml`. A wheel install
  has no `config/feeds.yaml` at all, so decide whether `init` should ship the sample
  as package data.
