"""Offline query-cost/delivery regression fixtures; no token or production bot."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import engineering_telegram as e
from test_engineering_telegram import job, result

class OptimizationTests(unittest.TestCase):
    def test_batch_one_process_profiles_only_on_stdin(self):
        profiles=[dict(e.DEFAULT) for _ in range(4)]
        with patch.object(e.subprocess,'run',return_value=Mock(stdout=json.dumps([result()] * 4))) as run:
            self.assertEqual(len(e.query_batch(profiles)),4)
        self.assertEqual(run.call_count,1)
        args,kw=run.call_args
        self.assertEqual(args[0][-1],'--query-batch')
        self.assertNotIn('configured',' '.join(args[0]))
        self.assertEqual(json.loads(kw['input'])['profiles'],profiles)
        self.assertTrue(kw['check'])
    def test_bad_batch_shape_rejected(self):
        with patch.object(e.subprocess,'run',return_value=Mock(stdout='[]')):
            with self.assertRaises(ValueError): e.query_batch([dict(e.DEFAULT)])
    def test_four_searches_one_batch_and_per_send_ack(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e,'STATE',Path(tmp)/'state.json'):
            state=e.load_state();state['searches']={f's{i}':{'role':'python','city':'Chennai'} for i in range(4)};e.save_state(state)
            bot=Mock();bot.send_message.side_effect=[None,RuntimeError('fixture failed')]
            with patch.object(e,'query_batch',return_value=[result([job(1)])]*4) as batch:
                with self.assertRaises(RuntimeError): e.dispatch(bot,'123')
            self.assertEqual(batch.call_count,1)
            self.assertEqual(len(batch.call_args.args[0]),4)
            after=e.load_state()
            self.assertIn('s0',after['seen']);self.assertNotIn('s1',after['seen'])
    def test_repeated_snapshot_quiet_and_integrity_upgrade_delivered(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e,'STATE',Path(tmp)/'state.json'):
            bot=Mock()
            uncertain={**job(1),'match':{'integrity':'uncertain','score':50}}
            with patch.object(e,'query_batch',return_value=[result([uncertain])]):
                self.assertEqual(e.dispatch(bot,'123'),1)
                self.assertEqual(e.dispatch(bot,'123'),0)
            with patch.object(e,'query_batch',return_value=[result([job(1)])]):
                self.assertEqual(e.dispatch(bot,'123'),1)
                self.assertEqual(e.dispatch(bot,'123'),0)
            self.assertEqual(bot.send_message.call_count,2)
            self.assertEqual(set(e.load_state()['seen']['default']),{'1:uncertain','1:verified'})
    def test_profile_error_keeps_prior_success_and_stops_in_order(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e,'STATE',Path(tmp)/'state.json'):
            state=e.load_state();state['searches']={'ok':{},'bad':{}};e.save_state(state)
            bot=Mock()
            with patch.object(e,'query_batch',return_value=[result([job(1)]),{'error':'fixture invalid city'}]):
                with self.assertRaises(ValueError): e.dispatch(bot,'123')
            self.assertEqual(bot.send_message.call_count,1)
            self.assertIn('ok',e.load_state()['seen'])
            self.assertNotIn('bad',e.load_state()['seen'])

if __name__=='__main__': unittest.main()
