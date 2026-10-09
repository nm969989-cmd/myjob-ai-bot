"""Offline regression tests: no real scraping, applications, or Telegram sends."""
import os
import ast
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import job_discovery as discovery
import bot_optimizer
import job_radar


class RegionalDiscoveryTests(unittest.TestCase):
    def test_aliases(self):
        for alias in ('tiruvannamalai', 'thiruvannamalai', 'thiruannamalai'):
            self.assertEqual(discovery.priority_city(alias), 'Tiruvannamalai')
        self.assertEqual(discovery.priority_city('Pondicherry, India'), 'Puducherry')
        self.assertTrue(discovery.city_matches('Puducherry', 'pondicherry'))
        self.assertEqual(discovery.priority_city('New Chennaiish'), '')

    def test_preferred_cities_above_other_locations(self):
        jobs = [{'location': 'Bangalore', 'relevance': 1000},
                {'location': 'Vellore', 'relevance': 5},
                {'location': 'Chennai', 'relevance': 10}]
        self.assertEqual([j['location'] for j in discovery.rank_jobs(jobs)], ['Chennai', 'Vellore', 'Bangalore'])

    def test_description_does_not_create_city_priority(self):
        jobs = [{'location': 'Bangalore', 'description': 'Chennai office', 'relevance': 100},
                {'location': 'Vellore', 'relevance': 1}]
        self.assertEqual(discovery.rank_jobs(jobs)[0]['location'], 'Vellore')

    def test_radar_accepts_puducherry_without_calling_it_tamil_nadu(self):
        valid, tier, _, is_tn = job_radar.classify_location('Pondicherry, India')
        self.assertTrue(valid)
        self.assertEqual(tier, 1)
        self.assertFalse(is_tn)
        self.assertEqual(job_radar.classify_location('Thiruannamalai')[1], 1)

    def test_cached_pagination_is_ranked_and_alias_aware(self):
        jobs = [{'title': 'Developer', 'location': 'Coimbatore', 'date_posted': '2026-10-05'},
                {'title': 'Developer', 'location': 'Puducherry', 'date_posted': '2026-10-04'}]
        results, total = job_radar._filter_and_paginate_tn_jobs(jobs, limit=1)
        self.assertEqual(results[0]['location'], 'Puducherry')
        self.assertEqual(total, 2)
        results, total = job_radar._filter_and_paginate_tn_jobs(jobs, city='pondicherry')
        self.assertEqual(total, 1)

    def test_all_four_cities_are_queried_and_urls_deduplicated(self):
        calls = []
        def fetch(query, location, limit):
            calls.append((query, location))
            return [{'role': 'Developer', 'location': location, 'link': 'https://example.com/job?utm_source=' + location}]
        jobs = discovery.fetch_priority_search('python', [fetch], timeout=2)
        self.assertEqual({location for _, location in calls}, {f'{city}, India' for city in discovery.PRIORITY_CITIES})
        self.assertEqual(len(jobs), 1)

    def test_explicit_city_search_strips_alias_and_filters_wrong_city(self):
        calls = []
        def fetch(query, location, limit):
            calls.append((query, location))
            return [{'location': 'Chennai', 'link': 'https://example.com/wrong'},
                    {'location': 'Puducherry', 'link': 'https://example.com/right'}]
        jobs = discovery.fetch_priority_search('python pondicherry', [fetch], timeout=2)
        self.assertEqual(calls, [('python', 'Puducherry, India')])
        self.assertEqual(jobs[0]['link'], 'https://example.com/right')
        self.assertEqual(len(jobs), 1)

    def test_live_queries_run_even_when_local_results_are_full(self):
        live = [{'company': 'Local Employer', 'role': 'Python Developer', 'location': 'Vellore',
                 'link': 'https://example.com/live', 'relevance': 20}]
        cached = [{'role': 'Python Developer', 'company': 'Cached Employer', 'city': 'Coimbatore',
                   'id': 'cached', 'google_maps': 'https://example.com/cached'}]
        with patch.object(discovery, 'fetch_priority_search', return_value=live) as fetch, \
             patch.object(bot_optimizer, 'get_walkin_drives', return_value=cached), \
             patch.object(bot_optimizer, 'get_national_drives', return_value=[]), \
             patch.object(bot_optimizer, 'get_tn_scraped_live_jobs', return_value=[]), \
             patch.object(job_radar, 'get_tamil_nadu_jobs', return_value=[]):
            results = bot_optimizer.search_jobs_multi_source('python', limit=1)['results']
        fetch.assert_called_once()
        self.assertEqual(results[0]['location'], 'Vellore')

    def test_priority_jobspy_queries_run_before_nationwide_queries(self):
        scrape = Mock(return_value=None)
        with patch.dict('sys.modules', {'jobspy': Mock(scrape_jobs=scrape)}), patch.object(job_radar.time, 'sleep'):
            job_radar.scrape_jobspy()
        locations = [c.kwargs['location'] for c in scrape.call_args_list]
        self.assertEqual(locations[:4], [f'{city}, India' for city in discovery.PRIORITY_CITIES])
        self.assertIn('India', locations)


