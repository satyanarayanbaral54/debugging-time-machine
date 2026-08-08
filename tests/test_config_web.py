from __future__ import annotations

import os
from pathlib import Path

import pytest

from dtm.config import load_env_file
from dtm.web import analyze_payload


def test_load_env_file_sets_missing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'DTM_API_BASE="https://example.test"\nDTM_API_KEY=secret\n', encoding="utf-8"
    )
    monkeypatch.delenv("DTM_API_BASE", raising=False)
    monkeypatch.delenv("DTM_API_KEY", raising=False)

    loaded = load_env_file(env_path)

    assert loaded == {
        "DTM_API_BASE": "https://example.test",
        "DTM_API_KEY": "secret",
    }
    assert os.environ["DTM_API_BASE"] == "https://example.test"


def test_analyze_payload_requires_repo() -> None:
    with pytest.raises(ValueError, match="repo is required"):
        analyze_payload({})
