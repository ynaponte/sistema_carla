import os
import sys
import configparser
import pathlib
import pytest
from pathlib import Path

# Ensure the module under test can be imported when tests run from anywhere
THIS_DIR = pathlib.Path(__file__).parent.resolve()
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from src.cli import config_check  # noqa: E402


# --------------------------
# Fixtures & Test Utilities
# --------------------------

@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Run each test in an isolated working directory and ensure a clean CONFIG_FILE."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(old_cwd)


class PromptSequencer:
    """Helper to feed a sequence of answers to typer.prompt calls in order."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, text, default=None):
        self.calls.append((text, default))
        if not self.answers:
            # Fallback to default if provided, otherwise raise to surface mismatch
            if default is not None:
                return default
            raise AssertionError(f"No more prompt answers left for question: {text!r}")
        return self.answers.pop(0)


class ConfirmSequencer:
    """Helper to feed a sequence of booleans to typer.confirm calls in order."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, text):
        self.calls.append(text)
        if not self.answers:
            raise AssertionError(f"No more confirm answers left for question: {text!r}")
        return self.answers.pop(0)


def read_cfg(path="carla.cfg"):
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    return cp


def write_cfg(paths_dict, path="carla.cfg"):
    cp = configparser.ConfigParser()
    cp["paths"] = paths_dict
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)


# --------------------------
# Tests
# --------------------------

def test_run_wizard_when_config_missing_creates_dirs_and_saves(monkeypatch, tmp_path):
    """If no config exists, validate_project_config should run the setup wizard,
    create dirs and save a config with wizard keys (docs_path, references_path, results_path, db_path)."""

    # Ensure no config file exists
    assert not Path(config_check.CONFIG_FILE).exists()

    # Prepare prompt answers for the wizard (4 prompts)
    report_dir = tmp_path / "report_wz"
    refs_dir = tmp_path / "refs_wz"
    results_dir = tmp_path / "results_wz"
    vec_dir = tmp_path / "vec_wz"

    prompts = PromptSequencer([str(report_dir), str(refs_dir), str(results_dir), str(vec_dir)])
    monkeypatch.setattr(config_check.typer, "prompt", prompts)

    # Run
    returned = config_check.validate_project_config()

    # Assert directories created
    for p in [report_dir, refs_dir, results_dir, vec_dir]:
        assert p.is_dir(), f"Directory not created: {p}"

    # Assert config file saved with wizard keys
    cp = read_cfg()
    assert "paths" in cp
    assert cp["paths"].get("docs_path") == str(report_dir)
    assert cp["paths"].get("references_path") == str(refs_dir)
    assert cp["paths"].get("results_path") == str(results_dir)
    assert cp["paths"].get("db_path") == str(vec_dir)

    # Returned value should match the wizard dict
    assert returned == {
        "docs_path": str(report_dir),
        "references_path": str(refs_dir),
        "results_path": str(results_dir),
        "db_path": str(vec_dir),
    }


def test_validate_adds_missing_required_keys_and_creates_dirs(monkeypatch, tmp_path):
    """Given an existing config lacking REQUIRED_KEYS, the validator should prompt for
    missing ones and create directories (with user confirming creation)."""

    # Start from a config with unrelated wizard keys only (simulating a typical first run)
    write_cfg({
        "docs_path": str(tmp_path / "docs"),
        "db_path": str(tmp_path / "db"),
    })

    # Prepare prompt answers for each missing required key in order:
    # REQUIRED_KEYS = ["report_path", "references_path", "results_path", "vectorstore_path"]
    report_dir = tmp_path / "report_added"
    refs_dir = tmp_path / "refs_added"
    results_dir = tmp_path / "results_added"
    vector_dir = tmp_path / "vector_added"

    prompts = PromptSequencer([str(report_dir), str(refs_dir), str(results_dir), str(vector_dir)])
    confirms = ConfirmSequencer([True, True, True, True])  # agree to create each

    monkeypatch.setattr(config_check.typer, "prompt", prompts)
    monkeypatch.setattr(config_check.typer, "confirm", confirms)

    out = config_check.validate_project_config()

    # All new directories should exist now
    for p in [report_dir, refs_dir, results_dir, vector_dir]:
        assert p.is_dir()

    # File should be updated with both original and new keys
    cp = read_cfg()
    paths = cp["paths"]
    assert paths.get("docs_path")
    assert paths.get("db_path")
    assert paths.get("report_path") == str(report_dir)
    assert paths.get("references_path") == str(refs_dir)
    assert paths.get("results_path") == str(results_dir)
    assert paths.get("vectorstore_path") == str(vector_dir)

    # Returned dict should contain at least the required keys
    for k in ("report_path", "references_path", "results_path", "vectorstore_path"):
        assert k in out


