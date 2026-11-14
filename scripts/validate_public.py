#!/usr/bin/env python3
"""Scrub check for the PUBLIC skbrain framework repo (design section 8.4).

Fails when the tree contains anything that belongs to an estate instead of the
framework: IP addresses, domains other than the example ones (plus a short
allowlist of public documentation hosts), home directory paths, tailnet
addresses, estate-named repos, em or en dashes, and any term from a private
denylist.

The denylist is a plain text file (one term per line, ``#`` comments, matched
case-insensitively) kept OUTSIDE this repo, so the list of private names is
never itself published. Pass it with ``--denylist PATH`` or the environment
variable ``SKBRAIN_SCRUB_DENYLIST``.

Release runs set ``SKBRAIN_SCRUB_RELEASE=1``. A release run with no denylist
(or an empty or unreadable one) FAILS CLOSED, exit 2: a green result without
the private check would certify less than it appears to.

Exit codes: 0 clean, 1 findings, 2 usage or fail-closed error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build"}
TEXT_SUFFIXES = {
    ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".txt", ".cfg", ".ini", ".sql", "",
}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".gif", ".whl", ".gz", ".zip"}

#: Documentation hosts a public repo may link to. Everything else fails.
ALLOWED_DOMAINS = {
    "example.org", "example.test", "example.com",
    "github.com", "raw.githubusercontent.com", "smilintux.github.io",
    "json-schema.org", "keepachangelog.com", "semver.org", "www.apache.org", "apache.org",
    "www.contributor-covenant.org", "contributor-covenant.org", "pypi.org", "mermaid.js.org",
    "docs.python.org", "peps.python.org",
}
#: Loopback and documentation ranges (RFC 5737) are not estate addresses.
ALLOWED_IPV4 = re.compile(r"^(127\.\d+\.\d+\.\d+|0\.0\.0\.0|192\.0\.2\.\d+|198\.51\.100\.\d+|203\.0\.113\.\d+)$")

_IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.]*\w)")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}:){4,7}[0-9a-fA-F]{1,4}(?![\w:])|(?<![\w:])(?:[0-9a-fA-F]{1,4}:){1,6}:(?:[0-9a-fA-F]{1,4})?(?![\w:])")
_TAILNET = re.compile(r"(?<![\w.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}(?![\w.]*\w)")
_DOMAIN = re.compile(
    r"(?<![\w@/.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:com|org|net|io|it|dev|cloud|local|lan|internal|us|info|xyz|ai|ts\.net))(?![\w-])",
    re.IGNORECASE,
)
_URL_HOST = re.compile(r"https?://([A-Za-z0-9.-]+)")
_HOME = re.compile(r"(?:/home/[a-z_][a-z0-9_.-]*|/Users/[A-Za-z_][\w.-]*|[A-Za-z]:\\Users\\)")
_ESTATE_REPO = re.compile(r"\b(?:skbrain-ops|skrsi-config)-(?!example\b|template\b|<)[a-z][a-z0-9]*\b")
_DASHES = (chr(0x2013), chr(0x2014))


def load_denylist(path: Path) -> list[re.Pattern[str]]:
    """Read the private denylist: one term per line, ``#`` comments, case-insensitive."""
    terms = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        term = raw.split("#", 1)[0].strip()
        if term:
            terms.append(re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE))
    return terms


def scan_text(text: str, name: str, denylist: list[re.Pattern[str]] | None = None) -> list[str]:
    """Return ``name:line: rule`` findings for one file's text."""
    out: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in _IPV4.finditer(line):
            ip = m.group(1)
            if all(0 <= int(p) <= 255 for p in ip.split(".")) and not ALLOWED_IPV4.match(ip):
                rule = "tailnet address (100.64/10)" if _TAILNET.search(ip) else "IPv4 address"
                out.append(f"{name}:{n}: {rule} {ip}")
        for m in _IPV6.finditer(line):
            out.append(f"{name}:{n}: IPv6 address {m.group(0)}")
        # A URL host with no dot (localhost, a bare test name) is not a public domain.
        hosts = {h.lower().rstrip(".") for h in _URL_HOST.findall(line) if "." in h.strip(".")}
        hosts |= {m.group(1).lower() for m in _DOMAIN.finditer(line)}
        for host in sorted(hosts):
            if host in ALLOWED_DOMAINS or any(host.endswith("." + d) for d in ("example.org", "example.test", "example.com")):
                continue
            if _IPV4.fullmatch(host):
                continue
            out.append(f"{name}:{n}: domain {host} is not an example or allowlisted documentation host")
        if _HOME.search(line):
            out.append(f"{name}:{n}: home directory path")
        if _ESTATE_REPO.search(line):
            out.append(f"{name}:{n}: estate-named repo (use the <estate> placeholder or the example estate)")
        if any(d in line for d in _DASHES):
            out.append(f"{name}:{n}: em or en dash")
        for pat in denylist or []:
            if pat.search(line):
                out.append(f"{name}:{n}: denylisted term (see the private denylist)")
    return out


def scan(root: Path, denylist: list[re.Pattern[str]] | None = None) -> list[str]:
    """Scan every text file under *root*."""
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or any(part in SKIP_DIRS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.suffix in SKIP_SUFFIXES or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(text, str(rel), denylist))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("root", nargs="?", default=None, help="tree to scan (default: this repo)")
    parser.add_argument("--denylist", default=None, help="private denylist file (or env SKBRAIN_SCRUB_DENYLIST)")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[1]
    release = os.environ.get("SKBRAIN_SCRUB_RELEASE") == "1"
    deny_path = args.denylist or os.environ.get("SKBRAIN_SCRUB_DENYLIST") or ""
    denylist: list[re.Pattern[str]] | None = None
    if deny_path:
        try:
            denylist = load_denylist(Path(deny_path))
        except OSError as exc:
            print(f"validate_public: cannot read denylist: {exc}", file=sys.stderr)
            return 2
        if not denylist:
            print("validate_public: the denylist is empty", file=sys.stderr)
            return 2
    elif release:
        print(
            "validate_public: SKBRAIN_SCRUB_RELEASE=1 but no denylist given "
            "(--denylist or SKBRAIN_SCRUB_DENYLIST); refusing to certify a release",
            file=sys.stderr,
        )
        return 2
    else:
        print("validate_public: note: no denylist, private-name check skipped (not a release run)", file=sys.stderr)

    findings = scan(root, denylist)
    for f in findings:
        print(f)
    if findings:
        print(f"validate_public: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("validate_public: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
