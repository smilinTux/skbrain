"""skbrain.yaml loading and validation, and canon resolution (no default)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from skbrain.config import (
    CanonNotSetError,
    ConfigError,
    load_config,
    parse_config,
    resolve_canon,
)

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO / "schemas" / "skbrain-instance-v1.schema.json").read_text())

GOOD = {
    "schema": "skbrain.instance.v1",
    "estate": "example",
    "namespace": "ops",
    "framework": "skbrain-v1.0.1",
    "forge": "forge.example.org",
    "projector_nodes": ["example-1"],
    "skrsi": {"instance": "example-org/skrsi-config-example"},
    "writers": ["w-bot"],
    "reviewers": ["r-bot"],
}


def _with(**over):
    data = dict(GOOD)
    data.update(over)
    return data


def test_load_config_happy_path(canon: Path):
    cfg = load_config(canon)
    assert cfg.estate == "example"
    assert cfg.framework == "skbrain-v1.0.1"
    assert cfg.framework_version == "1.0.1"
    assert cfg.projector_nodes == ("example-1",)
    assert cfg.skrsi_instance == "example-org/skrsi-config-example"
    assert cfg.repo_name == "skbrain-ops-example"
    assert cfg.nodes == ("node-example-1", "node-example-2")


def test_nodes_is_optional():
    assert parse_config(GOOD).nodes is None


def test_unknown_field_fails():
    with pytest.raises(ConfigError, match="unknown field"):
        parse_config(_with(extra="x"))


def test_unknown_field_under_skrsi_fails():
    with pytest.raises(ConfigError, match="unknown field"):
        parse_config(_with(skrsi={"instance": "a/b", "token": "x"}))


@pytest.mark.parametrize("field", list(GOOD))
def test_missing_required_field_fails(field):
    data = dict(GOOD)
    del data[field]
    with pytest.raises(ConfigError, match="missing required"):
        parse_config(data)


@pytest.mark.parametrize(
    "over",
    [
        {"schema": "skbrain.instance.v2"},
        {"estate": "Not-Ok"},
        {"namespace": "other"},
        {"framework": "1.0.0"},
        {"framework": "skbrain-v1.0"},
        {"forge": "https://forge.example.org"},
        {"projector_nodes": []},
        {"projector_nodes": ["bad host"]},
        {"skrsi": {"instance": "no-owner"}},
        {"writers": "w-bot"},
        {"nodes": ["not-a-node-slug"]},
    ],
)
def test_invalid_values_fail(over):
    with pytest.raises(ConfigError):
        parse_config(_with(**over))


def test_missing_file_is_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)


def test_invalid_yaml_is_config_error(tmp_path: Path):
    (tmp_path / "skbrain.yaml").write_text(": bad: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML"):
        load_config(tmp_path)


def test_python_validator_and_json_schema_agree():
    """The schema file and config.py must accept and reject the same documents."""
    validator = Draft202012Validator(SCHEMA)
    cases = [GOOD, _with(extra="x"), _with(estate="Bad"), _with(framework="v1"), _with(nodes=["node-a"]),
             _with(projector_nodes=[]), _with(skrsi={"instance": "bad"}), _with(namespace="x")]
    for case in cases:
        schema_ok = not list(validator.iter_errors(case))
        try:
            parse_config(case)
            py_ok = True
        except ConfigError:
            py_ok = False
        assert schema_ok == py_ok, case


def test_template_skbrain_yaml_matches_schema(canon: Path):
    data = yaml.safe_load((canon / "skbrain.yaml").read_text())
    assert not list(Draft202012Validator(SCHEMA).iter_errors(data))


# --- canon resolution: no estate default -----------------------------------


def test_resolve_canon_argument_wins_over_env():
    assert resolve_canon("/a/b", env={"SKBRAIN_CANON": "/c/d"}) == Path("/a/b")


def test_resolve_canon_from_env():
    assert resolve_canon(None, env={"SKBRAIN_CANON": "/c/d"}) == Path("/c/d")


def test_resolve_canon_has_no_default():
    with pytest.raises(CanonNotSetError, match="SKBRAIN_CANON"):
        resolve_canon(None, env={})


def test_resolve_canon_blank_env_is_unset():
    with pytest.raises(CanonNotSetError):
        resolve_canon(None, env={"SKBRAIN_CANON": "  "})
