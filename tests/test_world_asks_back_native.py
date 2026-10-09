#!/usr/bin/env python3
"""Cross-repository native reLATTE and GHoT WORLD-ASKS-BACK-002 gates."""
from __future__ import annotations
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ghot'))
import world_asks_back_native as native
from relatte_identity import IdentityKey

RELATTE_ROOT = os.getenv("RELATTE_ROOT", "")
GHOT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(mode: str):
    completed = subprocess.run(
        [sys.executable, str(GHOT_ROOT / 'ghot' / 'world_asks_back_native.py'),
         mode, RELATTE_ROOT], cwd=GHOT_ROOT, capture_output=True, text=True, timeout=90)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


@unittest.skipUnless(RELATTE_ROOT and (Path(RELATTE_ROOT) / "scripts" / "wab-receiver.ts").is_file(),
                     "Native reLATTE receiver checkout required")
class NativeWorkshopTests(unittest.TestCase):
    def test_native_real_hash_requires_local_admission(self):
        output = run_cli('demo')
        self.assertEqual(output['status'], 'NATIVE_LOCAL_HASH_EXECUTED')
        self.assertEqual(output['receiver_receive']['kind'], 'RECEIVED')
        self.assertEqual(output['receiver_admit']['kind'], 'R3_ADMIT')
        self.assertEqual(output['result']['status'], 'NATIVE_LOCAL_HASH_EXECUTED')
        self.assertFalse(output['result']['physical_part_produced'])
        self.assertEqual(output['result']['economic_credit'], 0)

    def test_no_consent_stays_native_held(self):
        output = run_cli('hold')
        self.assertEqual(output['status'], 'HOLD')
        self.assertIsNone(output['execution'])
        self.assertEqual(output['disposition_receipt']['kind'], 'R3_HOLD')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proposal, self.pins, self.keys = native.fixture(self.root / 'owners')
        self.offer = {'capability': 'system.hash', 'available': True,
                      'limits': {'remote_shell': False, 'bounded_adapter_only': True}}
        self.receiver = self.root / 'receiver'
        self.boot = native.receiver_call(Path(RELATTE_ROOT), {
            'schema': 'relatte.wab-native-request/v0', 'action': 'init',
            'receiver_root': str(self.receiver),
            'trusted_pins': self.pins, 'proposal': self.proposal,
        })
        self.crossing = native.signed_native_crossing(
            self.proposal, self.offer, self.keys['household'])
        self.grants = native.native_grants(self.crossing, self.proposal, self.keys)

    def submit(self, grants=None, crossing=None):
        return native.submit(Path(RELATTE_ROOT), self.receiver, self.proposal,
                             crossing if crossing is not None else self.crossing,
                             self.grants if grants is None else grants)

    def test_cold_replay_idempotent_and_native_pinned(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first['status'], 'ADMITTED_FOR_LOCAL_HASH')
        self.assertEqual(first['receive_receipt']['receipt_id'], second['receive_receipt']['receipt_id'])
        self.assertEqual(first['disposition_receipt']['receipt_id'], second['disposition_receipt']['receipt_id'])
        native.validate_native_admission(first, self.crossing, self.boot['receiver_public_key'])
        with self.assertRaisesRegex(ValueError, 'NOT_PINNED'):
            native.validate_native_admission(first, self.crossing,
              IdentityKey.load_or_create(self.root / 'imposter.pem').public_jwk())

    def test_missing_grants_signed_hold_not_work(self):
        res = self.submit(grants={})
        self.assertEqual(res['status'], 'HELD_NO_CONSENT')
        self.assertEqual(res['disposition_receipt']['kind'], 'R3_HOLD')
        with self.assertRaisesRegex(ValueError, 'NOT_ADMITTED'):
            native.validate_native_admission(res, self.crossing, self.boot['receiver_public_key'])
        # Cannot upgrade the terminal HOLD into an ADMIT by resending same crossing.
        with self.assertRaises(RuntimeError):
            self.submit()

    def test_partial_grants_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'WAB_PARTIAL_OR_EXTRA_GRANTS'):
            self.submit(grants={r: self.grants[r] for r in ('household','fabricator')})

    def test_wrong_role_and_scope_rejected(self):
        g = copy.deepcopy(self.grants)
        g['fabricator']['scope'] = 'unlimited-printer-access'
        with self.assertRaisesRegex(RuntimeError, 'WAB_GRANT_SCOPE_OR_PIN_FAILURE'):
            self.submit(grants=g)

    def test_wrong_key_and_signature_rejected(self):
        g = copy.deepcopy(self.grants)
        g['fabricator']['signature'] = g['stockist']['signature']
        with self.assertRaisesRegex(RuntimeError, 'WAB_BAD_GRANT_SIGNATURE'):
            self.submit(grants=g)

    def test_expired_grant_rejected(self):
        g = copy.deepcopy(self.grants)
        g['stockist']['expires_at'] = '2020-01-01T00:00:00.000Z'
        with self.assertRaisesRegex(RuntimeError, 'WAB_GRANT_SCOPE_OR_PIN_FAILURE'):
            self.submit(grants=g)

    def test_intent_expansion_rejected(self):
        crossing = copy.deepcopy(self.crossing)
        crossing['requested_effect'] = {'action': 'make-physical-print'}
        with self.assertRaisesRegex(RuntimeError, 'WAB_INVALID_SIGNED_CROSSING'):
            self.submit(crossing=crossing)

    def test_native_bridge_rejects_rogue_crossing_source(self):
        keys = {r: IdentityKey.load_or_create(self.root / ('rogue-' + r + '.pem'))
                for r in ('household','fabricator','stockist')}
        crossing = native.signed_native_crossing(self.proposal, self.offer, keys['household'])
        with self.assertRaisesRegex(RuntimeError, 'WAB_CROSSING_NOT_BOUND_TO_PINNED_INTENT'):
            self.submit(crossing=crossing)

    def test_stale_offer_denied_before_execution(self):
        admitted = self.submit()
        fake = {'offers':[self.offer]}
        withdrawn = copy.deepcopy(self.offer)
        withdrawn['available'] = False
        called = []
        with self.assertRaisesRegex(ValueError, 'WITHDRAWN'):
            native.execute_authorized_hash(
                self.proposal, self.crossing, admitted, self.offer,
                body_fn=lambda: {'offers':[withdrawn]},
                execute_fn=lambda *a, **kw: called.append(a),
                node_key=self.keys['fabricator'],
                trusted_receiver_key=self.boot['receiver_public_key'])
        self.assertEqual(called, [])

    def test_different_current_offer_denied_before_execution(self):
        admitted = self.submit()
        changed = copy.deepcopy(self.offer)
        changed['limits']['bounded_adapter_only'] = False
        called = []
        with self.assertRaisesRegex(ValueError, 'NATIVE_OFFER_CHANGED_BEFORE_EXECUTION'):
            native.execute_authorized_hash(
                self.proposal, self.crossing, admitted, self.offer,
                body_fn=lambda: {'offers':[changed]},
                execute_fn=lambda *a, **kw: called.append(a),
                node_key=self.keys['fabricator'],
                trusted_receiver_key=self.boot['receiver_public_key'])
        self.assertEqual(called, [])

    def test_forged_receiver_disposition_rejected(self):
        admitted = self.submit()
        forged = copy.deepcopy(admitted)
        forged['disposition_receipt']['kind'] = 'R3_ADMIT_SUPER'
        with self.assertRaisesRegex(ValueError, 'NATIVE_SIGNED_RECEIPT_INVALID'):
            native.validate_native_admission(forged, self.crossing,
                                            self.boot['receiver_public_key'])


if __name__ == '__main__':
    unittest.main()
