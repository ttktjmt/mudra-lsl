# Autonomous development cycle

The procedure a scheduled agent session runs. Read `CLAUDE.md` first (it is the
charter: persona, mission, autonomy limits, model routing). This file is only
the loop. Work as **ponytail**. English only. One focused unit of work per
cycle — do not sprawl, and if nothing is actionable, do nothing and say so.
Inventing busywork is a failure, not diligence.

## 1. Orient

- `git fetch origin` and check out `main` clean. If a prior cycle left an open
  branch/PR, prefer finishing it over starting new work.
- Skim `docs/mudraka-wishlist.md` and `docs/adr/` for current state. Do not
  relitigate accepted ADRs.
- Ensure `ttktjmt/mudraka` is reachable for issue/release checks. If it is not
  in this session's scope, add it (`add_repo`); PyPI checks are public.

## 2. Clear the human's desk first

- Check open `decision-review` issues on `ttktjmt/mudra-lsl` for maintainer
  responses. If a decision was approved: flip the matching ADR `Proposed →
  Accepted` and merge the held PR (if CI is green). If revised: adjust and
  re-request. This unblocks work already in flight before starting anything new.
- Check open PRs for review comments or red CI; address them.

## 3. Scan the mudraka loop

For each wishlist item (`docs/mudraka-wishlist.md`):

- Read the linked mudraka issue's state and mudraka's latest PyPI release.
- **Gap not yet requested** → file a clear issue on `ttktjmt/mudraka` (grounded
  in the real `IDecoder` / `StreamProfile` interface), link it in the wishlist.
- **Issue resolved and released** → this is implementation work (step 4).
- Otherwise → nothing to do for that item this cycle.

## 4. Pick and do ONE unit of work

Choose the single highest-value actionable item. In rough priority:

1. A newly-available signal to implement (mudraka issue resolved + released).
2. A correctness bug or failing/ flaky test.
3. A concrete robustness/quality gap with evidence (not speculative).
4. Docs/examples that are wrong or missing for shipped behavior.

Then, as ponytail:

- Branch: `agent/<short-topic>`.
- Implement the **minimum that works**, behind the existing `StreamPublisher`
  seam for new signals (one class + one line in `app.py`, not a rewrite).
- Write/extend offline tests using the synthetic-frame → real-`mudraka` → fake
  outlet pattern. Assert channel count, dtype, unit/type metadata, transpose,
  and the `lost > 0` path.
- `uv run ruff check .` and `uv run pytest` must pass.
- Write an ADR if the decision has lasting consequences. Significant-but-
  reversible decisions get a `Proposed` ADR + a `decision-review` issue (see
  CLAUDE.md); do not merge those until resolved.

## 5. Land it

- Open a PR with a description that states what changed and why, and links any
  ADR / mudraka issue.
- **Low-risk** (bug fix, docs, additive publisher, patch dependency bump):
  self-merge once CI is green, then update the wishlist/roadmap state.
- **Otherwise** (public API shape, breaking bump, anything under a `Proposed`
  ADR, or touching an irreversible): leave the PR open for the maintainer. Never
  cut a release or bump the public version yourself — prepare it and hand off.

## 6. Never (hard stops from CLAUDE.md)

- Do not write the README RawData-license / positioning placeholder.
- Do not modify or work around `mudraka`; file an issue instead.
- Do not publish to PyPI, change the package name or license, or tag a release
  autonomously.

## 7. Wrap up

End every cycle with a short written summary: what you changed (with PR/issue
links), what is blocked and on whom, and the single most likely next unit of
work. If you did nothing, say why — that is a valid and often correct outcome.
