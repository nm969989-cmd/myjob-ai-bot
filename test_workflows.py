"""Structural checks for the GitHub Actions workflows.

YAML parsing is optional so the suite still runs where PyYAML is absent; the
verification workflow installs it, so the parsed assertions execute in CI.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _text(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_workflow_files_exist():
    for name in ("job_bot.yml", "static.yml", "verify.yml"):
        assert (WORKFLOWS / name).is_file()


def test_offline_test_step_does_not_mask_failures():
    text = _text("job_bot.yml")
    assert "not scrape\" || true" not in text, "`|| true` hides real test failures"
    assert "not scrape\"" in text


def test_state_checkpoint_runs_even_when_cycle_fails():
    text = _text("job_bot.yml")
    commit_step = text.split("- name: 💾 Commit & Push")[1]
    assert "if: always()" in commit_step.split("run:")[0], (
        "delivered-job dedup state must still be committed when the cycle exits nonzero"
    )
    assert "git push origin main ||" not in commit_step


def test_pages_workflow_does_not_auto_enable():
    assert "enablement" not in _text("static.yml")


def test_verification_workflow_has_no_secret_references():
    text = _text("verify.yml")
    for secret in ("secrets.", "TELEGRAM", "GEMINI", "GROQ", "NOTION"):
        assert secret not in text, f"verify workflow must stay secret-free: {secret}"


def test_workflows_are_valid_yaml_and_have_expected_triggers():
    yaml = pytest.importorskip("yaml")
    bot = yaml.safe_load(_text("job_bot.yml"))
    static = yaml.safe_load(_text("static.yml"))
    verify = yaml.safe_load(_text("verify.yml"))

    assert "jobs" in bot and "jobs" in static and "jobs" in verify
    # PyYAML maps the bare `on:` key to the boolean True.
    triggers = verify.get(True, verify.get("on", {})) or {}
    if isinstance(triggers, str):
        triggers = [triggers]
    assert "pull_request" in triggers
