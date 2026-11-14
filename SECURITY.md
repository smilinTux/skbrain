# Security

## Threat model summary

skbrain handles an estate's private operations knowledge. This public repo holds no
such knowledge. The risks it addresses:

- Private data published into this repo. Mitigation: `scripts/validate_public.py` on every PR and before every tag, with a private denylist and a fail-closed release run.
- One estate's canon projected into another estate's database. Mitigation: `skbrain.yaml` `estate` and `projector_nodes`, the `SKBRAIN_ESTATE` guard in `skbrain sync --commit`, no default canon.
- Secrets committed into pages. Mitigation: `skbrain lint` in CI and in every sync; pages name vault entries, never values.
- A bad page reaching retrieval. Mitigation: branch protection and review in the instance repo; the projection is derived and rebuilt from git.

## Reporting a vulnerability

Report privately to the maintainers through the contact on the
[smilinTux organization profile](https://github.com/smilinTux). Do not open a public
issue for a leak or a wall bypass. Expect an acknowledgement and a fix plan.

## Secret handling

The framework never reads or stores a credential beyond the database DSNs passed in
the environment (`SKBRAIN_PG_PROJECTOR_DSN`, `SKBRAIN_PG_READER_DSN`). Error output
never includes a DSN. CI in this repo and in instances holds no secrets and uploads no
artifacts.

## Dependency posture

Runtime dependencies: typer, click, pyyaml, requests, psycopg, jsonschema. Pin
instances to a release tag, never to a branch. The vendored skrsi files are read-only
copies recorded by tag in `src/skbrain/vendor/skrsi/SKRSI_TAG`.

CRYPTOGRAPHY_STANDARD: not applicable, this repo generates, stores and verifies no key material.
