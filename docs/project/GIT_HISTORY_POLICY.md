# Git History and Branch Hygiene

Last updated: September 26, 2026

## Repository Merge Settings

Configured on GitHub repository `davisbuilds/feed`:

- `allow_squash_merge`: `false`
- `allow_merge_commit`: `true`
- `allow_rebase_merge`: `true`
- `delete_branch_on_merge`: `true`
- `merge_commit_title`: `PR_TITLE`
- `merge_commit_message`: `PR_BODY`

Result:

- PR branches retain their full commit history when merged.
- `main` receives either a merge commit (preserving the PR boundary) or rebased commits (linear history), depending on which strategy the merger picks for that PR.
- Squash merging is disabled — full per-commit history is preserved.
- Merged remote branches are auto-deleted.

## Merge Strategy

Merge commits and rebase merges are both allowed; squash merges are disabled.

- **Default — merge commit.** Preserves the PR as a discoverable boundary in `main`'s history. Best when the PR contains multiple meaningful commits worth keeping addressable individually.
- **Rebase merge.** Use when the PR's commits are clean and the linear history reads better without an extra merge node. Avoid if the PR's commits are noisy (WIP, fixups) — clean them up locally first.
- **Authoring expectation.** Because squash is gone, individual PR commits land in `main`. Keep PR commit messages tidy: meaningful subjects, no WIP markers, no fixup chains. Squash or reword locally before opening the PR if needed.

## Commit Classification And Versioning

Use `type(scope): description` (scope optional) for each non-merge commit. CI
checks subjects on PRs because preserved commits, rather than just the PR title,
feed Release Please. Choose the type from the actual user-visible impact:

| Change | Subject | Before 1.0 | At/after 1.0 |
| --- | --- | --- | --- |
| Compatible feature | `feat:` | Minor | Minor |
| Runtime bug or performance fix; user-visible revert | `fix:` / `perf:` / `revert:` | Patch | Patch |
| Incompatible behavior | Any type with `!` or `BREAKING CHANGE:` footer | Minor | Major |
| Non-runtime maintenance | `docs:`, `test:`, `ci:`, `chore:`, `build:`, `style:`, `refactor:` | No release alone | No release alone |

An incompatible CLI flag, output shape, or configuration change must be marked
breaking regardless of the amount of code changed. A `refactor:` changes no
observable behavior; use `fix:` or `feat:` when behavior changes. Dependency
maintenance uses `chore(deps):` or `build(deps):`; use `fix(deps):` for a dependency
update that fixes a runtime or security bug and should trigger a patch. The
subject guard verifies syntax, while review verifies the actual classification.

Release PRs follow the existing merge/rebase policy and normal review/CI gates.
Release Please manages versions and released user-facing changes in
`CHANGELOG.md`; `ROADMAP.md` owns direction and orientation highlights, and
`BACKLOG.md` owns unresolved actionable gaps. See
`docs/system/OPERATIONS.md` for the bootstrap boundary and App activation.

## CI Gates

Workflow: `.github/workflows/ci.yml`

Quality gates before merge:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run python -m pytest`
- PR commit-subject classification and locked dependency installation.

## Current Limitation

`main` branch protection is not enabled because GitHub returned `403` for branch protection APIs on this private repository tier. Until upgraded, enforce checks and review discipline by team convention.

## Recommended Ongoing Hygiene

1. Create short-lived feature branches from `main`.
2. Open PRs early; keep them focused.
3. Tidy your PR commit history *before* merging — reword/squash locally so what lands on `main` reads cleanly.
4. Pick **Create a merge commit** by default; pick **Rebase and merge** when linear history is materially better.
5. Periodically prune local branches:

```bash
git fetch --prune
git branch --merged main | grep -v ' main$' | xargs -n 1 git branch -d
```
