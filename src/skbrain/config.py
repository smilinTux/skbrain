"""skbrain.config - the instance config (``skbrain.yaml``) and the canon guards.

Every estate canon repo (``skbrain-ops-<estate>``) carries one ``skbrain.yaml``
at its root. This module loads and validates it (schema ``skbrain.instance.v1``,
unknown fields fail), resolves WHICH canon a command works on (no default: fail
closed), and implements the guards that keep one estate's canon out of another
estate's projection.

``schemas/skbrain-instance-v1.schema.json`` documents the same shape;
``tests/test_config.py`` checks the two agree.
"""

from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE = "skbrain.yaml"
SCHEMA_ID = "skbrain.instance.v1"
FRAMEWORK_PREFIX = "skbrain-v"

#: Every key a v1 ``skbrain.yaml`` may carry. Anything else is an error.
REQUIRED_FIELDS = (
    "schema",
    "estate",
    "namespace",
    "framework",
    "forge",
    "projector_nodes",
    "skrsi",
    "writers",
    "reviewers",
)
OPTIONAL_FIELDS = ("nodes",)

_ESTATE_RE = re.compile(r"^[a-z][a-z0-9]{0,31}$")
_FRAMEWORK_RE = re.compile(r"^skbrain-v[0-9]+\.[0-9]+\.[0-9]+$")
_FORGE_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?$")
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_SKRSI_INSTANCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_NODE_SLUG_RE = re.compile(r"^node-[a-z0-9][a-z0-9-]*$")


class ConfigError(ValueError):
    """The instance config is missing, malformed, or fails validation."""


class CanonNotSetError(ConfigError):
    """No canon was named: ``--canon`` and ``SKBRAIN_CANON`` are both unset."""


@dataclass(frozen=True)
class InstanceConfig:
    """A validated ``skbrain.yaml``."""

    schema: str
    estate: str
    namespace: str
    framework: str
    forge: str
    projector_nodes: tuple[str, ...]
    skrsi_instance: str
    writers: tuple[str, ...]
    reviewers: tuple[str, ...]
    nodes: tuple[str, ...] | None = None

    @property
    def framework_version(self) -> str:
        """The pinned version without the ``skbrain-v`` prefix."""
        return self.framework[len(FRAMEWORK_PREFIX) :]

    @property
    def repo_name(self) -> str:
        """The repo name this estate's canon must carry."""
        return f"skbrain-ops-{self.estate}"


def resolve_canon(canon: Path | str | None = None, *, env: dict[str, str] | None = None) -> Path:
    """Return the canon root to work on. There is NO default.

    Order: the explicit *canon* argument (``--canon``), then ``SKBRAIN_CANON``.
    Any estate default here would let a node project, or lint, the wrong
    estate's canon, so the absence of both is an error.

    Raises:
        CanonNotSetError: neither is set (or both are blank).
    """
    environ = os.environ if env is None else env
    chosen = str(canon).strip() if canon is not None else ""
    if not chosen:
        chosen = environ.get("SKBRAIN_CANON", "").strip()
    if not chosen:
        raise CanonNotSetError(
            "no canon selected: pass --canon PATH or set SKBRAIN_CANON "
            "(skbrain has no default canon on purpose, so it can never "
            "work on the wrong estate)"
        )
    return Path(chosen).expanduser()


def config_path(canon: Path | str) -> Path:
    """Where the instance config of *canon* lives."""
    return Path(canon) / CONFIG_FILE


def has_config(canon: Path | str) -> bool:
    """True when *canon* carries a ``skbrain.yaml``."""
    return config_path(canon).is_file()


def _str_list(raw: Any, name: str, *, item_re: re.Pattern[str] | None, min_items: int) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ConfigError(f"{name} must be a list")
    if len(raw) < min_items:
        raise ConfigError(f"{name} must have at least {min_items} item(s)")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{name} entries must be non-empty strings")
        if item_re is not None and not item_re.match(item):
            raise ConfigError(f"{name} entry {item!r} is not valid")
        out.append(item)
    if len(set(out)) != len(out):
        raise ConfigError(f"{name} has duplicate entries")
    return tuple(out)