class AutomaticSearchTests(unittest.TestCase):
    def test_hourly_default_and_safe_config_range(self):
        self.assertEqual(discovery.automatic_search_interval_minutes('60'), 60)
        self.assertEqual(discovery.automatic_search_interval_minutes('invalid'), 60)
        self.assertEqual(discovery.automatic_search_interval_minutes('0'), 15)
        self.assertEqual(discovery.automatic_search_interval_minutes('9999'), 1440)
        with patch.dict(os.environ, {'AUTO_SEARCH_INTERVAL_MINUTES': '120'}):
            self.assertEqual(discovery.automatic_search_interval_minutes(), 120)

    def test_automatic_delivery_filters_seen_jobs_and_marks_after_send(self):
        bot = Mock()
        jobs = [{'title': 'Developer', 'location': 'Vellore', 'link': 'https://example.com/seen'},
                {'title': 'Developer', 'location': 'Puducherry', 'link': 'https://example.com/new'}]
        with patch.object(job_radar, 'get_tamil_nadu_jobs', return_value=jobs) as fetch, \
             patch.object(job_radar, 'load_seen_jobs', return_value={'https://example.com/seen'}), \
             patch.object(job_radar.os.path, 'exists', return_value=False), \
             patch.object(job_radar, 'format_tamil_nadu_telegram_digest', return_value=(['test alert'], None)), \
             patch.object(job_radar, 'mark_seen') as mark, \
             patch.object(job_radar.time, 'sleep'):
            sent = job_radar.dispatch_tamil_nadu_alerts(bot=bot, chat_id=123, force_refresh=True, only_unseen=True)
        self.assertEqual(sent, 1)
        fetch.assert_called_once_with(limit=50, force_refresh=True)
        bot.send_message.assert_called_once()
        self.assertEqual(bot.send_message.call_args.args[0], 123)
        mark.assert_called_once_with('https://example.com/new')

    def test_failed_automatic_delivery_does_not_mark_jobs_seen(self):
        bot = Mock()
        bot.send_message.side_effect = RuntimeError('Telegram unavailable')
        with patch.object(job_radar, 'get_tamil_nadu_jobs', return_value=[{'link': 'https://example.com/new'}]), \
             patch.object(job_radar, 'load_seen_jobs', return_value=set()), \
             patch.object(job_radar.os.path, 'exists', return_value=False), \
             patch.object(job_radar, 'format_tamil_nadu_telegram_digest', return_value=(['test alert'], None)), \
             patch.object(job_radar, 'mark_seen') as mark:
            with self.assertRaises(RuntimeError):
                job_radar.dispatch_tamil_nadu_alerts(bot=bot, chat_id=123, only_unseen=True)
        mark.assert_not_called()

    def test_cloud_priority_search_precedes_channel_scraping(self):
        filename = os.path.join(os.path.dirname(__file__), 'cloud_runner.py')
        with open(filename, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_cloud')
        lines = {}
        for call in ast.walk(fn):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                lines.setdefault(call.func.id, call.lineno)
        self.assertLess(lines['dispatch_tamil_nadu_alerts'], lines['scrape_single_channel'])

    def test_running_bot_searches_and_sends_without_manual_command(self):
        filename = os.path.join(os.path.dirname(__file__), 'main.py')
        with open(filename, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'radar_loop')
        class EndLoop(BaseException):
            pass
        def sleep(seconds):
            if seconds == 5:
                raise EndLoop()
        namespace = {'automatic_search_interval_minutes': lambda: 60,
                     'print': Mock(), 'time': Mock(sleep=sleep), 'BOT_PAUSED': False,
                     'load_chat_id': lambda: 123, 'bot': Mock()}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), filename, 'exec'), namespace)
        with patch.object(job_radar, 'dispatch_tamil_nadu_alerts', return_value=1) as dispatch, \
             patch.object(job_radar, 'run_radar', return_value=[]), \
             patch.object(bot_optimizer, 'dispatch_walkin_alerts'):
            with self.assertRaises(EndLoop):
                namespace['radar_loop']()
        dispatch.assert_called_once_with(bot=namespace['bot'], chat_id=123, limit=6, force_refresh=True, only_unseen=True)
        self.assertIn('60 minutes', namespace['bot'].send_message.call_args.args[1])


class CardAndReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'state.json')
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=discovery.IST)
        self.job = {'id': 'test_walkin', 'company': 'Example & Co', 'role': 'Developer',
                    'city': 'Vellore', 'event_start': '2026-10-06T09:00:00+05:30',
                    'source_url': 'https://example.com/job?a=1&b=2',
                    'registration_link': 'https://example.com/job'}

    def tearDown(self):
        self.temp.cleanup()

    def test_card_escapes_html_and_labels_unverified_source(self):
        text = discovery.compact_walkin(self.job)
        self.assertIn('Example &amp; Co', text)
        self.assertIn('Unconfirmed', text)
        self.assertIn('06 Oct 2026', text)
        self.assertIn('a=1&amp;b=2', text)
        self.assertIn('Not recorded', text)

    def test_verified_feed_name_is_not_employer_confirmation(self):
        text = discovery.source_lines({'source': 'Verified official feed'})
        self.assertIn('Unconfirmed', text)
        self.assertNotIn('Employer-confirmed', text)
        confirmed = discovery.source_lines({'verification_status': 'confirmed', 'verified_at': '2026-10-04'})
        self.assertIn('Employer-confirmed', confirmed)

    def test_relative_date_cannot_schedule(self):
        job = dict(self.job, event_start='', timing='Upcoming Saturday')
        self.assertIsNone(discovery.event_start(job))
        self.assertIn('not set', discovery.schedule_reminder(1, job, now=self.now, path=self.path))
        self.assertFalse(os.path.exists(self.path))

    def test_date_only_requires_reporting_time(self):
        job = dict(self.job, event_start='', walkin_date='2026-10-06')
        self.assertIsNone(discovery.event_start(job))
        self.assertIn('06 Oct 2026', discovery.event_label(job))
        job['reporting_time'] = '09:30'
        self.assertEqual(discovery.event_start(job).hour, 9)
        self.assertEqual(discovery.event_start(job).minute, 30)

    def test_invalid_or_expired_events_are_rejected(self):
        self.assertIsNone(discovery.event_start({'event_start': '2026-99-99'}))
        job = dict(self.job, event_start='2026-10-03T09:00:00+05:30')
        self.assertIn('expired', discovery.schedule_reminder(1, job, now=self.now, path=self.path))

    def test_reminder_persists_and_delivers_once(self):
        discovery.schedule_reminder(1, self.job, now=self.now, path=self.path)
        self.assertEqual(len(discovery.list_reminders(1, path=self.path)), 1)
        bot = Mock()
        discovery.dispatch_due_reminders(bot, now=self.now, path=self.path)
        bot.send_message.assert_not_called()
        due = self.now + timedelta(days=1)
        discovery.dispatch_due_reminders(bot, now=due, path=self.path)
        discovery.dispatch_due_reminders(bot, now=due, path=self.path)
        bot.send_message.assert_called_once()
        self.assertEqual(discovery.list_reminders(1, path=self.path), [])

    def test_repeated_click_does_not_reset_delivered_reminder(self):
        discovery.schedule_reminder(1, self.job, now=self.now, path=self.path)
        self.assertIn('already', discovery.schedule_reminder(1, self.job, now=self.now, path=self.path))
        self.assertEqual(len(discovery.list_reminders(1, path=self.path)), 1)

    def test_failed_delivery_retries(self):
        discovery.schedule_reminder(1, self.job, now=self.now, path=self.path)
        bot = Mock()
        bot.send_message.side_effect = RuntimeError('Telegram offline')
        with self.assertLogs(level='ERROR'):
            discovery.dispatch_due_reminders(bot, now=self.now + timedelta(days=1), path=self.path)
        self.assertEqual(len(discovery.list_reminders(1, path=self.path)), 1)
        bot.send_message.side_effect = None
        discovery.dispatch_due_reminders(bot, now=self.now + timedelta(days=1), path=self.path)
        self.assertEqual(discovery.list_reminders(1, path=self.path), [])

    def test_cancel_is_chat_scoped(self):
        for chat_id in (1, 2):
            discovery.schedule_reminder(chat_id, self.job, now=self.now, path=self.path)
        discovery.cancel_reminders(1, path=self.path)
        self.assertEqual(discovery.list_reminders(1, path=self.path), [])
        self.assertEqual(len(discovery.list_reminders(2, path=self.path)), 1)

    def test_missed_expired_reminder_is_not_sent(self):
        discovery.schedule_reminder(1, self.job, now=self.now, path=self.path)
        bot = Mock()
        discovery.dispatch_due_reminders(bot, now=self.now + timedelta(days=3), path=self.path)
        bot.send_message.assert_not_called()
        self.assertEqual(discovery.list_reminders(1, path=self.path), [])

    def test_calendar_is_utc_and_folded_at_75_bytes(self):
        job = dict(self.job, company='测试' * 60 + '\nInjected line')
        data = discovery.calendar_event(job, now=self.now)
        self.assertIn(b'DTSTART:20261006T033000Z', data)
        self.assertIn(b'BEGIN:VCALENDAR', data)
        self.assertTrue(all(len(line) <= 75 for line in data.split(b'\r\n')))
        self.assertNotIn(b'\r\nInjected line', data)

    def test_buttons_have_safe_callback_lengths_and_persist_card(self):
        with patch.object(discovery, 'STATE_FILE', self.path):
            markup = discovery.walkin_keyboard(self.job)
            callbacks = [b['callback_data'] for row in markup.to_dict()['inline_keyboard'] for b in row if 'callback_data' in b]
            self.assertTrue(all(len(c.encode()) <= 64 for c in callbacks))
            key = callbacks[0].split(':')[-1]
            self.assertEqual(discovery.get_card(key)['company'], self.job['company'])
            self.assertTrue(any('calendar' in c for c in callbacks))

    def test_compact_delivery_uses_individual_action_buttons(self):
        bot = Mock()
        job = dict(self.job, event_start='2099-10-06T09:00:00+05:30')
        with patch.object(discovery, 'STATE_FILE', self.path), patch.object(discovery.time, 'sleep'):
            discovery.send_walkin_cards(bot, 1, [job])
        bot.send_message.assert_called_once()
        args, kwargs = bot.send_message.call_args
        self.assertIn('Source:', args[1])
        self.assertIn('reply_markup', kwargs)
        self.assertNotIn('SELECTION PROCESS', args[1])

    def test_known_expired_walkin_is_not_posted(self):
        bot = Mock()
        job = dict(self.job, event_start='2000-10-06T09:00:00+05:30')
        discovery.send_walkin_cards(bot, 1, [job])
        bot.send_message.assert_not_called()

    def test_link_check_timestamp_is_not_employer_confirmation(self):
        text = discovery.source_lines({'source_checked_at': '2026-10-04T09:00:00+05:30'})
        self.assertIn('Link checked', text)
        self.assertIn('not employer confirmation', text)
        self.assertIn('Unconfirmed', text)

    def test_search_report_labels_sources_and_has_city_buttons(self):
        job = {'company': 'Example', 'role': 'Python Developer', 'location': 'Vellore',
               'source_type': 'Verified source', 'link': 'https://example.com/job?a=1&b=2'}
        chunks, markup = bot_optimizer.format_search_results_report('python', [job])
        self.assertIn('Unconfirmed', chunks[0])
        self.assertIn('a=1&amp;b=2', chunks[0])
        callbacks = [b['callback_data'] for row in markup.to_dict()['inline_keyboard'] for b in row if 'callback_data' in b]
        for city in ('tiruvannamalai', 'vellore', 'puducherry', 'chennai'):
            self.assertIn('search:' + city, callbacks)

    def test_missing_publication_date_stays_unknown(self):
        job = job_radar._make_job('Developer', 'Employer', 'https://example.com', 'Vellore', 'Portal')
        self.assertEqual(job['date_posted'], '')
        self.assertIn('found_at', job)


