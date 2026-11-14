"""Shared fixtures: a valid fake-estate canon copied from the instance template."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "instance-repo"


@pytest.fixture
def canon(tmp_path: Path) -> Path:
    """A fresh, valid copy of the example estate canon, named like a real repo."""
    dest = tmp_path / "skbrain-ops-example"
    shutil.copytree(TEMPLATE, dest)
    return dest