def test_validate_reprompts_when_user_declines_create_and_provides_valid_path(monkeypatch, tmp_path):
    """When a required path doesn't exist and the user declines auto-create,
    the validator should re-prompt until a valid path is provided."""

    # Pre-create config with all required keys except 'report_path'
    refs = tmp_path / "refs_ok"; refs.mkdir()
    res = tmp_path / "results_ok"; res.mkdir()
    vec = tmp_path / "vec_ok"; vec.mkdir()

    write_cfg({
        "references_path": str(refs),
        "results_path": str(res),
        "vectorstore_path": str(vec),
    })

    # First answer is an invalid path; user declines creation; then supplies a valid existing path
    bad_path = tmp_path / "nonexistent" / "deep"
    good_path = tmp_path / "good_report"
    good_path.mkdir()

    prompts = PromptSequencer([str(bad_path), str(good_path)])
    confirms = ConfirmSequencer([False])  # decline directory creation once

    monkeypatch.setattr(config_check.typer, "prompt", prompts)
    monkeypatch.setattr(config_check.typer, "confirm", confirms)

    out = config_check.validate_project_config()

    # Ensure final path used is the valid one
    assert out["report_path"] == str(good_path)

    # Config file should persist that valid path
    cp = read_cfg()
    assert cp["paths"].get("report_path") == str(good_path)


def test_no_update_when_all_required_keys_present(monkeypatch, tmp_path):
    """If all required keys exist and point to directories, the config must not be rewritten."""
    # Create directories for each required key
    req_dirs = {}
    for k in config_check.REQUIRED_KEYS:
        p = tmp_path / f"{k}_dir"
        p.mkdir()
        req_dirs[k] = str(p)

    write_cfg(req_dirs)

    # Spy on save_config to ensure it is NOT called
    called = {"flag": False}
    def spy_save(cfg):
        called["flag"] = True
        raise AssertionError("save_config should not be called when no updates are needed")

    monkeypatch.setattr(config_check, "save_config", spy_save)

    out = config_check.validate_project_config()

    assert not called["flag"]
    assert out == req_dirs  # unchanged


def test_load_config_returns_empty_if_paths_section_missing(monkeypatch, tmp_path):
    """load_config should return {} when the config exists but lacks a [paths] section,
    causing validate to run the wizard."""

    # Write config with some other section
    cp = configparser.ConfigParser()
    cp["other"] = {"x": "1"}
    with open(config_check.CONFIG_FILE, "w", encoding="utf-8") as f:
        cp.write(f)

    # Prepare wizard prompt answers
    report_dir = tmp_path / "report_wizard2"
    refs_dir = tmp_path / "refs_wizard2"
    results_dir = tmp_path / "results_wizard2"
    vec_dir = tmp_path / "vec_wizard2"
    prompts = PromptSequencer([str(report_dir), str(refs_dir), str(results_dir), str(vec_dir)])
    monkeypatch.setattr(config_check.typer, "prompt", prompts)

    out = config_check.validate_project_config()

    # Wizard should have created directories and saved them under wizard keys
    for p in [report_dir, refs_dir, results_dir, vec_dir]:
        assert p.is_dir()

    cp2 = read_cfg()
    assert "paths" in cp2
    assert cp2["paths"].get("docs_path") == str(report_dir)
    assert out.get("docs_path") == str(report_dir)


def test_save_config_roundtrip_utf8_and_section():
    """save_config should write a UTF-8 file with a [paths] section that round-trips."""
    data = {"a": "áéíóú ç", "b": "/tmp/β"}
    config_check.save_config(data)

    cp = read_cfg()
    assert "paths" in cp
    assert cp["paths"].get("a") == "áéíóú ç"
    assert cp["paths"].get("b") == "/tmp/β"
