# Git History and Branch Hygiene

Last updated: September 27, 2026

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
checks the actual PR range because preserved commits, rather than just the PR
title, feed Release Please. Main CI also checks the current push's actual
`before..after` range and the complete unreleased non-merge history after the
matching real manifest-version tag, or bootstrap when that tag is absent.
Missing, zero, unavailable, empty push, and non-forward revisions fail closed.
A later valid main push cannot erase an earlier invalid unreleased commit whose
CI failed. Preserve published history; see Operations for owner-reviewed recovery.
Choose the type from the actual user-visible impact:

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
- PR/main-push commit classification, complete unreleased-history validation,
  and locked dependency installation.

## Current Protection State

On September 26, 2026, `gh api repos/davisbuilds/feed --jq .visibility`
returned `public`, and `gh api repos/davisbuilds/feed/branches/main/protection`
returned HTTP 404, `Branch not protected`. This observation does not establish
why protection is absent or whether other rules apply. The CI gates and review
discipline above remain the repository's merge policy; re-query protection
before relying on server enforcement.

## Recommended Ongoing Hygiene

1. Create short-lived feature branches from `main`.
2. Open PRs early; keep them focused.
3. Tidy your PR commit history *before* merging — reword/squash locally so what lands on `main` reads cleanly.
4. Pick **Create a merge commit** by default; pick **Rebase and merge** when linear history is materially better.
5. Refresh remote refs with `git fetch --prune`, then inspect `git worktree list`
   and candidate branch history before local cleanup. Preserve branches used by
   active worktrees or concurrent work. Delete only an individually verified,
   completed branch with `git branch -d BRANCH`; do not force-delete unmerged
   work or run a blanket deletion pipeline.
