# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-14

### Changed
- Vendored skrsi vocabulary moves to skrsi `main` at `aafcd22a`: four lesson tags from skrsi#17 (`token-budget`,
  `retry-amplification`, `no-attribution`, `unalerted-rate`) are now accepted by `skbrain check`.

## [Unreleased]

## [1.0.0] - 2026-11-14

First framework release. The engine was extracted, with its history, from the
`skos.brain.ops` package of the skos installer; the 0.x line below is that history.

### Added
- `skbrain check --canon PATH`: the hermetic instance CI check (secret lint, page parse, front matter schemas, slug and link rules, dashes, estate guard, index coverage).
- `skbrain.yaml` instance config (`skbrain.instance.v1`), loaded and validated by `skbrain.config`; unknown fields fail.
- `sync --commit` estate guard: refuses when `SKBRAIN_ESTATE` differs from the canon's estate or the host is not in `projector_nodes`.
- `skbrain:pin` doctor check: installed version, `skbrain.yaml` `framework` and the `framework/` submodule tag must agree.
- Schemas `skbrain-instance-v1` and `page-frontmatter-v1`; the skrsi `lesson-v1` schema and `lesson-tags-v1` vocabulary vendored read-only.
- Page templates, the example estate instance fixture, `scripts/generate-instance-template.sh` and `scripts/validate_public.py`.
- Docs: SCHEMA, INSTANCE-MODEL, SKRSI-CONTRACT, ARCHITECTURE, LESSONS.

### Changed
- `walk_pages` parses only files under `pages/`; a canon with no `pages/` directory is an error.
- There is no default canon: `--canon` or `SKBRAIN_CANON`, otherwise exit 2.
- `lint_tree` skips the `framework/` submodule and `.git`.
- `doctor` checks that read the skos installer pack degrade when that pack is not installed.
- Estate-specific comments in the engine were made generic.

### Removed
- Em and en dashes from all sources.

## [0.x] - history

0.x is the `skos.brain.ops` history: SB1.1 projection foundation, KEDB coverage, the
operator contract, CMDB drift gating, and live-projection fixes. See `git log`.
