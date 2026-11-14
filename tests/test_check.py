"""skbrain check: the hermetic CI check (design 3.4). No DSN, no network."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skbrain.check import ERROR, WARNING, run_check
from skbrain.cli import app

runner = CliRunner(mix_stderr=False)


def codes(report, severity=None):
    return sorted(f.code for f in report.findings if severity is None or f.severity == severity)


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, (path, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_template_canon_is_clean(canon: Path):
    report = run_check(canon)
    assert report.ok, report.findings
    assert report.findings == []
    assert report.pages == 9


def test_check_makes_no_database_or_network_use(canon: Path, monkeypatch):
    for var in ("SKBRAIN_PG_READER_DSN", "SKBRAIN_PG_PROJECTOR_DSN", "SKBRAIN_ESTATE", "SKBRAIN_CANON"):
        monkeypatch.delenv(var, raising=False)
    import socket

    def no_network(*a, **k):
        raise AssertionError("skbrain check must not open a socket")

    monkeypatch.setattr(socket, "socket", no_network)
    assert run_check(canon).ok


# 1. secret lint ----------------------------------------------------------


def test_secret_in_a_page_fails(canon: Path):
    page = canon / "pages" / "services" / "service-widget.md"
    page.write_text(page.read_text() + "\npassword=hunter2hunter2\n", encoding="utf-8")
    report = run_check(canon)
    assert "secret" in codes(report, ERROR)


def test_framework_submodule_docs_are_not_secret_linted(canon: Path):
    (canon / "framework" / "docs").mkdir(parents=True)
    (canon / "framework" / "docs" / "EXAMPLE.md").write_text("password=exampleexample1\n", encoding="utf-8")
    assert run_check(canon).ok


# 2. parse only pages/ -----------------------------------------------------


def test_sop_and_other_documents_do_not_fail_the_parse(canon: Path):
    # The instance already carries SOP.md, README.md, AGENTS.md: none has front matter.
    assert (canon / "SOP.md").is_file()
    assert "parse" not in codes(run_check(canon))


def test_malformed_page_is_a_parse_error(canon: Path):
    (canon / "pages" / "services" / "service-broken.md").write_text("no front matter\n", encoding="utf-8")
    assert "parse" in codes(run_check(canon), ERROR)


def test_missing_pages_dir_is_an_error(tmp_path: Path, canon: Path):
    import shutil

    shutil.rmtree(canon / "pages")
    assert "pages" in codes(run_check(canon), ERROR)


# 3. front matter ----------------------------------------------------------


def test_unknown_page_type_fails_schema(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "type: service", "type: gadget")
    assert "frontmatter" in codes(run_check(canon), ERROR)


def test_unknown_front_matter_field_fails(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "namespace: ops", "namespace: ops\nrecurrence: 3")
    assert "frontmatter" in codes(run_check(canon), ERROR)


def test_bad_edge_type_fails(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "type: runs_on", "type: affects")
    assert "frontmatter" in codes(run_check(canon), ERROR)


def test_lesson_validates_against_vendored_skrsi_schema(canon: Path):
    page = canon / "pages" / "lessons" / "lesson-alert-on-stale-heartbeat.md"
    _edit(page, "status: proposed", "status: proposed\nrecurrence: 4")  # lesson-v1 forbids it
    report = run_check(canon)
    assert any(f.code == "frontmatter" and "lesson-v1" in f.message for f in report.findings)


def test_lesson_with_origin_field_fails(canon: Path):
    _edit(canon / "pages" / "lessons" / "lesson-alert-on-stale-heartbeat.md", "status: proposed", "status: proposed\norigin: git")
    assert "frontmatter" in codes(run_check(canon), ERROR)


def test_lesson_tag_outside_vocabulary_fails(canon: Path):
    _edit(canon / "pages" / "lessons" / "lesson-alert-on-stale-heartbeat.md", "tags: [job-failure-streak]", "tags: [made-up-tag]")
    assert "lesson-tag" in codes(run_check(canon), ERROR)


def test_lesson_tags_on_other_pages_must_be_vocabulary_keys(canon: Path):
    _edit(canon / "pages" / "postmortems" / "postmortem-2026-01-15-widget-wedge.md", "lesson_tags: [job-failure-streak]", "lesson_tags: [token-budget]")
    report = run_check(canon)
    assert "lesson-tag" in codes(report, ERROR)


def test_free_tags_stay_free_on_non_lesson_pages(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "tags: [widget, example]", "tags: [anything-goes, whatever]")
    assert run_check(canon).ok


def test_vendored_skrsi_tag_is_recorded():
    from skbrain.check import skrsi_tag

    assert skrsi_tag().startswith("skrsi-v")


# 4. slug and links --------------------------------------------------------


def test_id_must_equal_filename_stem(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "id: service-widget", "id: service-other")
    assert "parse" in codes(run_check(canon), ERROR)


def test_duplicate_slug_across_directories_fails(canon: Path):
    import shutil

    shutil.copy(canon / "pages" / "services" / "service-widget.md", canon / "pages" / "cis" / "service-widget.md")
    assert "duplicate-slug" in codes(run_check(canon), ERROR)


def test_wikilink_with_a_path_fails(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "[[node-example-1]]", "[[nodes/node-example-1]]")
    assert "wikilink-not-bare" in codes(run_check(canon), ERROR)


def test_wikilink_with_a_title_fails(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "[[node-example-1]]", "[[Example One]]")
    assert "wikilink-not-bare" in codes(run_check(canon), ERROR)


def test_dangling_link_is_reported_not_failed(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "[[node-example-1]]", "[[node-example-9]]")
    report = run_check(canon)
    assert report.ok
    assert "dangling-link" in codes(report, WARNING)


# 5. dashes ----------------------------------------------------------------


def test_em_dash_in_any_markdown_fails(canon: Path):
    (canon / "log.md").write_text("# Log\n\nA " + chr(0x2014) + " B\n", encoding="utf-8")
    report = run_check(canon)
    assert "dash" in codes(report, ERROR)
    assert any(f.path == "log.md" for f in report.findings)


def test_en_dash_in_a_page_fails(canon: Path):
    page = canon / "pages" / "services" / "service-widget.md"
    page.write_text(page.read_text() + "\nrange 5" + chr(0x2013) + "10\n", encoding="utf-8")
    assert "dash" in codes(run_check(canon), ERROR)


def test_hyphen_is_fine(canon: Path):
    page = canon / "pages" / "services" / "service-widget.md"
    page.write_text(page.read_text() + "\nrange 5-10, and a - b\n", encoding="utf-8")
    assert run_check(canon).ok


# 6. estate guard ----------------------------------------------------------


def test_repo_name_must_end_with_the_estate(tmp_path: Path, canon: Path):
    wrong = tmp_path / ("skbrain-ops-" + "other")
    canon.rename(wrong)
    assert "estate-repo-name" in codes(run_check(wrong), ERROR)


def test_repo_name_override_for_ci_checkouts(tmp_path: Path, canon: Path):
    wrong = tmp_path / "workspace"
    canon.rename(wrong)
    assert "estate-repo-name" in codes(run_check(wrong), ERROR)
    assert run_check(wrong, repo_name="skbrain-ops-example").ok


def test_evidence_ref_from_another_estate_fails(canon: Path):
    _edit(
        canon / "pages" / "postmortems" / "postmortem-2026-01-15-widget-wedge.md",
        "skrsi-config-example@a1b2c3d",
        "skrsi-config-" + "other@a1b2c3d",
    )
    report = run_check(canon)
    assert "evidence-wrong-instance" in codes(report, ERROR)


def test_evidence_ref_must_be_commit_pinned(canon: Path):
    _edit(
        canon / "pages" / "postmortems" / "postmortem-2026-01-15-widget-wedge.md",
        "skrsi-config-example@a1b2c3d:",
        "skrsi-config-example@main:",
    )
    assert "evidence-not-pinned" in codes(run_check(canon), ERROR)


def test_node_outside_the_estate_list_is_a_warning_only(canon: Path):
    _edit(canon / "pages" / "services" / "service-widget.md", "[[node-example-1]]", "[[node-example-1]] and [[node-elsewhere-7]]")
    report = run_check(canon)
    assert report.ok
    assert "node-outside-estate" in codes(report, WARNING)


def test_node_guard_is_off_without_a_nodes_list(canon: Path):
    _edit(canon / "skbrain.yaml", "nodes: [node-example-1, node-example-2]\n", "")
    _edit(canon / "pages" / "services" / "service-widget.md", "[[node-example-1]]", "[[node-example-1]] and [[node-elsewhere-7]]")
    assert "node-outside-estate" not in codes(run_check(canon))


def test_writer_reviewer_overlap_warns(canon: Path):
    _edit(canon / "skbrain.yaml", "reviewers: [example-review-bot]", "reviewers: [example-writer-bot]")
    assert "writer-reviewer-overlap" in codes(run_check(canon), WARNING)


def test_missing_config_fails(canon: Path):
    (canon / "skbrain.yaml").unlink()
    assert "config" in codes(run_check(canon), ERROR)


def test_invalid_config_fails(canon: Path):
    _edit(canon / "skbrain.yaml", "namespace: ops", "namespace: ops\nsurprise: 1")
    assert "config" in codes(run_check(canon), ERROR)


# 7. index -----------------------------------------------------------------


def test_page_missing_from_index_warns(canon: Path):
    _edit(canon / "index.md", "- [[node-example-2]]\n", "")
    report = run_check(canon)
    assert report.ok
    assert "index-unlisted" in codes(report, WARNING)


def test_missing_index_warns(canon: Path):
    (canon / "index.md").unlink()
    assert "index-missing" in codes(run_check(canon), WARNING)


# CLI ----------------------------------------------------------------------


def test_cli_check_exit_zero_and_json(canon: Path):
    result = runner.invoke(app, ["check", "--canon", str(canon)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True and payload["errors"] == 0


def test_cli_check_exit_one_on_error(canon: Path):
    (canon / "log.md").write_text("bad " + chr(0x2014) + " dash\n", encoding="utf-8")
    result = runner.invoke(app, ["check", "--canon", str(canon)])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"] >= 1


def test_cli_check_has_no_default_canon(monkeypatch):
    monkeypatch.delenv("SKBRAIN_CANON", raising=False)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 2
    assert "SKBRAIN_CANON" in result.stderr


def test_cli_check_reads_skbrain_canon_env(canon: Path, monkeypatch):
    monkeypatch.setenv("SKBRAIN_CANON", str(canon))
    assert runner.invoke(app, ["check"]).exit_code == 0
