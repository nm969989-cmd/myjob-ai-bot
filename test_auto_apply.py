"""No external submissions: policy, caps, outcome and notification regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, timedelta
from flask import Flask
import auto_apply_service as a
from career_service import Store, UTC, register_routes

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
URL = 'https://jobs.lever.co/example/12345678-1234-1234-1234-123456789abc'


class AutoApplyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.store = Store(self.root/'state.sqlite3')
        (self.root/'profile.json').write_text(json.dumps(dict(full_name='Synthetic Candidate', email='test@candidate.invalid', phone='12345')))
        (self.root/'resume.pdf').write_bytes(b'%PDF-1.4 synthetic fixture')
        self.p = dict(a.defaults(), enabled=True, profileConfirmed=True, employers=[dict(company='Example',leverSlug='example')], roles=['Python Developer'], cities=['Chennai'], minSalaryLpa=5, dailyLimit=1)
        a.save_policy(self.store, self.p, 0)
        self.job = dict(title='Python Developer',company='Example',city='Chennai',salary='6-8 LPA',apply_url=URL,verified_at=NOW.isoformat())
        self.sender = Mock(); self.adapter = Mock(return_value=True)

    def tick(self, jobs=None, now=NOW):
        a.tick(self.store, jobs or [self.job], self.root, self.sender, 'synthetic-chat', self.adapter, now)

    def test_exact_employer_host_role_location_salary_expiry_filters(self):
        self.assertTrue(a.eligible(self.job,self.p,NOW))
        for update in [dict(company='Other'),dict(city='Delhi'),dict(title='Java Developer'),dict(salary='Not stated'),dict(salary='4-9 LPA'),dict(deadline='2000-01-01'),dict(verified_at=''),dict(apply_url=URL.replace('jobs.lever.co','jobs.lever.co.evil.invalid')),dict(apply_url=URL.replace('/example/','/other/'))]:
            self.assertFalse(a.eligible(dict(self.job,**update),self.p,NOW),update)

    def test_confirmed_submission_updates_tracker_and_sends_link_once(self):
        self.tick(); self.tick(now=NOW+timedelta(days=1))
        self.adapter.assert_called_once();self.sender.send_message.assert_called_once()
        message=self.sender.send_message.call_args.args[1]
        self.assertIn('Application submitted',message);self.assertIn(URL,message)
        self.assertEqual(self.store.read()['state']['applications'][URL]['status'],'Applied')

    def test_unknown_counts_toward_cap_and_never_retries(self):
        self.adapter.side_effect=TimeoutError();self.tick()
        self.adapter.side_effect=None
        self.tick([dict(self.job,apply_url=URL.replace('abc','abd'))])
        self.tick(now=NOW+timedelta(days=1))
        self.adapter.assert_called_once()
        self.assertEqual(self.store.read()['state']['applications'],{})
        self.assertEqual(a.policy(self.store)['attempts'][0]['status'],'unknown')
        self.assertNotIn('Application submitted',self.sender.send_message.call_args.args[1])

    def test_notification_retry_does_not_resubmit(self):
        self.sender.send_message.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):self.tick()
        self.sender.send_message.side_effect=None;self.tick()
        self.adapter.assert_called_once();self.assertEqual(self.sender.send_message.call_count,2)
        self.assertTrue(a.policy(self.store)['attempts'][0]['notified'])

    def test_disabled_and_missing_profile_never_apply(self):
        a.save_policy(self.store,dict(self.p,enabled=False),1);self.tick();self.adapter.assert_not_called()
        a.save_policy(self.store,self.p,2);(self.root/'profile.json').unlink()
        with self.assertRaises(FileNotFoundError):self.tick()
        self.adapter.assert_not_called()

    def test_already_tracked_or_legacy_applied_are_skipped(self):
        (self.root/'applied_jobs.json').write_text(json.dumps([URL]));self.tick();self.adapter.assert_not_called()
        (self.root/'applied_jobs.json').unlink()
        snapshot=self.store.read();snapshot['state']['applications'][URL]={'job':self.job,'status':'Saved','notes':'keep','followUp':''}
        self.store.write(snapshot['state'],snapshot['revision']);self.tick();self.adapter.assert_not_called()

    def test_truthy_unconfirmed_outcome_is_not_success(self):
        self.adapter.return_value={'submitted':False};self.tick()
        self.assertEqual(a.policy(self.store)['attempts'][0]['status'],'manual')
        self.assertEqual(self.store.read()['state']['applications'],{})

    def test_interrupted_attempt_is_not_retried(self):
        with self.store.connect() as db:
            a.tables(db);db.execute("INSERT INTO auto_attempts VALUES (?,?,'reserved',?,'',0)",(URL,'2026-10-09',json.dumps(a.normalize(self.job))));db.commit()
        self.tick();self.adapter.assert_not_called()
        self.assertEqual(a.policy(self.store)['attempts'][0]['status'],'unknown')

    def test_policy_validation_revision_and_routes(self):
        for update in [dict(dailyLimit=0),dict(dailyLimit=True),dict(minSalaryLpa=float('nan')),dict(employers=[]),dict(roles=[]),dict(profileConfirmed=False),dict(timezone='../etc')]:
            with self.assertRaises(ValueError):a.validate(dict(self.p,**update))
        app=Flask(__name__);register_routes(app,self.root,self.store);client=app.test_client()
        self.assertEqual(client.get('/api/career/automation').json['revision'],1)
        self.assertEqual(client.post('/api/career/automation',json={'settings':self.p,'revision':0}).status_code,409)
        from test_dashboard import DashboardAuthTests
        guard=DashboardAuthTests();guard.setUp()
        self.assertEqual(guard.client.get('/api/career/automation').status_code,401)
        guard.login()
        self.assertEqual(guard.client.post('/api/career/automation',json={},base_url='https://localhost',headers={'Origin':'https://evil.invalid'}).status_code,403)


if __name__=='__main__':unittest.main()
