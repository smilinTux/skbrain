"""walk_pages parses ONLY files under pages/."""

from __future__ import annotations

from pathlib import Path

import pytest

from skbrain.parser import walk_pages


def _page(slug: str) -> str:
    return f"---\nid: {slug}\ntype: node\nnamespace: ops\ntitle: T\n---\nbody\n"


def test_documents_outside_pages_are_never_parsed(tmp_path: Path):
    (tmp_path / "pages" / "nodes").mkdir(parents=True)
    (tmp_path / "pages" / "nodes" / "node-a.md").write_text(_page("node-a"), encoding="utf-8")
    # None of these has front matter; parsing any of them would raise.
    for name in ("SOP.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "README.md", "notes.md"):
        (tmp_path / name).write_text("# plain document\n", encoding="utf-8")
    assert [p.slug for p in walk_pages(tmp_path)] == ["node-a"]


def test_framework_submodule_docs_are_not_parsed(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "node-a.md").write_text(_page("node-a"), encoding="utf-8")
    (tmp_path / "framework" / "docs").mkdir(parents=True)
    (tmp_path / "framework" / "docs" / "SCHEMA.md").write_text("# no front matter\n", encoding="utf-8")
    assert [p.slug for p in walk_pages(tmp_path)] == ["node-a"]


def test_underscore_files_in_pages_are_skipped(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "_index.md").write_text("# nav\n", encoding="utf-8")
    (tmp_path / "pages" / "node-a.md").write_text(_page("node-a"), encoding="utf-8")
    assert [p.slug for p in walk_pages(tmp_path)] == ["node-a"]


def test_malformed_page_inside_pages_still_raises_loudly(tmp_path: Path):
    from skbrain.parser import OpsParseError

    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "bad.md").write_text("# no front matter\n", encoding="utf-8")
    with pytest.raises(OpsParseError):
        walk_pages(tmp_path)


def test_canon_without_pages_dir_fails_closed(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="pages"):
        walk_pages(tmp_path)