class SearchQualityTests(unittest.TestCase):
    """Match-quality and paging regressions for the multi-source search."""

    def _patch_sources(self, jobs):
        return (
            patch.object(discovery, 'fetch_priority_search', return_value=list(jobs)),
            patch.object(bot_optimizer, 'get_walkin_drives', return_value=[]),
            patch.object(bot_optimizer, 'get_national_drives', return_value=[]),
            patch.object(bot_optimizer, 'get_tn_scraped_live_jobs', return_value=[]),
            patch.object(bot_optimizer, 'fetch_live_adzuna_search', return_value=[]),
            patch.object(bot_optimizer, 'fetch_jobspy_live_search', return_value=[]),
            patch.object(bot_optimizer, 'fetch_simplify_jobs', return_value=[]),
            patch.object(job_radar, 'get_tamil_nadu_jobs', return_value=[]),
        )

    def _search(self, jobs, query, **kwargs):
        patches = self._patch_sources(jobs)
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return bot_optimizer.search_jobs_multi_source(query, **kwargs)

    def test_exact_title_and_company_outrank_description_only(self):
        jobs = [
            {'role': 'Sales Executive', 'company': 'Acme', 'location': 'Chennai',
             'link': 'https://example.com/sales', 'snippet': 'Python skills a plus'},
            {'role': 'Python Developer', 'company': 'Zoho', 'location': 'Chennai',
             'link': 'https://example.com/python', 'snippet': 'Build APIs'},
        ]
        result = self._search(jobs, 'python', limit=5)
        # Real title match ranks above an incidental description mention.
        self.assertEqual(result['results'][0]['link'], 'https://example.com/python')
        self.assertGreater(result['results'][0]['relevance'], result['results'][1]['relevance'])

    def test_typo_query_still_matches_python(self):
        jobs = [{'role': 'Python Developer', 'company': 'Acme', 'location': 'Vellore',
                 'link': 'https://example.com/py', 'snippet': 'Backend'}]
        result = self._search(jobs, 'pyhton', limit=5)
        self.assertEqual(len(result['results']), 1)

    def test_synonym_query_matches_related_role(self):
        # "frontend" is absent from the listing; only the synonym (react) matches.
        jobs = [{'role': 'React Developer', 'company': 'Acme', 'location': 'Chennai',
                 'link': 'https://example.com/fe', 'snippet': 'Build web UI'}]
        result = self._search(jobs, 'frontend', limit=5)
        self.assertEqual(len(result['results']), 1)
        self.assertNotIn('frontend', (jobs[0]['role'] + jobs[0]['snippet']).lower())

    def test_pages_are_disjoint_and_has_more_flips(self):
        jobs = [
            {'role': f'Python Developer {i}', 'company': 'Acme', 'location': 'Chennai',
             'link': f'https://example.com/j{i}', 'snippet': 'python'}
            for i in range(5)
        ]
        first = self._search(jobs, 'python', limit=2, page=0)
        second = self._search(jobs, 'python', limit=2, page=1)
        self.assertTrue(first['has_more'])
        self.assertTrue(second['has_more'])
        self.assertEqual(first['page'], 0)
        self.assertEqual(second['page'], 1)
        first_links = {j['link'] for j in first['results']}
        second_links = {j['link'] for j in second['results']}
        self.assertFalse(first_links & second_links)
        self.assertEqual(len(first['results']), 2)

    def test_last_page_reports_no_more(self):
        jobs = [
            {'role': f'Python Developer {i}', 'company': 'Acme', 'location': 'Chennai',
             'link': f'https://example.com/j{i}', 'snippet': 'python'}
            for i in range(3)
        ]
        last = self._search(jobs, 'python', limit=2, page=1)
        self.assertEqual(len(last['results']), 1)
        self.assertFalse(last['has_more'])
        self.assertEqual(last['total_available'], 3)

    def test_search_more_button_hashed_and_absent_on_last_page(self):
        jobs = [{'role': 'Python Developer', 'company': 'Acme', 'location': 'Chennai',
                 'link': 'https://example.com/py', 'snippet': 'python'}]
        long_query = 'python developer chennai remote senior immediate joiner'
        chunks, markup = bot_optimizer.format_search_results_report(
            long_query, jobs, page=0, has_more=True,
        )
        buttons = markup.to_dict()['inline_keyboard']
        callbacks = [b['callback_data'] for row in buttons for b in row if 'callback_data' in b]
        self.assertTrue(all(len(c.encode()) <= 64 for c in callbacks))
        more = [c for c in callbacks if c.startswith('search_more:')]
        self.assertTrue(more)
        # The hashed key resolves back to the original query.
        qkey = more[0].split(':')[1]
        self.assertEqual(bot_optimizer.get_search_query(qkey), long_query)

        _, last_markup = bot_optimizer.format_search_results_report(long_query, jobs, page=3, has_more=False)
        last_callbacks = [b.get('callback_data') for row in last_markup.to_dict()['inline_keyboard'] for b in row]
        self.assertFalse(any((c or '').startswith('search_more:') for c in last_callbacks))

    def test_refresh_button_stays_within_callback_limit(self):
        jobs = [{'role': 'Python Developer', 'company': 'Acme', 'location': 'Chennai',
                 'link': 'https://example.com/py', 'snippet': 'python'}]
        long_query = 'x' * 200
        _, markup = bot_optimizer.format_search_results_report(long_query, jobs, has_more=True)
        callbacks = [b['callback_data'] for row in markup.to_dict()['inline_keyboard'] for b in row if 'callback_data' in b]
        self.assertTrue(all(len(c.encode()) <= 64 for c in callbacks))


if __name__ == '__main__':
    unittest.main()
