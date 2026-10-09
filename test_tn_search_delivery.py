import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock
from career_service import UTC
from tn_search_delivery import collect,csv_bytes,send

class SearchDeliveryTests(unittest.TestCase):
    def test_all_categories_dates_duplicates_region_and_formula_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'tn-live-jobs/public/data';d.mkdir(parents=True)
            src=root/'tn-live-jobs/src';src.mkdir()
            (src/'city-aliases.json').write_text(json.dumps(dict(Chennai=['chennai'],Puducherry=['puducherry'],Hosur=['hosur'])))
            base=dict(title='Nurse',company='Example',city='Hosur',apply_url='https://example.org/1',posted_at='2026-10-08')
            rows=[base,dict(base,apply_url=base['apply_url']+'?utm_source=x'),dict(base,title='=BAD',city='Puducherry',apply_url='https://example.org/2'),dict(base,posted_at='',apply_url='https://example.org/3'),dict(base,posted_at='2020-01-01',apply_url='https://example.org/4'),dict(base,city='Delhi',apply_url='https://example.org/5'),dict(base,deadline='2020-01-01',apply_url='https://example.org/6')]
            (d/'jobs.json').write_text(json.dumps({'jobs':rows}))
            jobs,unknown=collect(root,7,datetime(2026,10,9,tzinfo=UTC))
            self.assertEqual(len(jobs),2);self.assertEqual(unknown,1)
            self.assertIn("'=BAD",csv_bytes(jobs).decode('utf-8-sig'))
            self.assertEqual(jobs[1]['region'],'Puducherry (separate UT)')
            sender=Mock();send(sender,'synthetic-chat',root,90);sender.send_document.assert_called_once()
            with self.assertRaises(ValueError):collect(root,0)


class SearchReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        source=self.root/'tn-live-jobs/src';source.mkdir(parents=True)
        (source/'city-aliases.json').write_text(json.dumps({'Chennai':['chennai','madras'],'Hosur':['hosur'],'Puducherry':['puducherry','pondicherry']}))
        self.feed=self.root/'tn-live-jobs/public/data/jobs.json';self.feed.parent.mkdir(parents=True)
        self.now=datetime(2026,10,9,18,45,tzinfo=UTC) # October 10 IST
        self.job=dict(title='Teacher',company='Example',city='Chennai',apply_url='https://example.org/job',posted_at='2026-10-10')

    def write(self, rows):self.feed.write_text(json.dumps({'jobs':rows}))

    def test_calendar_dates_and_future_timestamps(self):
        from tn_search_delivery import search
        self.write([self.job,dict(self.job,apply_url='https://example.org/yesterday',posted_at='2026-10-09'),dict(self.job,apply_url='https://example.org/future',posted_at='2026-10-09T19:00:00Z')])
        result=search(self.root,1,now=self.now)
        self.assertEqual([j['url'] for j in result['jobs']],['https://example.org/job'])
        self.assertEqual(result['from_date'],'2026-10-10')

    def test_feed_failures_and_malformed_rows_are_reported(self):
        from tn_search_delivery import search,FeedUnavailable
        self.feed.write_text('null')
        with self.assertRaises(FeedUnavailable):search(self.root,now=self.now)
        self.write([None,[],42,self.job]);result=search(self.root,now=self.now)
        self.assertEqual(result['malformed'],3);self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['sources'][1]['status'],'unavailable')
        self.write([]);self.assertEqual(search(self.root,now=self.now)['jobs'],[])

    def test_newer_failed_copy_supersedes_old_open_listing(self):
        from tn_search_delivery import search
        self.write([dict(self.job,verified=True,verified_at='2026-10-09T10:00:00Z')])
        (self.root/'radar_results.json').write_text(json.dumps({'jobs':[dict(self.job,verified=False,verified_at='2026-10-09T11:00:00Z')]}))
        result=search(self.root,now=self.now)
        self.assertEqual(result['jobs'],[]);self.assertEqual(result['excluded'],1)

    def test_newer_check_keeps_existing_job_metadata(self):
        from tn_search_delivery import search
        self.write([self.job])
        (self.root/'radar_results.json').write_text(json.dumps({'jobs':[dict(link=self.job['apply_url'],verified=True,verified_at='2026-10-09T11:00:00Z')]}))
        result=search(self.root,now=self.now)
        self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['jobs'][0]['title'],'Teacher')
        self.assertEqual(result['jobs'][0]['checkStatus'],'success')

    def test_alias_filter_and_invalid_city(self):
        from tn_search_delivery import search
        self.write([self.job,dict(self.job,city='Hosur',apply_url='https://example.org/hosur')])
        self.assertEqual(len(search(self.root,city='Madras',now=self.now)['jobs']),1)
        with self.assertRaises(ValueError):search(self.root,city='Unknown',now=self.now)

    def test_private_route_error_codes_and_csv(self):
        from flask import Flask
        from career_service import register_routes,Store
        app=Flask(__name__);register_routes(app,self.root,Store(self.root/'state.sqlite3'));client=app.test_client()
        self.assertEqual(client.get('/api/career/tn-search').status_code,503)
        self.write([])
        self.assertEqual(client.get('/api/career/tn-search?days=bad').status_code,400)
        response=client.get('/api/career/tn-search?download=csv')
        self.assertEqual(response.status_code,200);self.assertIn('attachment',response.headers['Content-Disposition'])
        from test_dashboard import DashboardAuthTests
        guard=DashboardAuthTests();guard.setUp()
        self.assertEqual(guard.client.get('/api/career/tn-search').status_code,401)

    def test_delivery_caption_is_bounded_and_send_failure_propagates(self):
        from unittest.mock import patch
        from tn_search_delivery import search
        self.write([dict(self.job,apply_url='https://example.org/'+('a'*1500))])
        result=search(self.root,now=self.now)
        sender=Mock()
        with patch('tn_search_delivery.search',return_value=result):
            send(sender,'synthetic',self.root)
            self.assertLessEqual(len(sender.send_document.call_args.kwargs['caption']),1024)
            self.assertIsNone(sender.send_document.call_args.kwargs['parse_mode'])
            sender.send_document.side_effect=RuntimeError('transport down')
            with self.assertRaises(RuntimeError):send(sender,'synthetic',self.root)

if __name__=='__main__':unittest.main()
