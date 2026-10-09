"""Offline persistence, matching, expiry, notification and route tests."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask
import career_service as c

NOW = datetime(2026, 10, 9, 6, 0, tzinfo=c.UTC)  # 11:30 IST


def job(**values):
    return dict(title='Python Developer', company='Example', city='Chennai', skills=['Python'], salary='6-8 LPA',
                experience='1-3 years', verified_at='2026-10-09T05:00:00Z', apply_url='https://example.org/job/1', **values)


class CareerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = c.Store(self.root / 'private.sqlite3')
        self.sender = Mock()
        self.state = c.initial_state()
        self.state['preferences']['skills'] = ['Python']
        self.state['alerts']['enabled'] = True

    def save(self):
        snapshot = self.store.read()
        return self.store.write(self.state, snapshot['revision'])

    def test_private_state_survives_restart_and_conflicts_do_not_overwrite(self):
        self.save()
        self.assertEqual(c.Store(self.store.path).read()['state'], self.state)
        with self.assertRaises(c.Conflict):
            self.store.write(c.initial_state(), 0)
        self.assertEqual(self.store.read()['revision'], 1)

    def test_validation_rejects_invalid_threshold_timezone_date_and_url(self):
        for key, value in [('minScore', -1), ('maxAgeDays', 0), ('timezone', 'not/a/zone'), ('time', '25:00')]:
            state = c.initial_state(); state['alerts'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.validate_state(state)
        for url, due in [('javascript:alert(1)', ''), ('https://example.org', '2026-02-31'), ('https://example.org', '2026-01-01bad')]:
            state = c.initial_state(); state['applications']['x'] = {'job': {'url': url}, 'status': 'Applied', 'followUp': due}
            with self.assertRaises(ValueError):
                c.validate_state(state)
        self.state['preferences']['experience'] = float('nan')
        with self.assertRaises(ValueError):
            c.validate_state(self.state)

    def test_explained_ranking_uses_stated_evidence_and_exact_skills(self):
        p = dict(skills=['Python', 'Java'], cities=['Pondicherry'], experience=2, minSalary=5, remote=False)
        j = c.normalize(dict(job(), city='Puducherry', description='JavaScript only'))
        score, reasons = c.match(j, p)
        self.assertEqual(score, 75)
        self.assertIn('Skills: Python', reasons)
        self.assertEqual(c.match(j, c.initial_state()['preferences'])[0], None)

    def test_quiet_hours_cross_midnight_and_daytime_and_disabled_window(self):
        a = self.state['alerts']
        self.assertTrue(c.quiet(a, NOW.replace(hour=18)))  # 23:30 IST
        self.assertTrue(c.quiet(a, NOW.replace(hour=0)))
        self.assertFalse(c.quiet(a, NOW))
        a.update(quietStart='10:00', quietEnd='12:00')
        self.assertTrue(c.quiet(a, NOW))
        a.update(quietStart='10:00', quietEnd='10:00')
        self.assertFalse(c.quiet(a, NOW))

    def test_digest_once_daily_and_deduplicates_canonical_urls_across_days(self):
        self.save()
        jobs = [job(), dict(job(), apply_url='https://example.org/job/1/?utm_source=copy')]
        self.assertEqual(c.dispatch(self.store, jobs, self.sender, 'synthetic-chat', NOW), 1)
        message = self.sender.send_message.call_args.args[1]
        self.assertEqual(message.count('Python Developer'), 1)
        self.assertEqual(c.dispatch(self.store, jobs, self.sender, 'synthetic-chat', NOW), 0)
        self.assertEqual(c.dispatch(self.store, jobs, self.sender, 'synthetic-chat', NOW + timedelta(days=1)), 0)

    def test_failed_send_is_retried_without_recording_receipts(self):
        self.save()
        self.sender.send_message.side_effect = RuntimeError('fake transport failure')
        with self.assertRaises(RuntimeError):
            c.dispatch(self.store, [job()], self.sender, 'chat', NOW)
        self.sender.send_message.side_effect = None
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW), 1)
        self.assertEqual(self.sender.send_message.call_count, 2)

    def test_expired_stale_unknown_and_tracked_jobs_are_excluded(self):
        self.state['applications'] = {'x': {'job': job(), 'status': 'Applied', 'notes': '', 'followUp': ''}}
        self.save()
        invalid = [job(), dict(job(), apply_url='https://example.org/expired', deadline='2020-01-01'),
                   dict(job(), apply_url='https://example.org/closed', closed=True),
                   dict(job(), apply_url='https://example.org/unknown', verified_at='', posted_at=''),
                   dict(job(), apply_url='https://example.org/old', verified_at='2020-01-01'),
                   dict(job(), apply_url='https://example.org/future', verified_at='2026-10-10T05:00:00Z'),
                   dict(job(), apply_url='https://example.org/failed', verified=False),
                   dict(job(), apply_url='https://example.org/old-post', posted_at='2020-01-01')]
        self.assertEqual(c.dispatch(self.store, invalid, self.sender, 'chat', NOW), 0)
        self.sender.send_message.assert_not_called()
        self.assertEqual(len(self.store.read()['state']['applications']), 1)

    def test_quiet_and_before_digest_time_do_not_consume_next_delivery(self):
        self.save()
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW.replace(hour=0)), 0)
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW.replace(hour=3)), 0)
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW), 1)

    def test_late_night_digest_waits_until_next_morning(self):
        self.state['alerts'].update(time='23:00', timezone='UTC')
        self.save()
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW.replace(hour=23)), 0)
        morning = (NOW + timedelta(days=1)).replace(hour=8)
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', morning), 1)
        self.assertEqual(c.dispatch(self.store, [dict(job(), apply_url='https://example.org/new')], self.sender, 'chat', morning.replace(hour=12)), 0)

    def test_followups_are_due_once_per_date_and_survive_expired_feed(self):
        self.state['alerts'].update(enabled=False, followupsEnabled=True)
        self.state['applications'] = {'a': {'job': dict(job(), closed=True), 'status': 'Interview', 'notes': 'private note', 'followUp': '2026-10-09'}}
        self.save()
        self.assertEqual(c.dispatch(self.store, [], self.sender, 'chat', NOW), 1)
        self.assertEqual(c.dispatch(self.store, [], self.sender, 'chat', NOW), 0)
        self.assertNotIn('private note', self.sender.send_message.call_args.args[1])
        self.state['applications']['a']['followUp'] = '2026-10-10'; self.save()
        self.assertEqual(c.dispatch(self.store, [], self.sender, 'chat', NOW + timedelta(days=1)), 1)

    def test_disabled_notifications_and_rejected_followups_are_silent(self):
        self.store.write(c.initial_state(), 0)
        self.assertEqual(c.dispatch(self.store, [job()], self.sender, 'chat', NOW), 0)
        self.state['alerts'].update(enabled=False, followupsEnabled=True)
        self.state['applications'] = {'a': {'job': job(), 'status': 'Rejected', 'followUp': '2026-10-09'}}
        self.save()
        self.assertEqual(c.dispatch(self.store, [], self.sender, 'chat', NOW), 0)

    def test_health_is_honest_and_contains_no_credentials(self):
        data = c.integration_health(self.store, self.root, {'TELEGRAM_TOKEN': 'secret-token', 'TELEGRAM_CHAT_ID': 'secret-chat'}, NOW)
        self.assertEqual(data['checks'][0]['status'], 'Configured, not checked')
        self.assertNotIn('secret-token', json.dumps(data))
        self.store.observe('telegram', 'delivery succeeded', NOW)
        self.assertEqual(c.integration_health(self.store, self.root, {}, NOW)['checks'][0]['status'], 'Last observed result')

    def test_routes_validate_conflicts_payload_and_asset_allowlist(self):
        app = Flask(__name__); app.testing = True
        c.register_routes(app, self.root, self.store)
        client = app.test_client()
        self.assertEqual(client.get('/api/career/state').json['revision'], 0)
        self.assertEqual(client.post('/api/career/state', json={'state': self.state, 'revision': 0}).status_code, 200)
        self.assertEqual(client.post('/api/career/state', json={'state': self.state, 'revision': 0}).status_code, 409)
        self.assertEqual(client.post('/api/career/state', json=[]).status_code, 400)
        self.assertEqual(client.get('/career-assets/../../main.py').status_code, 404)
        self.assertEqual(client.get('/api/career/jobs').json, {'jobs': []})

    def test_existing_dashboard_guard_protects_career_routes(self):
        from test_dashboard import DashboardAuthTests
        fixture = DashboardAuthTests(); fixture.setUp()
        self.assertEqual(fixture.client.get('/api/career/state').status_code, 401)
        self.assertEqual(fixture.client.get('/api/career/health').status_code, 401)
        fixture.login()
        self.assertEqual(fixture.client.post('/api/career/state', json={}, base_url='https://localhost', headers={'Origin': 'https://evil.example'}).status_code, 403)

    def test_source_loader_keeps_metadata_and_deduplicates(self):
        path = self.root / 'tn-live-jobs/public/data'; path.mkdir(parents=True)
        (path / 'jobs.json').write_text(json.dumps({'jobs': [job()]}))
        (self.root / 'radar_results.json').write_text(json.dumps({'jobs': [job()]}))
        loaded = c.load_jobs(self.root)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]['verifiedAt'], '2026-10-09T05:00:00Z')


if __name__ == '__main__':
    unittest.main()
