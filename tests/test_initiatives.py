import json
import pytest
import initiatives


@pytest.fixture(autouse=True)
def patch_cache_file(tmp_path, monkeypatch):
    cache_file = tmp_path / "initiatives.json"
    monkeypatch.setattr(initiatives, "_CACHE_FILE", cache_file)
    return cache_file


_SAMPLE = [
    {"key": "INI-1", "summary": "Improve onboarding", "project_key": "PROJ"},
    {"key": "INI-2", "summary": "Reduce tech debt", "project_key": "CORE"},
]


def test_load_initiatives_no_file():
    assert initiatives.load_initiatives() == []


def test_load_initiatives_meta_no_file():
    meta = initiatives.load_initiatives_meta()
    assert meta["updated_at"] is None
    assert meta["items"] == []


def test_save_and_load_round_trip():
    initiatives.save_initiatives(_SAMPLE)
    result = initiatives.load_initiatives()
    assert result == _SAMPLE


def test_load_initiatives_meta_after_save():
    initiatives.save_initiatives(_SAMPLE)
    meta = initiatives.load_initiatives_meta()
    assert meta["updated_at"] is not None
    assert meta["items"] == _SAMPLE


def test_save_sets_updated_at():
    initiatives.save_initiatives([])
    meta = initiatives.load_initiatives_meta()
    assert meta["updated_at"] is not None
    # Should be a valid ISO timestamp
    assert "T" in meta["updated_at"]


def test_load_initiatives_corrupt_file(patch_cache_file):
    patch_cache_file.write_text("not valid json")
    assert initiatives.load_initiatives() == []


def test_load_initiatives_meta_corrupt_file(patch_cache_file):
    patch_cache_file.write_text("{broken")
    meta = initiatives.load_initiatives_meta()
    assert meta["updated_at"] is None
    assert meta["items"] == []


def test_save_creates_cache_directory(tmp_path, monkeypatch):
    nested = tmp_path / "subdir" / "initiatives.json"
    monkeypatch.setattr(initiatives, "_CACHE_FILE", nested)
    initiatives.save_initiatives(_SAMPLE)
    assert nested.exists()
    data = json.loads(nested.read_text())
    assert len(data["items"]) == 2
