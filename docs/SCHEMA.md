# Page schema

The normative description of an skbrain page: the slug rule, the front matter, the body
conventions per type, the entity model and the edge vocabulary. `schemas/page-frontmatter-v1.schema.json`
is the machine form; `skbrain check` enforces both.

Every estate canon (`skbrain-ops-<estate>`) follows this schema and adds estate rules only
in its own thin `AGENTS.md`.

## 1. The slug convention

- One flat slug space for the whole `ops` namespace.
- Every page's `id` is its slug, kebab-case, and MUST equal the filename stem.
  `pages/runbooks/runbook-restart-widget-bridge.md` has `id: runbook-restart-widget-bridge`.
- Every `[[wikilink]]` targets a BARE slug: `[[service-widget]]`, never a path such as
  `[[services/service-widget]]` and never a title.
- The projector resolves bare slugs against the namespace id set, never against file paths.
  Directory placement is presentation only.
- A `[[wikilink]]` to a slug that does not exist yet is a to-do marker. `skbrain check`
  reports it as a warning, never a failure. Liberal linking is the rule.
- `skbrain check` FAILS a page whose filename stem differs from its `id`, and a canon
  where two files share a slug.

Slug prefixes by type (keep them, they make the flat space readable):
`runbook-*`, `service-*`, `node-*`, `ke-*` (known error, matches the KEDB id verbatim),
`ci-*`, `postmortem-*`, `synthesis-*`, `lesson-*`.

## 2. Front matter

Every page carries this shape:

```yaml
---
id: runbook-restart-widget-bridge   # stable slug == filename stem
type: runbook                       # runbook | ci | service | node | known-error | postmortem | synthesis | lesson
namespace: ops
lifecycle: canon                    # draft | reviewed | canon
title: Recover a silently wedged widget bridge
tags: [widget, bridge]              # free topic tags
lesson_tags: [stale-config]         # optional; keys of the skrsi lesson-tags vocabulary ONLY
edges:                              # typed edges (section 4)
  - {target: ke-widget-wedge, type: remediates}
  - {target: service-widget, type: touches}
state_refs:                         # pointers INTO operational stores, never state itself
  kedb: ke-widget-wedge             # known-error id
  actions: [restart-widget-bridge]  # operator standard-action names
evidence:                           # optional; see SKRSI-CONTRACT.md
  - {kind: skrsi-evidence, ref: "skrsi-config-example@a1b2c3d:evidence/example-1/2026-01-15.json"}
created: 2026-01-15
updated: 2026-01-15
---
```

Required: `id`, `type`, `namespace`, `lifecycle`, `title`, `created`, `updated`. Unknown
fields fail, except the three optional provenance fields `origin`, `source_repo` and
`source_path`. `namespace` is always `ops` in v1.

Plain `[[wikilinks]]` in the body ALSO produce `links_to` edges (backlinks are the reverse
traversal), so link liberally in prose even when there is no typed edge.

`lesson` pages are the exception: their whole front matter is the skrsi `lesson-v1` schema
plus the canon envelope (`namespace`, `lifecycle`, `edges`, `created`, `updated`,
`state_refs`). See SKRSI-CONTRACT.md.

## 3. Body conventions per type

- **runbook**: Preconditions, Steps (numbered, copy-paste commands grounded in real units and paths), Verify, Rollback, Escalate. Reference secrets by vault entry name, never inline.
- **ci**: the DEFINITION of the configuration item (intended type, owner, node, intended relationships using the CMDB vocabulary verbatim, intended key attributes such as port, unit name, data path) plus links to the runbooks that touch it. No live status in the page.
- **known-error**: symptoms, root cause, workaround, permanent-fix status, with a link to the remediating runbook and the affected service or node. `id` is the `ke-*` id the operator adapters reference.
- **service / node**: the stable description plus a links hub. Node pages carry build and restore procedure links, never secrets.
- **postmortem**: what happened, timeline, root cause, what changed, with `about` (the incident or service) and `promoted` (the runbook or known error it produced) edges.
- **synthesis**: a cross-cutting operations thesis or standard, heavily wikilinked.
- **lesson**: one rule with its evidence and its enforcing check, per the skrsi lesson contract.

## 4. Entity model and edge vocabulary

Vertices, one graph label per `type`, plus projected state kinds: `Runbook`,
`ConfigurationItem`, `Service`, `Node`, `KnownError`, `Postmortem`, `Synthesis`, `Lesson`,
and (projected, read-only) `Incident`, `Problem`, `Change`.

Typed edges authorable in front matter (`edges[].type`):

| Edge | Meaning |
|---|---|
| `remediates` | `Runbook` to `KnownError` |
| `touches` | `Runbook` to `Node`, `Service` or `ConfigurationItem` |
| `depends_on`, `runs_on`, `hosts`, `connects_to` | between configuration items and nodes; the CMDB relationship vocabulary verbatim |
| `documents` | `KnownError` to `Problem`, or a synthesis to what it governs |
| `about` | `Postmortem` to the incident or service it concerns |
| `promoted` | `Postmortem` to the runbook or known error it produced |

State-derived edges (`affects`, `matches`, `resolved_by`, `modifies`, `caused`) are written
by the projector from the state stores. They are never authored in git. Definition edges
from pages carry `provenance: definition`; observed edges carry `provenance: observed`, so
drift is queryable.

## 5. Definition versus state

- Known-error pages are canon here; the projector upserts them into the KEDB store.
- CI pages are the definition; the CMDB store holds live status. Drift is the definition minus the state. Never write live status into a CI page.
- Incidents, problems and changes are STATE. They are projected read-only into the `ops` namespace so they take part in backlinks, retrieval and graph traversal. They are never written into the canon repo.
- A CMDB drift baseline (`baselines/cmdb-drift.json`) lives in the canon. Lower it as findings are fixed; only the operator raises it.

## 6. Writing rules

- No em or en dashes in any `*.md`. Use a comma, colon, period or hyphen. `skbrain check` fails on them.
- No secrets. Name the vault entry, never the value. `skbrain lint` fails on secret-shaped text.
- Topology, ports and unit names are fine in a private canon; credentials are not.
