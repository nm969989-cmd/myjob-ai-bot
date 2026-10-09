"""Offline private-state and delivery tests. Never import the production main bot."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import engineering_telegram as e


def result(jobs=None, age=0):
    return {'generated_at': (datetime.now(timezone.utc)-timedelta(hours=age)).isoformat(),
            'preset': dict(e.DEFAULT), 'jobs': jobs or []}


def job(i):
    return {'id': str(i), 'title': 'Python Developer', 'company': 'Example', 'city': 'Chennai',
            'apply_url': f'https://example.test/jobs/{i}', 'source': 'fixture',
            'verify_reason': 'live_public_job', 'match': {'integrity': 'verified', 'score': 90}}


class EngineeringTelegramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_patch = patch.object(e, 'STATE', Path(self.tmp.name)/'private/state.json')
        self.state_patch.start()
    def tearDown(self):
        self.state_patch.stop()
        self.tmp.cleanup()
    def test_unknown_defaults_and_private_permissions(self):
        state=e.load_state()
        self.assertFalse(state['profile']['configured'])
        self.assertIsNone(state['profile']['experience_years'])
        e.save_state(state)
        self.assertEqual(e.STATE.stat().st_mode & 0o777, 0o600)
    def test_profile_validation(self):
        p=e.parse_profile('branch=computer science;skills=python,sql;experience=unknown;radius=30',dict(e.DEFAULT))
        self.assertEqual(p['skills'],['python','sql'])
        self.assertIsNone(p['experience_years'])
        with self.assertRaises(ValueError): e.parse_profile('radius=999',p)
        with self.assertRaises(ValueError): e.parse_profile('experience=nan',p)
    def test_short_digest_and_stale_scan(self):
        jobs=[job(i) for i in range(20)]
        r=result(jobs)
        text=e.digest_text('default',r,jobs)
        self.assertLessEqual(len(text),3900)
        self.assertIn('experience unknown',text)
        self.assertIn('Uncertain',e.digest_text('default',r,[{**job(1),'match':{'integrity':'uncertain','score':50}}]))
        self.assertEqual(e.visible_jobs(result(jobs,age=49),jobs),[])
        self.assertIn('no current verified matches claimed',e.digest_text('default',result(jobs,age=49),jobs))
    def test_success_marks_only_rendered_ids_and_repeated_scan_is_quiet(self):
        jobs=[job(i) for i in range(20)]
        with patch.object(e,'query_batch',side_effect=lambda profiles:[result(jobs) for _ in profiles]):
            bot=Mock()
            e.dispatch(bot,'123')
            seen=e.load_state()['seen']['default']
            shown=e.visible_jobs(result(jobs),jobs)
            self.assertEqual(set(seen),{f"{j['id']}:verified" for j in shown})
            self.assertLess(len(seen),len(jobs))
    def test_failed_send_does_not_mark_seen(self):
        bot=Mock();bot.send_message.side_effect=RuntimeError('fixture provider failure')
        with patch.object(e,'query_batch',side_effect=lambda profiles:[result([job(1)]) for _ in profiles]), self.assertRaises(RuntimeError):
            e.dispatch(bot,'123')
        self.assertNotIn('default',e.load_state()['seen'])
    def test_saved_searches_round_robin_and_integrity_upgrade(self):
        state=e.load_state();state['searches']={f's{i}':{'role':'python','city':'Chennai'} for i in range(10)};e.save_state(state)
        bot=Mock()
        with patch.object(e,'query_batch',side_effect=lambda profiles:[result([job(1)]) for _ in profiles]):
            e.dispatch(bot,'123');e.dispatch(bot,'123');e.dispatch(bot,'123')
        self.assertEqual(len(e.load_state()['seen']),10)
        self.assertEqual(bot.send_message.call_count,10)
    def test_absolute_node_fixed_argv_and_stdin(self):
        executable = Path(self.tmp.name) / 'node'
        executable.write_text('fixture, never executed', encoding='utf8')
        executable.chmod(0o755)
        with patch.object(e.shutil, 'which', return_value=str(executable)), patch.object(e.subprocess, 'run', return_value=Mock(stdout='{}')) as run:
            e.query({'roles': ['$(not-a-command)']})
        argv, kwargs = run.call_args.args[0], run.call_args.kwargs
        self.assertEqual(argv, [str(executable.resolve()), str(e.ROOT / 'tn-live-jobs/src/engineering.js'), '--query'])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(e.json.loads(kwargs['input'])['profile']['roles'], ['$(not-a-command)'])
    def test_missing_node_fails_closed(self):
        with patch.object(e.shutil, 'which', return_value=None), self.assertRaises(FileNotFoundError):
            e.query(dict(e.DEFAULT))
    def test_invalid_private_state_not_overwritten(self):
        e.STATE.parent.mkdir(parents=True)
        e.STATE.write_text('[]', encoding='utf8')
        with self.assertRaises(TypeError):
            e.load_state()
        self.assertEqual(e.STATE.read_text(encoding='utf8'), '[]')
    def test_non_owner_private_command_is_ignored(self):
        bot=Mock();handlers=[]
        bot.message_handler.side_effect=lambda **kw: lambda fn: handlers.append(fn) or fn
        e.install_handlers(bot,'123')
        msg=Mock();msg.chat.id=456;msg.chat.type='private';msg.text='/searches'
        handlers[0](msg)
        bot.send_message.assert_not_called()


if __name__ == '__main__':
    unittest.main()
