import json
import pytest
import run_counter as rc


@pytest.fixture(autouse=True)
def patch_counter_file(tmp_path, monkeypatch):
    """Patch the counter file path to use a temp directory."""
    counter_file = tmp_path / "run_counter.json"
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    return counter_file


# ---------------------------------------------------------------------------
# load_counter
# ---------------------------------------------------------------------------


def test_load_counter_file_absent():
    """When file is absent, load_counter returns 0."""
    assert rc.load_counter() == 0


def test_load_counter_file_malformed_invalid_json(tmp_path, monkeypatch):
    """When file contains invalid JSON, load_counter returns 0."""
    counter_file = tmp_path / "run_counter.json"
    counter_file.write_text("not valid json")
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    assert rc.load_counter() == 0


def test_load_counter_file_missing_counter_key(tmp_path, monkeypatch):
    """When file is valid JSON but missing 'counter' key, return 0."""
    counter_file = tmp_path / "run_counter.json"
    counter_file.write_text(json.dumps({}))
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    assert rc.load_counter() == 0


def test_load_counter_counter_is_not_int(tmp_path, monkeypatch):
    """When counter value is not an int, return 0."""
    counter_file = tmp_path / "run_counter.json"
    counter_file.write_text(json.dumps({"counter": "not an int"}))
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    assert rc.load_counter() == 0


def test_load_counter_counter_is_negative(tmp_path, monkeypatch):
    """When counter value is negative, return 0."""
    counter_file = tmp_path / "run_counter.json"
    counter_file.write_text(json.dumps({"counter": -5}))
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    assert rc.load_counter() == 0


def test_load_counter_valid_file():
    """When file contains valid counter, load_counter returns it."""
    # Use the patched fixture which starts empty
    # First save a value
    rc.increment_and_save()
    # Then load it
    assert rc.load_counter() == 1


def test_load_counter_existing_value(tmp_path, monkeypatch):
    """Load a specific counter value from file."""
    counter_file = tmp_path / "run_counter.json"
    counter_file.write_text(json.dumps({"counter": 42}))
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    assert rc.load_counter() == 42


# ---------------------------------------------------------------------------
# increment_and_save
# ---------------------------------------------------------------------------


def test_increment_and_save_from_zero():
    """When counter doesn't exist, increment from 0 to 1."""
    result = rc.increment_and_save()
    assert result == 1


def test_increment_and_save_persists(tmp_path, monkeypatch):
    """After increment_and_save, the file contains the new value."""
    counter_file = tmp_path / "run_counter.json"
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    rc.increment_and_save()
    data = json.loads(counter_file.read_text())
    assert data["counter"] == 1


def test_increment_and_save_sequential():
    """Multiple calls increment sequentially."""
    assert rc.increment_and_save() == 1
    assert rc.increment_and_save() == 2
    assert rc.increment_and_save() == 3


def test_increment_and_save_from_41():
    """Increment from 41 returns 42."""
    # Manually write 41 to the file
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 41}))
    result = rc.increment_and_save()
    assert result == 42


def test_increment_and_save_creates_cache_dir(tmp_path, monkeypatch):
    """increment_and_save creates cache/ directory if it doesn't exist."""
    cache_dir = tmp_path / "cache"
    counter_file = cache_dir / "run_counter.json"
    monkeypatch.setattr(rc, "_COUNTER_FILE", counter_file)
    # cache_dir does not exist yet
    assert not cache_dir.exists()
    rc.increment_and_save()
    assert cache_dir.exists()
    assert counter_file.exists()


# ---------------------------------------------------------------------------
# build_run_label
# ---------------------------------------------------------------------------


def test_build_run_label_stefan_mueller():
    """build_run_label with 'stefan.mueller@company.com' and counter 42."""
    # We need to mock the counter to return 42
    # But build_run_label calls increment_and_save, which will increment
    # So we need to set the file to 41 so that after increment it's 42
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 41}))
    label = rc.build_run_label("stefan.mueller@company.com")
    assert label == "JiraMaster-STM-000042"


def test_build_run_label_john_doe():
    """build_run_label with 'john.doe@company.com' and counter 1."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("john.doe@company.com")
    assert label == "JiraMaster-JOD-000001"


def test_build_run_label_single_name():
    """build_run_label with single-part name 'john@company.com'."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("john@company.com")
    assert label == "JiraMaster-JOH-000001"


def test_build_run_label_very_short_parts():
    """build_run_label with short name segments 'a.b@company.com'."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("a.b@company.com")
    # First segment "a" (1 char) + second segment "b" (1 char) = "ab" (2 chars)
    # Pad to 3: "abX" -> But our logic uses ljust('X') which would give "abX"
    # Actually, let me check the code: we use .ljust(3, "X") which pads with X
    # So "ab".ljust(3, "X") = "abX"
    assert label == "JiraMaster-ABX-000001"


def test_build_run_label_uppercase():
    """Initials are always uppercase."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 99}))
    label = rc.build_run_label("alice.beta@example.com")
    # alice -> "al" (first 2), beta -> "b" (first 1) = "alb" -> uppercase = "ALB"
    assert label == "JiraMaster-ALB-000100"


def test_build_run_label_zero_padded_counter():
    """Counter is zero-padded to 6 digits."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("test@example.com")
    # Counter should be 000001
    assert "000001" in label


def test_build_run_label_counter_increments():
    """Each call to build_run_label increments the counter."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))

    label1 = rc.build_run_label("test@example.com")
    label2 = rc.build_run_label("test@example.com")

    assert "000001" in label1
    assert "000002" in label2


def test_build_run_label_strips_non_alpha():
    """Non-alphabetic characters are stripped from initials."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    # Name like "john-paul.peter@example.com"
    # local part is "john-paul.peter"
    # segments: ["john-paul", "peter"]
    # first 2 of "john-paul": "jo"
    # first 1 of "peter": "p"
    # Result: "jop" (all alpha, no stripping needed)
    label = rc.build_run_label("john-paul.peter@example.com")
    # We take first 2 chars of "john-paul" = "jo", strip non-alpha = "jo"
    # Then first 1 char of "peter" = "p"
    # "jop" uppercase = "JOP"
    assert "JOP" in label


def test_build_run_label_no_at_sign():
    """Handle username with no @ sign (fallback to full string)."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("justaname")
    # local_part = "justaname" (no @ found)
    # segments = ["justaname"]
    # First 3 chars: "jus" -> "JUS"
    assert "JUS" in label


def test_build_run_label_with_numbers_in_email():
    """Email with numbers in the local part."""
    counter_file = rc._COUNTER_FILE
    counter_file.parent.mkdir(exist_ok=True)
    counter_file.write_text(json.dumps({"counter": 0}))
    label = rc.build_run_label("user123.test456@example.com")
    # segments: ["user123", "test456"]
    # first 2 of "user123": "us"
    # first 1 of "test456": "t"
    # "ust" -> "UST" (all alpha after strip, numbers are stripped)
    # Actually wait, numbers are not alpha, so they get stripped
    # "user123"[:2] = "us", strip non-alpha = "us"
    # "test456"[:1] = "t", strip non-alpha = "t"
    # "ust" uppercase = "UST"
    assert "UST" in label
