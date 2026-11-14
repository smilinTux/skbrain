# skbrain

Maturity tier: T0 (N/A, no key material). Version phase: Active v1 (1.0.0).

skbrain is the framework for an estate's operations brain: runbooks, known errors,
postmortems, lessons and configuration-item definitions kept as reviewed Markdown pages
in a private git repo, then projected into Postgres for retrieval. This repo is the
public part: the engine, the page schema, the checks, the templates and the docs. It
holds no estate data.

## What it is

| Part | Where |
|---|---|
| Engine: parser, chunker, embedder client, projector, reader, secret lint, doctor | `src/skbrain/` |
| Instance CI check (`skbrain check`) | `src/skbrain/check.py` |
| Instance config loader and estate guard | `src/skbrain/config.py` |
| Page and instance schemas | `schemas/` |
| Page templates and the example estate instance | `templates/` |
| Docs: schema, instance model, skrsi contract, architecture | `docs/` |

An estate keeps its pages in its own private repo, `skbrain-ops-<estate>`, which pins
a release of this framework as a `framework/` submodule. See
[docs/INSTANCE-MODEL.md](docs/INSTANCE-MODEL.md).

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                           # the test gate
skbrain check --canon templates/instance-repo \
  --repo-name skbrain-ops-example                   # check the example estate
python3 scripts/validate_public.py                  # scrub check for this repo
```

`skbrain` has no default canon. Every command that reads a canon needs `--canon PATH`
or `SKBRAIN_CANON`, and stops with an error when neither is set.

## Commands

| Command | What |
|---|---|
| `skbrain check --canon PATH` | Hermetic CI check: no database, no network |
| `skbrain lint --canon PATH` | Secret lint only |
| `skbrain sync --canon PATH [--commit]` | Lint, parse, project into the `ops` schema (dry run by default) |
| `skbrain search QUERY` | Search the projection with the reader identity |
| `skbrain doctor --canon PATH` | Non-mutating health checks, including `skbrain:pin` |
| `skbrain operator explain\|observe\|act` | The bounded out-of-process operator contract |

## Honest claims

- The check is hermetic: `tests/test_check.py::test_check_makes_no_database_or_network_use` fails if it opens a socket.
- The estate guard refuses `sync --commit` on the wrong estate or node: `tests/test_estate_guard.py`.
- The public tree is scrubbed by `scripts/validate_public.py`, run in CI and before every tag.

## Related projects / See also

- Depends on: [skrsi](https://github.com/smilinTux/skrsi), whose lesson schema and tag vocabulary are vendored read-only in `src/skbrain/vendor/skrsi/`.
- Used by: private estate canons named `skbrain-ops-<estate>`, and the `skos` installer pack.
- Siblings: [skmemory](https://github.com/smilinTux/skmemory), which owns the Postgres schema skbrain projects into.
- Standards: [sk-standards](https://github.com/smilinTux/sk-standards), including the repo doc and docs-freshness standards.
