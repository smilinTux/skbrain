"""Non-mutating health checks for a fresh or installed skbrain pack."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from skbrain.config import FRAMEWORK_PREFIX, ConfigError, has_config, load_config
from skbrain.kedb_coverage import compute_kedb_coverage
from skbrain.postgres import _connect
from skbrain.secrets import lint_tree


def _pack_loader() -> Any | None:
    """Return the ``skos.packs.loader`` module, or ``None`` without the skos pack.

    The installer pack (manifest, fleet cron objects) lives in the separate
    ``skos`` package. A framework-only install has no pack, so the two checks
    that read the pack degrade instead of importing it unconditionally.
    """
    try:
        return importlib.import_module("skos.packs.loader")
    except Exception:  # noqa: BLE001 - any import failure means "no pack here"
        return None


@dataclass(frozen=True)
class Check:
    """One machine-readable health assertion."""

    name: str
    ok: bool
    detail: str


def _skcapstone_home() -> Path:
    """The skcapstone home dir. Mirrors every other skos module's identical
    helper (e.g. ``skos.watchdog.adapters.itil._skcapstone_home``): same env
    var, same default, so no two readers of skcapstone state can disagree."""
    return Path(os.environ.get("SKCAPSTONE_HOME", str(Path.home() / ".skcapstone"))).expanduser()


def _installed_version() -> str | None:
    """The installed skbrain package version, or None when not installed."""
    try:
        return importlib.metadata.version("skbrain")
    except importlib.metadata.PackageNotFoundError:
        return None


def _submodule_tag(framework_dir: Path) -> str | None:
    """The release tag the ``framework/`` submodule is checked out at, or None.

    Uses ``git describe --exact-match``; falls back to the submodule's own
    ``pyproject.toml`` version when git cannot answer (a plain copy, no git).
    """
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(framework_dir), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        tag = out.stdout.strip()
        if out.returncode == 0 and tag:
            return tag
    except (OSError, subprocess.SubprocessError):
        pass
    pyproject = framework_dir / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version") and "=" in line:
                return FRAMEWORK_PREFIX + line.split("=", 1)[1].strip().strip("\"'")
    return None


def _check_pin(
    canon: Path,
    *,
    installed: str | None = None,
    submodule_tag: str | None = None,
) -> Check:
    """``skbrain:pin`` -- installed version == ``skbrain.yaml`` framework == submodule tag.

    The three must agree so a node never projects a canon with an engine
    version the canon did not pin. A canon with no ``skbrain.yaml`` is a legacy
    canon: the pin is not declared, so it is not enforced (the estate guard in
    ``skbrain sync`` is off for it too). The submodule leg applies only when a
    ``framework/`` directory exists. ``installed`` and ``submodule_tag`` are
    injectable for tests.
    """
    if not has_config(canon):
        return Check("skbrain:pin", True, "legacy canon: no skbrain.yaml, pin not declared")
    try:
        cfg = load_config(canon)
    except ConfigError as exc:
        return Check("skbrain:pin", False, f"skbrain.yaml invalid ({exc})")
    have = installed if installed is not None else _installed_version()
    if have is None:
        return Check("skbrain:pin", False, "skbrain package version unknown")
    want = cfg.framework_version
    if have != want:
        return Check(
            "skbrain:pin", False, f"installed skbrain {have} != pinned {cfg.framework} in skbrain.yaml"
        )
    framework_dir = canon / "framework"
    if framework_dir.is_dir():
        tag = submodule_tag if submodule_tag is not None else _submodule_tag(framework_dir)
        if tag != cfg.framework:
            return Check(
                "skbrain:pin",
                False,
                f"framework/ submodule is at {tag or 'no release tag'}, skbrain.yaml pins {cfg.framework}",
            )
        return Check("skbrain:pin", True, f"{cfg.framework}: installed, skbrain.yaml and submodule agree")
    return Check("skbrain:pin", True, f"{cfg.framework}: installed matches skbrain.yaml (no framework/ submodule)")


def _check_kedb(
    canon: Path, *, kedb_loader: Callable[[Path], list[str]] | None = None
) -> Check:
    """``skbrain:kedb`` -- real KedbCanonCovered coverage, doctor-shaped.

    Reuses :func:`compute_kedb_coverage` (card 8c6e05e3) so the doctor check
    and the ``operator observe`` condition can never compute two different
    answers to the same question. A doctor check has no ``Unknown`` state, so
    an ``Unknown`` coverage verdict (the authoritative fold is genuinely
    unreachable -- e.g. the optional skcapstone/skcoord sibling is absent, as
    it always is in CI) fails closed here, exactly like every other doctor
    check fails closed on missing evidence.

    ``kedb_loader`` is forwarded to :func:`compute_kedb_coverage` (tests
    inject a fake so this check is exercisable without the optional sibling
    installed); defaults to the real authoritative-fold reader.
    """
    kwargs = {"kedb_loader": kedb_loader} if kedb_loader is not None else {}
    coverage = compute_kedb_coverage(canon, **kwargs)
    return Check("skbrain:kedb", coverage.status == "True", coverage.reason)


def _check_adapter() -> Check:
    """``skbrain:adapter`` -- the manifest's declared knowledge retriever
    resolves.

    The signed manifest's ``knowledge.retriever`` (a ``module:callable`` ref,
    currently ``skbrain.read_api:build_retriever``) is exactly what
    ATLAS's manifest-driven discovery probes to decide whether SKBrain's RAG
    adapter is available (skcapstone ``operator_seat/discovery.py``,
    ``_default_knowledge_prober``: import the module, ``hasattr`` the
    attribute). This check mirrors that probe locally so a broken or renamed
    retriever ref is a red doctor check on this side, not a silent RAG
    fallback discovered only from ATLAS's side later. The ref is read from the
    manifest itself (never hardcoded here), so a manifest edit can never drift
    silently past this check.
    """
    loader = _pack_loader()
    if loader is None:
        # No skos pack: probe the framework's own retriever entry point.
        ref = "skbrain.read_api:build_retriever"
    else:
        knowledge = loader.load_manifest_dict("skbrain").get("knowledge") or {}
        ref = knowledge.get("retriever")
    if not ref or ":" not in ref:
        return Check(
            "skbrain:adapter", False, f"manifest knowledge.retriever is malformed: {ref!r}"
        )
    mod_name, _, attr = ref.partition(":")
    try:
        mod = importlib.import_module(mod_name)
    except Exception as exc:  # noqa: BLE001 - report class only, never leak a traceback
        return Check(
            "skbrain:adapter",
            False,
            f"retriever module {mod_name!r} unimportable ({type(exc).__name__})",
        )
    if not attr or not hasattr(mod, attr):
        return Check(
            "skbrain:adapter", False, f"retriever attribute {attr!r} missing from {mod_name!r}"
        )
    return Check("skbrain:adapter", True, f"knowledge retriever {ref} resolves")


def _check_cron() -> Check:
    """``skbrain:cron`` -- the pack's fleet CronJob objects are installed and
    match the shipped templates.

    Scope, stated plainly: this verifies the fleet object DECLARATIONS the
    pack's ``fleet_objects`` install step writes (the skos pack effect
    ``fleet_objects``) are present under ``<SKCAPSTONE_HOME>/fleet/
    objects/`` and byte-identical to what this pack ships. It does NOT verify
    a scheduler is actually invoking them on schedule -- that liveness signal
    belongs to the scheduler/watchdog subsystem (``skos.watchdog``), which has
    its own adapter for exactly that. A green ``skbrain:cron`` means "the cron
    is correctly wired," not "the cron definitely fired most recently."
    """
    loader = _pack_loader()
    if loader is None:
        return Check(
            "skbrain:cron", True, "not applicable: the skos pack is not installed (it owns the cron)"
        )
    manifest = loader.load_manifest_dict("skbrain")
    fleet_steps = [
        s for s in manifest.get("install", {}).get("steps", []) if s.get("kind") == "fleet_objects"
    ]
    objects = [str(o) for step in fleet_steps for o in step.get("objects", [])]
    if not objects:
        return Check("skbrain:cron", False, "manifest declares no fleet_objects step")

    source_dir = loader.pack_dir("skbrain")
    installed_dir = _skcapstone_home() / "fleet" / "objects"
    missing: list[str] = []
    stale: list[str] = []
    for rel in objects:
        src = source_dir / rel
        dst = installed_dir / Path(rel).name
        if not dst.is_file():
            missing.append(dst.name)
            continue
        if src.is_file() and src.read_text(encoding="utf-8") != dst.read_text(encoding="utf-8"):
            stale.append(dst.name)

    if not missing and not stale:
        return Check(
            "skbrain:cron", True, f"{len(objects)} fleet cron object(s) installed and current"
        )
    detail_parts = []
    if missing:
        detail_parts.append(f"missing: {', '.join(missing)}")
    if stale:
        detail_parts.append(f"stale (differs from shipped template): {', '.join(stale)}")
    return Check("skbrain:cron", False, "; ".join(detail_parts))


def run_checks(
    *,
    canon: str | Path,
    reader_dsn: str | None,
    connect: Callable[[str], Any] = _connect,
    kedb_loader: Callable[[Path], list[str]] | None = None,
) -> list[Check]:
    """Check content, secret hygiene, KEDB coverage, retriever adapter, fleet
    cron wiring, schema, grants, and projector population -- the full set the
    signed manifest's ``doctor`` install step declares
    (``skos/packs/skbrain/skworld.module.json``)."""
    root = Path(canon).expanduser()
    checks = [
        Check(
            "skbrain:content", root.is_dir(), "canon present" if root.is_dir() else "canon missing"
        )
    ]
    if root.is_dir():
        findings = lint_tree(root)
        checks.append(
            Check(
                "skbrain:secret-lint",
                not findings,
                "clean" if not findings else f"{len(findings)} redacted finding(s)",
            )
        )
    else:
        checks.append(Check("skbrain:secret-lint", False, "content unavailable"))
    # kedb, adapter, and cron are independent of the reader DSN/database, so
    # they run unconditionally (unlike schema/grants/projector below).
    checks.append(_check_kedb(root, kedb_loader=kedb_loader))
    checks.append(_check_pin(root))
    checks.append(_check_adapter())
    checks.append(_check_cron())
    if not reader_dsn:
        checks.extend(
            [
                Check("skbrain:schema", False, "reader DSN missing"),
                Check("skbrain:grants", False, "reader DSN missing"),
                Check("skbrain:projector", False, "reader DSN missing"),
            ]
        )
        return checks
    try:
        with connect(reader_dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('ops.wiki_nodes'), "
                "to_regclass('ops.wiki_chunks'), to_regclass('ops.links')"
            )
            schema = cur.fetchone()
            checks.append(
                Check(
                    "skbrain:schema",
                    bool(schema and all(schema)),
                    "ops relations present" if schema and all(schema) else "ops relations missing",
                )
            )
            cur.execute(
                "SELECT has_schema_privilege(current_user,'ops','USAGE'), "
                "has_table_privilege(current_user,'ops.wiki_nodes','SELECT')"
            )
            grants = cur.fetchone()
            checks.append(
                Check(
                    "skbrain:grants",
                    bool(grants and all(grants)),
                    "reader wall valid" if grants and all(grants) else "reader grants invalid",
                )
            )
            cur.execute(
                "SELECT count(*), EXTRACT(EPOCH FROM (now()-max(updated_at))) FROM ops.wiki_nodes"
            )
            count, age_seconds = cur.fetchone()
            fresh = int(count) > 0 and age_seconds is not None and float(age_seconds) <= 7200
            age = int(age_seconds) if age_seconds is not None else "unknown"
            detail = f"{count} node(s); age_seconds={age}"
            checks.append(Check("skbrain:projector", fresh, detail))
    except Exception as exc:  # do not include DSN or exception repr
        checks.extend(
            [
                Check("skbrain:schema", False, f"database unavailable ({type(exc).__name__})"),
                Check("skbrain:grants", False, "database unavailable"),
                Check("skbrain:projector", False, "database unavailable"),
            ]
        )
    return checks


def checks_json(checks: list[Check]) -> list[dict[str, object]]:
    """Serialize checks without implementation-specific objects."""
    return [asdict(item) for item in checks]
