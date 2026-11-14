"""skbrain sync --commit refuses the wrong estate and the wrong node."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skbrain import cli
from skbrain.cli import app
from skbrain.config import estate_guard, load_config

runner = CliRunner()


class _FakeEmbedder:
    def embed(self, texts):
        return [[0.0] * 1024 for _ in texts]


class FakeBackend:
    """Stands in for PostgresWriterBackend: records that it was opened."""

    opened = 0

    def __init__(self, dsn):
        pass

    def __enter__(self):
        FakeBackend.opened += 1
        return self

    def __exit__(self, *a):
        return None

    def existing_hashes(self):
        return {}

    def upsert_node(self, *a):
        pass

    def delete_node(self, *a):
        pass

    def mark_observed(self, *a):
        pass


def _patch(monkeypatch, hostname="example-1"):
    FakeBackend.opened = 0
    monkeypatch.setattr(cli, "PostgresWriterBackend", FakeBackend)
    monkeypatch.setattr(cli, "dsn_from_env", lambda name: "redacted")
    monkeypatch.setattr(cli, "MxbaiEmbedder", lambda: _FakeEmbedder())
    monkeypatch.setattr("skbrain.config.short_hostname", lambda: hostname)
    monkeypatch.delenv("SKBRAIN_ESTATE", raising=False)


def test_guard_passes_on_matching_estate_and_node(canon: Path):
    cfg = load_config(canon)
    assert estate_guard(cfg, env={"SKBRAIN_ESTATE": "example"}, hostname="example-1") == []


def test_guard_unset_estate_is_not_a_mismatch(canon: Path):
    assert estate_guard(load_config(canon), env={}, hostname="example-1") == []


def test_guard_refuses_estate_mismatch(canon: Path):
    problems = estate_guard(load_config(canon), env={"SKBRAIN_ESTATE": "other"}, hostname="example-1")
    assert len(problems) == 1 and "SKBRAIN_ESTATE" in problems[0]


def test_guard_refuses_node_not_in_projector_nodes(canon: Path):
    problems = estate_guard(load_config(canon), env={}, hostname="stranger-9")
    assert len(problems) == 1 and "projector_nodes" in problems[0]


def test_guard_reports_both_problems(canon: Path):
    assert len(estate_guard(load_config(canon), env={"SKBRAIN_ESTATE": "other"}, hostname="stranger-9")) == 2


def test_sync_commit_refused_on_estate_mismatch(canon: Path, monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setenv("SKBRAIN_ESTATE", "other")
    result = runner.invoke(app, ["sync", "--commit", "--canon", str(canon)])
    assert result.exit_code == 2
    assert "refusing" in result.output
    assert FakeBackend.opened == 0, "a refused projection must never touch the database"


def test_sync_commit_refused_on_wrong_node(canon: Path, monkeypatch):
    _patch(monkeypatch, hostname="stranger-9")
    result = runner.invoke(app, ["sync", "--commit", "--canon", str(canon)])
    assert result.exit_code == 2
    assert "projector_nodes" in result.output
    assert FakeBackend.opened == 0


def test_sync_commit_allowed_on_matching_node_and_estate(canon: Path, monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setenv("SKBRAIN_ESTATE", "example")
    result = runner.invoke(app, ["sync", "--commit", "--canon", str(canon)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout.strip().splitlines()[-1])["committed"] is True


def test_dry_run_is_still_allowed_on_a_non_projector_node(canon: Path, monkeypatch):
    _patch(monkeypatch, hostname="stranger-9")
    monkeypatch.setenv("SKBRAIN_ESTATE", "other")
    result = runner.invoke(app, ["sync", "--canon", str(canon)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout.strip().splitlines()[-1])["committed"] is False


def test_canon_without_config_warns_and_keeps_legacy_behaviour(tmp_path: Path, monkeypatch):
    _patch(monkeypatch, hostname="anything")
    (tmp_path / "pages").mkdir()
    result = runner.invoke(app, ["sync", "--commit", "--canon", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "no skbrain.yaml" in result.output


def test_invalid_config_blocks_sync(canon: Path, monkeypatch):
    _patch(monkeypatch)
    (canon / "skbrain.yaml").write_text("schema: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["sync", "--canon", str(canon)])
    assert result.exit_code == 2
    assert FakeBackend.opened == 0


def test_sync_without_any_canon_fails_closed(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.delenv("SKBRAIN_CANON", raising=False)
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 2
    assert "SKBRAIN_CANON" in result.output
    assert FakeBackend.opened == 0


def test_lint_and_doctor_also_have_no_default_canon(monkeypatch):
    monkeypatch.delenv("SKBRAIN_CANON", raising=False)
    assert runner.invoke(app, ["lint"]).exit_code == 2
    assert runner.invoke(app, ["doctor"]).exit_code == 2
