# skrsi contract

How skrsi (the evidence and recursive improvement system) relates to an skbrain canon.
Normative. The direction is one way: skrsi proposes, skbrain pages record.

## 1. Direction and ownership

- skrsi owns evidence, evaluations, recurrence counts and lesson tags. skbrain owns pages.
- skrsi WRITES into a canon only by opening a pull request. It never pushes to `main`, never merges, never edits a merged page in place (a change is a new PR), and never writes recurrence or metrics into a page.
- skbrain never writes into an skrsi instance. A page links to skrsi evidence by commit, and that is all.
- **Invariant 7 stays:** skrsi never selects what a final gate runs. Nothing in a page (a runbook, a lesson, a `check:` field) is read by a gate as an instruction to skip or choose checks. `skbrain check` is fixed by the pinned framework, not by page content, and skrsi has no write path to the framework pin.
- **Invariant 2 applied:** the PR author (the skrsi retrospective identity) and the merging reviewer are different identities, enforced by branch protection plus a CI warning when `writers` and `reviewers` overlap.

## 2. Pull request format

- Branch: `skrsi/<YYYY-MM-DD>-<slug>`. Title: `postmortem: <date> <short>`, `lesson: <short>` or `known-error: <short>`.
- One page per PR. A postmortem and the lessons it produced may share one PR if they cite the same evidence.
- The body must contain: the evidence list with `skrsi-config-<estate>@<commit>:<path>` refs; which lesson tags apply; whether any tag is missing from skrsi (link the skrsi issue, never invent a tag); and the line "Not merged by the author."
- Every new page starts `lifecycle: draft`. The reviewer moves it to `reviewed` or `canon` in the merge.
- The skrsi instance that opens the PR must equal `skbrain.yaml` `skrsi.instance`. `skbrain check` verifies that the evidence refs name that instance: a ref from another estate's skrsi instance fails the check.

## 3. Front matter fields that cite skrsi

| Field | Type | Meaning |
|---|---|---|
| `evidence` | list of `{kind, ref}` | `kind` is one of `skrsi-evidence`, `skrsi-evaluation`, `pr`, `incident`, `card`. `ref` is commit-pinned (`<repo>@<sha>:<path>`), never a branch. A ref that cites skrsi must name `skrsi.instance` |
| `lesson_tags` | list | keys of the skrsi `lesson-tags-v1` vocabulary only; empty is allowed |
| `skrsi_metrics` | list of `{target, metric}` | optional back-links to skrsi target ids and metric names, so a page says which metric would show recurrence |
| `lesson` pages | whole front matter | exactly skrsi `lesson-v1` plus the canon envelope (`namespace`, `lifecycle`, `edges`, `created`, `updated`, `state_refs`); no `recurrence`, no `origin` |

Free `tags` remain free on non-lesson pages. `lesson_tags` is the only controlled field.
On a `lesson` page the skrsi `tags` field is itself limited to the vocabulary.

## 4. The vendored copy

skbrain checks lesson pages and tags against a read-only copy of skrsi's `lesson-v1.schema.json`
and `lesson-tags-v1.json`, kept in `src/skbrain/vendor/skrsi/` with the source release recorded in
`SKRSI_TAG`. skrsi owns the vocabulary. Moving to a newer vocabulary is a framework release.

## 5. Who reviews and merges

The estate decides in its own `AGENTS.md`. The framework requires only that the author never
merges and that runbooks and baselines get the operator's approval.

## 6. A tag skrsi does not have yet

Do not invent one. Carry the term in the free `tags` of the page, link the skrsi issue in the PR
body, and move it to `lesson_tags` after skrsi publishes it and the framework vendors that release.
