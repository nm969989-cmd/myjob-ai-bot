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

if __name__=='__main__':unittest.main()
