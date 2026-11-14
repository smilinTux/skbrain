# Contributing

## Branches and review

- Branch from `main`: `feat/...`, `fix/...`, `docs/...`. Open a pull request; never push to `main`.
- One reviewer other than the author approves. The author does not merge.
- Work in a git worktree, not in a shared checkout.

## Commits

- Conventional prefix (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`), one logical change per commit.
- Add a `Co-Authored-By` trailer naming the agent or person who actually did the work, and only when that is true.
- Commit before you start a long test run.

## Test gate

```bash
pip install -e ".[dev]"
pytest -q
python3 scripts/validate_public.py
skbrain check --canon templates/instance-repo --repo-name skbrain-ops-example
```

Every feature needs at least three tests: the happy path, an edge case and a failure.

## What never goes in this repo

A hostname, an IP address, a person or client name, an estate name, a measured number
from a real estate, or a secret. If it names a node, a host, a person, a client or an
estate it belongs in the instance repo. The mechanism goes here, the values go there.
`scripts/validate_public.py` enforces it.

## Writing rules

No em or en dashes anywhere. Use a comma, a colon, a period or a hyphen.

## Changelog

Every PR that touches `src/` or `pyproject.toml` updates `CHANGELOG.md`.
