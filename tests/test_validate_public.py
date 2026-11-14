"""scripts/validate_public.py: the scrub check for the public repo (design 8.4)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_public.py"
spec = importlib.util.spec_from_file_location("validate_public", SCRIPT)
vp = importlib.util.module_from_spec(spec)
sys.modules["validate_public"] = vp
spec.loader.exec_module(vp)


def rules(text: str, denylist=None) -> list[str]:
    return vp.scan_text(text, "f.md", denylist)


def u(text: str) -> str:
    """Spell dots as ~ and colons as ^ so this file never contains the forbidden text itself."""
    return text.replace("~", ".").replace("^", ":")


@pytest.mark.parametrize(
    "text, needle",
    [
        (u("connect to 10~1~2~3 now"), "IPv4"),
        (u("addr 100~101~102~103"), "tailnet"),
        (u("addr fe80^0^0^0^1^2^3^4"), "IPv6"),
        (u("see https^//internal~corp~net/path"), "domain"),
        (u("host box~internal~lan"), "domain"),
        ("path /home" + "/someone/work", "home directory"),
        ("see " + "skbrain-ops-" + "acme", "estate-named repo"),
        ("a " + chr(0x2014) + " b", "dash"),
        ("a " + chr(0x2013) + " b", "dash"),
    ],
)
def test_forbidden_content_is_flagged(text, needle):
    assert any(needle in f for f in rules(text)), rules(text)


@pytest.mark.parametrize(
    "text",
    [
        "bind 127.0.0.1:5432",
        "docs range 192.0.2.10",
        "https://example.org/x and forge.example.org",
        "https://github.com/smilinTux/skbrain",
        "repo skbrain-ops-<estate> and skbrain-ops-example",
        "version 1.0.0 and 5-10 and a - b",
        "http://localhost:11434/api/embed",
        "path /home/<user>/x",
        "time 12:05:00",
    ],
)
def test_allowed_content_is_not_flagged(text):
    assert rules(text) == []


def test_denylist_term_is_flagged_as_a_whole_word(tmp_path: Path):
    deny = tmp_path / "deny.txt"
    deny.write_text("# private\nsecretnode\n", encoding="utf-8")
    patterns = vp.load_denylist(deny)
    assert any("denylisted" in f for f in rules("runs on SecretNode today", patterns))
    assert rules("secretnodes are fine as a different word", patterns) == []


def test_repo_tree_is_clean():
    assert vp.scan(SCRIPT.parents[1]) == []


def _run(args, env=None, cwd=None):
    import os

    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], **(env or {})},
        cwd=cwd,
    )


def test_release_run_without_denylist_fails_closed(tmp_path: Path):
    (tmp_path / "a.md").write_text("clean\n", encoding="utf-8")
    result = _run([str(tmp_path)], env={"SKBRAIN_SCRUB_RELEASE": "1"})
    assert result.returncode == 2
    assert "denylist" in result.stderr


def test_release_run_with_denylist_passes_a_clean_tree(tmp_path: Path):
    (tmp_path / "a.md").write_text("clean\n", encoding="utf-8")
    deny = tmp_path.parent / (tmp_path.name + "-deny.txt")
    deny.write_text("secretnode\n", encoding="utf-8")
    result = _run([str(tmp_path), "--denylist", str(deny)], env={"SKBRAIN_SCRUB_RELEASE": "1"})
    assert result.returncode == 0, result.stderr


def test_denylist_from_environment(tmp_path: Path):
    (tmp_path / "a.md").write_text("runs on secretnode\n", encoding="utf-8")
    deny = tmp_path.parent / (tmp_path.name + "-deny.txt")
    deny.write_text("secretnode\n", encoding="utf-8")
    result = _run([str(tmp_path)], env={"SKBRAIN_SCRUB_DENYLIST": str(deny)})
    assert result.returncode == 1
    assert "denylisted" in result.stdout


def test_empty_or_missing_denylist_fails_closed(tmp_path: Path):
    (tmp_path / "a.md").write_text("clean\n", encoding="utf-8")
    empty = tmp_path.parent / (tmp_path.name + "-empty.txt")
    empty.write_text("# nothing\n", encoding="utf-8")
    assert _run([str(tmp_path), "--denylist", str(empty)]).returncode == 2
    assert _run([str(tmp_path), "--denylist", str(tmp_path / "missing.txt")]).returncode == 2


def test_dirty_tree_exits_one(tmp_path: Path):
    (tmp_path / "a.md").write_text(u("host 10~9~8~7\n"), encoding="utf-8")
    assert _run([str(tmp_path)]).returncode == 1
