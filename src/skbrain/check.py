"""skbrain.check - the hermetic CI check for an estate canon (design 3.4).

``skbrain check --canon PATH`` is what an instance repo's CI runs against its
own pinned framework. It reads files only: no database, no DSN, no network.

Checks, in order:

1. secret lint (the same rules as ``skbrain lint``);
2. every page under ``pages/`` (and only there) parses;
3. front matter validates against ``page-frontmatter-v1``; ``lesson`` pages
   validate against the vendored skrsi ``lesson-v1`` schema; ``lesson_tags``
   and lesson ``tags`` are keys of the vendored skrsi ``lesson-tags-v1``;
4. the page ``id`` equals the filename stem; wikilinks are bare slugs;
   dangling links are REPORTED (a warning), not failed;
5. no em or en dashes in any ``*.md``;
6. the estate guard: ``skbrain.yaml`` names the estate the repo is named for,
   evidence refs that cite skrsi name the declared ``skrsi.instance``, and (when
   the config lists ``nodes``) no page names a ``node-<x>`` slug outside it;
7. ``index.md`` lists every page (a warning for now).

Findings are ``error`` (the check fails) or ``warning`` (reported only).
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from skbrain.config import (
    ConfigError,
    InstanceConfig,
    has_config,
    load_config,
)
from skbrain.parser import PAGES_DIR, OpsParseError, extract_wikilinks, parse_page
from skbrain.secrets import lint_tree

ERROR = "error"
WARNING = "warning"

#: Top-level directories that are not canon content.
_SKIP_TOP_DIRS = frozenset({"framework", ".git", "node_modules", ".venv"})

_DASHES = (chr(0x2013), chr(0x2014))  # en dash, em dash
_RAW_WIKILINK_RE = re.compile(r"\[\[\s*([^\]|]+?)\s*(?:\|[^\]]*)?\]\]")
_NODE_TOKEN_RE = re.compile(r"(?<![a-z0-9-])node-[a-z0-9][a-z0-9-]*[a-z0-9](?![a-z0-9-])")
_PINNED_REF_RE = re.compile(r"^(?P<repo>[^@:]+)@(?P<sha>[0-9a-f]{7,40}):")


@dataclass(frozen=True)
class Finding:
    """One result of the check."""

    severity: str
    code: str
    path: str
    message: str


@dataclass
class CheckReport:
    """All findings of one run."""

    findings: list[Finding] = field(default_factory=list)
    pages: int = 0

    def add(self, severity: str, code: str, path: str, message: str) -> None:
        self.findings.append(Finding(severity, code, path, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "pages": self.pages,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "findings": [asdict(f) for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Schema and vendored data loading
# ---------------------------------------------------------------------------


def _schema_dir() -> Path:
    """Where ``schemas/`` lives: the repo checkout, else the installed package."""
    repo = Path(__file__).resolve().parents[2] / "schemas"
    if repo.is_dir():
        return repo
    return Path(str(resources.files("skbrain") / "_data" / "schemas"))


def _vendor_dir() -> Path:
    return Path(str(resources.files("skbrain") / "vendor" / "skrsi"))


@lru_cache(maxsize=None)
def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def page_schema() -> dict[str, Any]:
    """The ``page-frontmatter-v1`` schema."""
    return _load_json(str(_schema_dir() / "page-frontmatter-v1.schema.json"))


def lesson_schema() -> dict[str, Any]:
    """The vendored skrsi ``lesson-v1`` schema."""
    return _load_json(str(_vendor_dir() / "lesson-v1.schema.json"))


def lesson_tag_keys() -> frozenset[str]:
    """The keys of the vendored skrsi ``lesson-tags-v1`` vocabulary."""
    return frozenset(_load_json(str(_vendor_dir() / "lesson-tags-v1.json"))["tags"])


def skrsi_tag() -> str:
    """The skrsi release the vendored vocabulary was copied from."""
    return (_vendor_dir() / "SKRSI_TAG").read_text(encoding="utf-8").strip()


def _normalize(value: Any) -> Any:
    """Turn YAML dates into ``YYYY-MM-DD`` strings so schemas can check them."""
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _schema_errors(schema: dict[str, Any], instance: Any) -> list[str]:
    out = []
    for err in sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(map(str, e.path))):
        where = ".".join(str(p) for p in err.path) or "(front matter)"
        out.append(f"{where}: {err.message[:200]}")
    return out


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def _canon_markdown(canon: Path) -> list[Path]:
    return [
        p
        for p in sorted(canon.rglob("*.md"))
        if p.relative_to(canon).parts[0] not in _SKIP_TOP_DIRS
    ]


def _check_dashes(canon: Path, report: CheckReport) -> None:
    for md in _canon_markdown(canon):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = [i for i, line in enumerate(text.splitlines(), 1) if any(d in line for d in _DASHES)]
        if lines:
            shown = ", ".join(str(n) for n in lines[:5])
            more = f" (+{len(lines) - 5} more)" if len(lines) > 5 else ""
            report.add(
                ERROR,
                "dash",
                str(md.relative_to(canon)),
                f"em or en dash on line(s) {shown}{more}; use a comma, colon, period or hyphen",
            )


def _check_evidence_refs(
    rel: str, fm: dict[str, Any], cfg: InstanceConfig | None, report: CheckReport
) -> None:
    evidence = fm.get("evidence")
    if not isinstance(evidence, list):
        return
    instance_name = cfg.skrsi_instance.split("/", 1)[1] if cfg else None
    for item in evidence:
        if not isinstance(item, dict):
            continue
        kind, ref = str(item.get("kind", "")), str(item.get("ref", ""))
        if not (kind.startswith("skrsi-") or ref.startswith("skrsi-config-")):
            continue
        m = _PINNED_REF_RE.match(ref)
        if not m:
            report.add(
                ERROR,
                "evidence-not-pinned",
                rel,
                f"evidence ref {ref!r} must be commit-pinned: <repo>@<sha>:<path>",
            )
            continue
        if instance_name is not None and m.group("repo") not in (instance_name, cfg.skrsi_instance):
            report.add(
                ERROR,
                "evidence-wrong-instance",
                rel,
                f"evidence ref names {m.group('repo')!r} but this canon's skrsi.instance is "
                f"{cfg.skrsi_instance!r} (an evidence ref from another estate does not belong here)",
            )


def run_check(canon: Path | str, *, repo_name: str | None = None) -> CheckReport:
    """Run every check against *canon* and return the report. Never raises on content.

    Args:
        canon: the canon repo root.
        repo_name: the repo's name when the directory name is not it (CI
            checkouts); defaults to the canon directory's own name.
    """
    root = Path(canon).expanduser()
    report = CheckReport()
    if not root.is_dir():
        report.add(ERROR, "canon", str(root), "canon directory does not exist")
        return report
    root = root.resolve()

    # 6a. config + estate wall (loaded first: other checks use it)
    cfg: InstanceConfig | None = None
    if not has_config(root):
        report.add(ERROR, "config", "skbrain.yaml", "skbrain.yaml is missing")
    else:
        try:
            cfg = load_config(root)
        except ConfigError as exc:
            report.add(ERROR, "config", "skbrain.yaml", str(exc))
    if cfg is not None:
        name = repo_name if repo_name else root.name
        if not name.endswith(f"-{cfg.estate}"):
            report.add(
                ERROR,
                "estate-repo-name",
                "skbrain.yaml",
                f"estate is {cfg.estate!r} but the repo is named {name!r}; "
                f"an estate canon is named {cfg.repo_name}",
            )
        overlap = sorted(set(cfg.writers) & set(cfg.reviewers))
        if overlap:
            report.add(
                WARNING,
                "writer-reviewer-overlap",
                "skbrain.yaml",
                f"identities are both writer and reviewer: {', '.join(overlap)}",
            )

    # 1. secret lint
    for f in lint_tree(root):
        report.add(ERROR, "secret", f"{Path(f.path).name}:{f.line}", f"secret-shaped material ({f.rule})")

    # 5. dashes
    _check_dashes(root, report)

    # 2. pages
    pages_root = root / PAGES_DIR
    if not pages_root.is_dir():
        report.add(ERROR, "pages", PAGES_DIR, "canon has no pages/ directory")
        return report

    known_tags = lesson_tag_keys()
    slugs: dict[str, str] = {}
    parsed: list[tuple[str, Any]] = []
    for md in sorted(pages_root.rglob("*.md")):
        if md.stem.startswith("_"):
            continue
        rel = str(md.relative_to(root))
        report.pages += 1
        slug = md.stem
        if slug != slug.lower():
            report.add(ERROR, "slug", rel, "filename stem must be lowercase (it is the page id)")
        slug = slug.lower()
        if slug in slugs:
            report.add(ERROR, "duplicate-slug", rel, f"slug {slug!r} is also used by {slugs[slug]}")
        slugs[slug] = rel
        try:
            page = parse_page(md.read_text(encoding="utf-8"), slug=slug)
        except OpsParseError as exc:
            report.add(ERROR, "parse", rel, str(exc))
            continue
        except UnicodeDecodeError:
            report.add(ERROR, "parse", rel, "page is not valid UTF-8")
            continue
        fm = _normalize(page.frontmatter)
        if "id" not in fm:
            report.add(ERROR, "slug", rel, "front matter has no id (id must equal the filename stem)")
        parsed.append((rel, page))

        # 3. front matter
        if page.kind == "lesson":
            for msg in _schema_errors(lesson_schema(), fm):
                report.add(ERROR, "frontmatter", rel, f"lesson-v1: {msg}")
            bad = sorted(set(fm.get("tags") or []) - known_tags) if isinstance(fm.get("tags"), list) else []
            if bad:
                report.add(
                    ERROR,
                    "lesson-tag",
                    rel,
                    f"lesson tags not in skrsi lesson-tags-v1 ({skrsi_tag()}): {', '.join(map(str, bad))}",
                )
        else:
            for msg in _schema_errors(page_schema(), fm):
                report.add(ERROR, "frontmatter", rel, msg)
            lt = fm.get("lesson_tags")
            if isinstance(lt, list):
                bad = sorted(set(map(str, lt)) - known_tags)
                if bad:
                    report.add(
                        ERROR,
                        "lesson-tag",
                        rel,
                        f"lesson_tags not in skrsi lesson-tags-v1 ({skrsi_tag()}): {', '.join(bad)}",
                    )

        # 4. bare-slug wikilinks
        for raw in _RAW_WIKILINK_RE.findall(page.body_md):
            t = raw.strip()
            if "/" in t or "\\" in t or " " in t or t.lower().endswith(".md"):
                report.add(
                    ERROR,
                    "wikilink-not-bare",
                    rel,
                    f"wikilink [[{t}]] must be a bare slug, not a path or title",
                )

        # 6b. evidence refs
        _check_evidence_refs(rel, fm, cfg, report)

        # 6c. node-name guard (warning in v1)
        if cfg is not None and cfg.nodes is not None:
            haystack = yaml.safe_dump(page.frontmatter, default_flow_style=True) + "\n" + page.body_md
            outside = sorted({t for t in _NODE_TOKEN_RE.findall(haystack) if t not in cfg.nodes})
            if outside:
                report.add(
                    WARNING,
                    "node-outside-estate",
                    rel,
                    f"names node slug(s) not in this estate's nodes list: {', '.join(outside)}",
                )

    # 4b. dangling links (reported, not failed)
    for rel, page in parsed:
        targets = set(page.wikilinks) | {e.dst for e in page.edges}
        dangling = sorted(t for t in targets if t not in slugs)
        if dangling:
            report.add(
                WARNING,
                "dangling-link",
                rel,
                f"links to slug(s) with no page yet: {', '.join(dangling)}",
            )

    # 7. index.md lists every page (warning for now)
    index = root / "index.md"
    if not index.is_file():
        report.add(WARNING, "index-missing", "index.md", "index.md is missing")
    else:
        listed = set(extract_wikilinks(index.read_text(encoding="utf-8")))
        unlisted = sorted(set(slugs) - listed)
        if unlisted:
            report.add(
                WARNING,
                "index-unlisted",
                "index.md",
                f"{len(unlisted)} page(s) not listed in index.md: {', '.join(unlisted[:8])}"
                + (", ..." if len(unlisted) > 8 else ""),
            )
    return report
