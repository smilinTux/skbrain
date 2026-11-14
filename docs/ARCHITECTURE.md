# Architecture

## Flow

```mermaid
flowchart LR
  PAGES["canon pages (git, reviewed)"] --> LINT["skbrain lint (secret check)"]
  LINT --> PARSE["parser: pages/ only"]
  PARSE --> CHUNK["chunker: 512-token chunks"]
  CHUNK --> EMBED["embedder client"]
  EMBED --> PLAN["writer: content-hash diff, UpsertPlan"]
  PLAN -->|"sync --commit, projector login"| OPS[("ops schema: wiki_nodes, wiki_chunks, links")]
  OPS --> READ["read_api: reader login, hybrid search"]
  READ --> AGENT["agents retrieve before acting"]
```

## The pieces

| Module | Role | I/O |
|---|---|---|
| `parser` | page markdown to `OpsPage`: slug, type, typed edges, wikilinks | none (`walk_pages` reads `pages/`) |
| `chunker` | heading-aware chunks sized for a 512-token embedder | none |
| `embed` | `Embedder` protocol and an HTTP client for an embedding service | network, injectable |
| `writer` | content-hash-diffed `UpsertPlan` and the backend protocol | none until a backend is given |
| `postgres` | transactional projector backend for the `ops` schema | database |
| `read_api` | reader-side hybrid search and the retriever entry point | database, injectable |
| `secrets` | secret-shaped material lint | none |
| `check` | the hermetic instance CI check | files only |
| `config` | `skbrain.yaml`, canon resolution, the estate guard | none |
| `doctor` | non-mutating health checks, including `skbrain:pin` | database read |
| `cmdb_drift`, `kedb_coverage` | operator conditions read from state stores | optional siblings |

## Projection

The projection is derived and rebuildable from git. Rows are keyed by slug, so renaming the
canon repo never duplicates them. `sync` is a dry run by default. A committed projection
embeds every new or changed chunk (storing no vector and then skipping on the content hash
would hide the page from semantic search forever) and runs inside one transaction.

## Definition versus state

Pages are definitions. Incidents, problems, changes and live CMDB status are state in their own
stores, projected read-only. See SCHEMA.md section 5.

## Roles in the database

The `ops` schema is owned by the memory system's migrations, not by this repo. The projector
uses a read-write login and agents use a select-only reader login. `ops` is not granted to
`PUBLIC`.

## Agent integration

Retrieval is exposed as `skbrain.read_api:build_retriever`. An operator agent retrieves before
acting and only from its own estate's projection. The `skbrain operator` verbs
(`explain`, `observe`, `act`) are an observation-only contract: `act` always refuses.

## What this repo does not do

It does not own the database DDL, the installer pack, scheduling, or any estate's pages.
