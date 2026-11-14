"""doctor skbrain:pin: installed version == skbrain.yaml framework == submodule tag."""

from __future__ import annotations

import subprocess
from pathlib import Path

from skbrain.doctor import _check_pin, _installed_version, _submodule_tag


def test_pin_ok_without_submodule(canon: Path):
    check = _check_pin(canon, installed="1.0.0")
    assert check.name == "skbrain:pin" and check.ok, check.detail


def test_pin_fails_when_installed_version_differs(canon: Path):
    check = _check_pin(canon, installed="1.0.1")
    assert not check.ok
    assert "1.0.1" in check.detail and "skbrain-v1.0.0" in check.detail


def test_pin_fails_when_version_unknown(canon: Path, monkeypatch):
    monkeypatch.setattr("skbrain.doctor._installed_version", lambda: None)
    check = _check_pin(canon)
    assert not check.ok and "unknown" in check.detail


def test_installed_version_matches_package_metadata():
    assert _installed_version() == "1.0.0"


def test_pin_ok_when_submodule_tag_matches(canon: Path):
    (canon / "framework").mkdir()
    assert _check_pin(canon, installed="1.0.0", submodule_tag="skbrain-v1.0.0").ok


def test_pin_fails_when_submodule_tag_differs(canon: Path):
    (canon / "framework").mkdir()
    check = _check_pin(canon, installed="1.0.0", submodule_tag="skbrain-v0.9.0")
    assert not check.ok and "skbrain-v0.9.0" in check.detail


def test_pin_fails_when_submodule_has_no_release_tag(canon: Path):
    (canon / "framework").mkdir()
    check = _check_pin(canon, installed="1.0.0", submodule_tag=None)
    # None means "ask git"; an empty fake dir answers "no tag".
    assert not check.ok


def test_pin_legacy_canon_without_config_is_not_enforced(tmp_path: Path):
    check = _check_pin(tmp_path, installed="1.0.0")
    assert check.ok and "legacy" in check.detail


def test_pin_invalid_config_fails(canon: Path):
    (canon / "skbrain.yaml").write_text("schema: nope\n", encoding="utf-8")
    assert not _check_pin(canon, installed="1.0.0").ok


def test_submodule_tag_reads_a_real_git_tag(tmp_path: Path):
    repo = tmp_path / "framework"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org", "PATH": "/usr/bin:/bin"}
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"], ["tag", "skbrain-v1.0.0"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True)
    assert _submodule_tag(repo) == "skbrain-v1.0.0"


def test_submodule_tag_falls_back_to_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "skbrain"\nversion = "1.2.3"\n', encoding="utf-8")
    assert _submodule_tag(tmp_path) == "skbrain-v1.2.3"


def test_run_checks_includes_the_pin_check(canon: Path):
    from skbrain.doctor import run_checks

    names = {c.name for c in run_checks(canon=canon, reader_dsn=None, kedb_loader=lambda h: [])}
    assert "skbrain:pin" in names
