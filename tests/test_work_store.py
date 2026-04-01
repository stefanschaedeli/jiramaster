import json
import time
import uuid
import pytest
import work_store as ws
from models import Epic, Story


def _valid_uuid():
    return str(uuid.uuid4())


@pytest.fixture(autouse=True)
def patch_work_dir(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir()
    monkeypatch.setattr(ws, "WORK_DIR", work_dir)
    return work_dir


# ---------------------------------------------------------------------------
# _safe_work_path
# ---------------------------------------------------------------------------

def test_safe_work_path_valid():
    uid = _valid_uuid()
    path = ws._safe_work_path(uid)
    assert path.name == f"{uid}.json"
    assert ws.WORK_DIR in path.parents


def test_safe_work_path_invalid():
    with pytest.raises(ValueError, match="Invalid work_id"):
        ws._safe_work_path("not-a-uuid")


def test_safe_work_path_traversal():
    with pytest.raises(ValueError, match="Invalid work_id"):
        ws._safe_work_path("../../../etc/passwd")


def test_safe_work_path_empty():
    with pytest.raises(ValueError, match="Invalid work_id"):
        ws._safe_work_path("")


# ---------------------------------------------------------------------------
# load_epics / save_epics
# ---------------------------------------------------------------------------

def test_load_epics_missing_file():
    uid = _valid_uuid()
    assert ws.load_epics(uid) == []


def test_save_epics_creates_file(tmp_path):
    uid = _valid_uuid()
    epics = [Epic(title="E1", stories=[Story(title="S1")])]
    ws.save_epics(uid, epics)
    path = ws.WORK_DIR / f"{uid}.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data[0]["title"] == "E1"


def test_load_epics_existing(tmp_path):
    uid = _valid_uuid()
    path = ws.WORK_DIR / f"{uid}.json"
    data = [{"title": "E1", "description": "", "acceptance_criteria": "",
              "due_date": "", "priority": "Medium", "assignee": "",
              "status": "", "labels": [], "comment": "", "stories": [],
              "include": True, "initiative_id": None, "project_key": None,
              "jira_key": None}]
    path.write_text(json.dumps(data))
    epics = ws.load_epics(uid)
    assert len(epics) == 1
    assert epics[0].title == "E1"


def test_save_load_roundtrip():
    uid = _valid_uuid()
    original = [
        Epic(title="Epic A", stories=[Story(title="Story 1"), Story(title="Story 2")]),
        Epic(title="Epic B"),
    ]
    ws.save_epics(uid, original)
    loaded = ws.load_epics(uid)
    assert len(loaded) == 2
    assert loaded[0].title == "Epic A"
    assert len(loaded[0].stories) == 2
    assert loaded[1].title == "Epic B"


# ---------------------------------------------------------------------------
# cleanup_stale_work_files
# ---------------------------------------------------------------------------

def test_cleanup_stale_old_files(tmp_path):
    old_file = ws.WORK_DIR / f"{_valid_uuid()}.json"
    old_file.write_text("[]")
    # Set mtime to 25 hours ago
    old_time = time.time() - (25 * 3600)
    import os
    os.utime(old_file, (old_time, old_time))

    count = ws.cleanup_stale_work_files(max_age_hours=24)
    assert count == 1
    assert not old_file.exists()


def test_cleanup_preserves_recent_files(tmp_path):
    recent_file = ws.WORK_DIR / f"{_valid_uuid()}.json"
    recent_file.write_text("[]")
    count = ws.cleanup_stale_work_files(max_age_hours=24)
    assert count == 0
    assert recent_file.exists()


def test_cleanup_returns_count(tmp_path):
    import os
    old_time = time.time() - (48 * 3600)
    for _ in range(3):
        f = ws.WORK_DIR / f"{_valid_uuid()}.json"
        f.write_text("[]")
        os.utime(f, (old_time, old_time))
    count = ws.cleanup_stale_work_files(max_age_hours=24)
    assert count == 3
