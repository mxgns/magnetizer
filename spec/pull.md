# `pull.py` specification (planning document)

This is a full design spec for `pull.py`, written ahead of implementation so the design can be reviewed as a whole. It is **not** part of `spec/specification.md` — that gets updated alongside the actual implementation, per this project's usual spec-first convention. (See issue #61.)

### Purpose

Since `ingest.py` was wired into CI (publish.yml Stage 7), posts dropped into `inbox/` on the iPad get committed and pushed to `blog:main` by CI directly — without any local step, the Mac's own checkout can silently fall behind `origin/main`. `pull.py` is the minimal, safe counterpart to `publish.py`: it brings the local project's own source (not the generated `dist/` output — see [Publishing](../README.md#publishing) for that, which already has its own `git pull --rebase` guidance for `dist/`) up to date with `origin/main`, strictly by fast-forwarding.

It is not a general sync tool. It never merges, never rebases, and never touches anything other than deciding whether a fast-forward is possible and performing it. Its job is catching up the *entire* project source on changes made elsewhere — not resolving conflicts, which is explicitly a manual job.

**Scope is deliberately whole-repo, not restricted to `content/`.** Issue #61 frames the motivating case as CI's ingest-and-push step, which only ever touches `content/`/`inbox/` — but changes to `templates/`, `resources/` (CSS/JS), or `config.yaml` also get made and pushed from elsewhere, not just content. Restricting the fast-forward to a subset of paths would mean those changes silently never reach a Mac session that only ever runs `pull.py`, which is worse than the problem this tool exists to solve. A single `git merge --ff-only origin/main` already fast-forwards correctly regardless of which paths actually changed — there's no need (and no safe way, short of partial-tree checkouts that reintroduce their own staleness/conflict risks) to special-case this to one directory.

### CLI

```
pull.py
```

Run from the project root, same convention as `build.py`/`new-post.py`/`publish.py`. No arguments — deliberately minimal, matching the issue's own framing.

### Behaviour

1. **Branch guard.** Refuses to run unless the current branch is `main` — the same guard `source_publisher.py:publish_source` already uses, for the same reason: this tool's only job is keeping local `main` in sync with `origin main`, so running it elsewhere would be meaningless (and silently fast-forwarding the wrong branch would be worse than meaningless).
2. **Fetch.** `git fetch origin main`.
3. **Compare histories** via `git rev-list --count` in both directions between `HEAD` and `origin/main`:
   - **Nothing new on origin** (local is even with or ahead of origin): no-op. Being locally ahead (unpushed local commits) is not an error here — that's `publish.py`'s concern, not this tool's.
   - **Purely behind** (origin has commits local doesn't, local has none origin doesn't): fast-forward — `git merge --ff-only origin/main`.
   - **Diverged** (both sides have commits the other doesn't): hard error, no changes made. This is exactly the scenario a real `--ff-only` pull is designed to refuse, and exactly the scenario that needs a human to look at it (e.g. `git rebase origin/main`) rather than any automatic resolution.
4. **Uncommitted local changes that the fast-forward would overwrite** are handled by `git merge --ff-only`'s own existing safety check, which refuses with a nonzero exit rather than clobbering anything — surfaced the same way every other git failure in this codebase is (`RuntimeError` with the real git stderr attached).

No file in the working tree is modified except via the one `git merge --ff-only` call — there is no separate "restrict this to `content/`" step (see Scope note under Purpose above).

### Output

- Nothing to pull: `Already up to date.`, exit 0, no changes.
- Successful fast-forward: `Pulled N commit(s).` (N = however many), exit 0.
- Diverged: clear error naming both commit counts (e.g. `Local main and origin/main have diverged (2 commit(s) local, 3 commit(s) origin) — pull.py only fast-forwards, it never merges. Resolve manually (e.g. 'git rebase origin/main').`), nonzero exit, no changes.
- Not on `main`: clear error naming the current branch, nonzero exit, no changes (mirrors `publish_source`'s existing wording).
- Any other git failure (e.g. a fast-forward blocked by uncommitted local changes, a timed-out `git fetch`, or no `git` executable on `PATH`): a clear error (git's own stderr where there is one), nonzero exit, no changes.
- Detached `HEAD`: treated as "not on `main`" — the error names it as detached rather than literally quoting the branch name as `'HEAD'`.

### Implementation note

Mirrors `source_publisher.py`'s existing shape (`_run_git`/`_run_git_probe` helpers, 60s timeout per git call, `RuntimeError` on failure) rather than introducing a different error-handling style for what is otherwise the same kind of tool. `magnetizer/pull.py` holds the logic (a single `pull(project_dir)` function); the root `pull.py` is a thin CLI wrapper, same split as `ingest.py`/`inbox.py` and `publish.py`/`source_publisher.py`.

### Test plan

Not on `main` errors, names the branch, makes no git calls beyond the branch check; detached `HEAD` errors with a clear message, not a literal `'HEAD'` branch name; already up to date (both counts zero) is a clean no-op; purely ahead (local has unpushed commits, origin has nothing new) is also a clean no-op, not an error; purely behind fast-forwards and reports the right commit count; diverged (both counts nonzero) raises, names both counts, and runs no merge; a fast-forward blocked by conflicting uncommitted local changes raises with git's real stderr and leaves the working tree exactly as it was; a timed-out git call and a missing `git` executable both raise `RuntimeError` rather than propagating a raw exception; every git call specifies a timeout. CLI-level (real git repos, local bare remote, no network): a real incoming fast-forward (simulating CI's ingest-and-push) is pulled and the new file appears locally; already-up-to-date prints its message and exits 0; a diverged repo exits with status 1 and no local changes; a wrong-branch run exits with status 1 naming the branch; `--help` exits 0.

---

## Status

Ready for implementation.
