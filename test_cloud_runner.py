"""Cloud exit statuses with all external services mocked."""
import importlib
import sys
import types
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('TELEGRAM_TOKEN', raising=False)
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    module = importlib.import_module('cloud_runner')
    monkeypatch.setattr(module, 'bot', Mock())
    monkeypatch.setattr(module, 'chat_id', 'offline-chat')
    monkeypatch.setattr(module, 'step_errors', [])
    monkeypatch.setattr(module, 'stage_notes', [])
    monkeypatch.setattr(module, 'stage_times', {})
    monkeypatch.setattr(module, 'START_TIME', module.time.time())
    fake_main = types.SimpleNamespace(
        TARGET_CHANNELS=[], scrape_single_channel=Mock(return_value=(0, 0)),
        load_applied_jobs=Mock(return_value=set()), save_applied_job=Mock(),
        load_profile=Mock(return_value={}))
    monkeypatch.setitem(sys.modules, 'main', fake_main)
    monkeypatch.setattr(module, 'run_radar', Mock(return_value=[]))
    with patch('job_radar.dispatch_tamil_nadu_alerts', return_value=0), patch('bot_optimizer.dispatch_walkin_alerts', return_value=0):
        yield module


def test_missing_delivery_configuration_fails_without_search(runner):
    runner.bot = None
    assert runner.run_cloud() == 2
    runner.run_radar.assert_not_called()


def test_empty_successful_cycle_is_not_failure(runner):
    assert runner.run_cloud() == 0
    runner.bot.send_message.assert_called_once()


def test_caught_stage_failure_is_nonzero(runner):
    runner.run_radar.side_effect = RuntimeError('mocked radar failure')
    assert runner.run_cloud() == 1
    assert any('Radar stage' in error for error in runner.step_errors)


def test_status_delivery_failure_is_nonzero(runner):
    runner.bot.send_message.side_effect = RuntimeError('mocked delivery failure')
    assert runner.run_cloud() == 1
    assert any('Status delivery' in error for error in runner.step_errors)


def test_unavailable_channel_is_nonfatal_note(runner):
    sys.modules['main'].scrape_single_channel.side_effect = TimeoutError('source offline')
    assert runner.run_cloud() == 0
    assert any('unavailable' in note for note in runner.stage_notes)