def parse_config(data: Any) -> InstanceConfig:
    """Validate an already-loaded ``skbrain.yaml`` mapping.

    Raises:
        ConfigError: on any missing, unknown or invalid field.
    """
    if not isinstance(data, dict):
        raise ConfigError("skbrain.yaml must be a YAML mapping")
    unknown = sorted(set(data) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        raise ConfigError(f"unknown field(s): {', '.join(str(u) for u in unknown)}")
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise ConfigError(f"missing required field(s): {', '.join(missing)}")

    if data["schema"] != SCHEMA_ID:
        raise ConfigError(f"schema must be {SCHEMA_ID!r}, got {data['schema']!r}")
    estate = data["estate"]
    if not isinstance(estate, str) or not _ESTATE_RE.match(estate):
        raise ConfigError("estate must be a short lowercase name (letters and digits)")
    if data["namespace"] != "ops":
        raise ConfigError("namespace must be 'ops'")
    framework = data["framework"]
    if not isinstance(framework, str) or not _FRAMEWORK_RE.match(framework):
        raise ConfigError("framework must look like skbrain-v1.2.3")
    forge = data["forge"]
    if not isinstance(forge, str) or not _FORGE_RE.match(forge):
        raise ConfigError("forge must be a host (optionally host:port), no scheme or path")
    projector_nodes = _str_list(
        data["projector_nodes"], "projector_nodes", item_re=_HOST_RE, min_items=1
    )

    skrsi = data["skrsi"]
    if not isinstance(skrsi, dict):
        raise ConfigError("skrsi must be a mapping with an 'instance' key")
    extra = sorted(set(skrsi) - {"instance"})
    if extra:
        raise ConfigError(f"unknown field(s) under skrsi: {', '.join(str(e) for e in extra)}")
    instance = skrsi.get("instance")
    if not isinstance(instance, str) or not _SKRSI_INSTANCE_RE.match(instance):
        raise ConfigError("skrsi.instance must look like owner/name")

    writers = _str_list(data["writers"], "writers", item_re=None, min_items=0)
    reviewers = _str_list(data["reviewers"], "reviewers", item_re=None, min_items=0)
    nodes = None
    if "nodes" in data:
        nodes = _str_list(data["nodes"], "nodes", item_re=_NODE_SLUG_RE, min_items=0)

    return InstanceConfig(
        schema=data["schema"],
        estate=estate,
        namespace=data["namespace"],
        framework=framework,
        forge=forge,
        projector_nodes=projector_nodes,
        skrsi_instance=instance,
        writers=writers,
        reviewers=reviewers,
        nodes=nodes,
    )


def load_config(canon: Path | str) -> InstanceConfig:
    """Load and validate ``<canon>/skbrain.yaml``.

    Raises:
        FileNotFoundError: the canon has no ``skbrain.yaml``.
        ConfigError: the file is not valid YAML or fails validation.
    """
    path = config_path(canon)
    if not path.is_file():
        raise FileNotFoundError(f"{CONFIG_FILE} not found in {canon}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{CONFIG_FILE} is not valid YAML: {exc}") from exc
    return parse_config(data)


def short_hostname() -> str:
    """This node's short hostname (the part before the first dot)."""
    return socket.gethostname().split(".", 1)[0]


def estate_guard(
    cfg: InstanceConfig,
    *,
    env: dict[str, str] | None = None,
    hostname: str | None = None,
) -> list[str]:
    """Return the reasons a committed projection of this canon must be refused.

    Two independent walls, both must hold:

    * ``SKBRAIN_ESTATE`` (the node's declared estate), when set, must equal the
      canon's ``estate``. An unset variable is not a mismatch: nodes that have
      not declared an estate keep working, and the node wall below still holds.
    * the node's short hostname must be one of ``projector_nodes``.

    An empty list means the projection may proceed.
    """
    environ = os.environ if env is None else env
    problems: list[str] = []
    declared = environ.get("SKBRAIN_ESTATE", "").strip()
    if declared and declared != cfg.estate:
        problems.append(
            f"SKBRAIN_ESTATE={declared!r} but this canon belongs to estate {cfg.estate!r}"
        )
    host = hostname if hostname is not None else short_hostname()
    if host not in cfg.projector_nodes:
        problems.append(
            f"node {host!r} is not in projector_nodes {list(cfg.projector_nodes)} of this canon"
        )
    return problems
