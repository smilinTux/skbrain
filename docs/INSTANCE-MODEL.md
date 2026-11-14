# Instance model

skbrain follows the framework and instance pattern: a public framework repo, and one
private instance repo per estate.

## The rule

If another operator running a different estate would want it, it goes in the framework.
If it names a node, a host, a person, a client, a measured number or an estate, it goes in
the instance. When both are true the change is split: the mechanism to the framework, the
values to the instance.

## Repos

| Repo | Visibility | Holds |
|---|---|---|
| `skbrain` (this repo) | public | engine, schemas, checks, templates, docs |
| `skbrain-ops-template` | public, generated | the instance fixture, regenerated from `templates/instance-repo/`, never hand edited |
| `skbrain-ops-<estate>` | private, one per estate | that estate's pages, baselines and `skbrain.yaml` |

An estate canon has exactly one writer set and one projection. Two estates never share a
canon, a database, an agent identity with write on both, or a reader DSN.

## Instance layout

```
skbrain-ops-<estate>/
  framework/          # git submodule: skbrain at a release tag (read-only)
  skbrain.yaml        # the instance config
  AGENTS.md           # thin: points at framework/docs/SCHEMA.md, adds estate rules only
  README.md  SOP.md  SECURITY.md  CONTRIBUTING.md  CHANGELOG.md
  index.md  log.md
  pages/
    runbooks/ known-errors/ services/ nodes/ cis/ postmortems/ lessons/ synthesis/
  baselines/cmdb-drift.json
  .forgejo/workflows/skbrain-check.yml
```

Only files under `pages/` are pages. Every other `*.md` is a document and is never parsed
as a page. Directory placement under `pages/` is presentation only.

## skbrain.yaml

Schema `skbrain.instance.v1` (`schemas/skbrain-instance-v1.schema.json`). Unknown fields fail.

```yaml
schema: skbrain.instance.v1
estate: example                  # the repo must be named skbrain-ops-<estate>
namespace: ops
framework: skbrain-v1.0.0        # must equal the submodule tag and the installed version
forge: forge.example.org         # where this canon lives
projector_nodes: [example-1]     # the only hosts allowed to run `sync --commit`
skrsi:
  instance: example-org/skrsi-config-example   # the one skrsi instance allowed to open lesson PRs
writers: [example-writer-bot]    # identities allowed to author PRs
reviewers: [example-review-bot]  # identities allowed to review and merge
nodes: [node-example-1]          # optional: the node slugs this estate may name
```

## Pinning

- The instance pins an exact framework tag (`skbrain-vX.Y.Z`) as the `framework/` submodule.
- Nodes install the engine at the same version.
- `skbrain doctor` has the check `skbrain:pin`: installed version, `framework:` in `skbrain.yaml`
  and the submodule tag must be equal.
- Upgrading is a pull request in the instance that bumps the submodule and `framework:`.
  CI runs the NEW framework's check against the canon before merge.

## The estate wall

| Layer | Enforced by |
|---|---|
| Forge access | team-scoped repo permissions; no agent identity owns every estate |
| Projection | `projector_nodes` and the `SKBRAIN_ESTATE` guard in `skbrain sync --commit`; a node-local, unreplicated database |
| Retrieval | each estate's agents hold only their own estate's reader DSN |
| Content | the `skbrain check` estate guard: repo name, evidence refs and node names |
| Lessons for both estates | never in a canon: scrubbed into this repo's `docs/LESSONS.md` by pull request |
| Transport | git only; no file sync tool is a canon transport |

`SKBRAIN_ESTATE` is declared per node, derived from the node's own configuration and never
pasted by hand. There is no default canon: a node that has not declared `SKBRAIN_CANON`
stops, so it cannot work on another estate's canon by accident.

## CI

Each instance runs `.forgejo/workflows/skbrain-check.yml`: check out with submodules, install
the pinned framework, run `skbrain check --canon . --repo-name <repo>`. The check is
hermetic: no database, no network after checkout, no secrets, no uploaded artifacts.

## Review

`main` accepts no direct pushes. One approval from a `reviewers` identity is required, the
author never approves their own PR, and the `skbrain-check` status is required. Runbooks and
anything under `baselines/` additionally need the operator's approval, because a runbook is
executable knowledge and only the operator raises a drift baseline.

## Creating an instance

```bash
scripts/generate-instance-template.sh /path/to/new-repo      # writes the example fixture
```

Then replace every value (`skbrain.yaml`, node slugs, the example pages), add the
`framework/` submodule, and run `skbrain check --canon . --repo-name skbrain-ops-<estate>`.
