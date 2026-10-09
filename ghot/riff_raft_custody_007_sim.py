#!/usr/bin/env python3
"""007 regression suite: mirror, source signatures, local custody signature guards."""
import copy
import unittest
from pathlib import Path
from riff_raft_custody_007 import (
    CustodyHold,SOURCE_SHA256,custody_statement,load_evidence,sign_statement,
    verify_local_receipt
)

ROOT=Path(__file__).resolve().parent.parent
MIRROR=ROOT/"fixtures/riff-raft-007/signed-005-return.bundle.json"


class CustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original,_=load_evidence(MIRROR)
    def test_source_is_pinned_and_full_ancestry_is_verified(self):
        self.assertGreater(len(self.original),100_000)
        s=custody_statement(MIRROR,"GHoT")
        self.assertEqual(s["source_full_bundle_sha256"],SOURCE_SHA256)
        self.assertEqual(s["signed_005_world_count"],2)
        self.assertTrue(s["source_004_and_005_signatures_reverified"])
        self.assertEqual(s["disposition"],"HOLD")
        self.assertFalse(s["administrative_independence_verified"])
    def test_ephemeral_local_receipt_is_verifiable_but_not_an_authority_grant(self):
        receipt=sign_statement(custody_statement(MIRROR,"GHoT"))
        self.assertTrue(verify_local_receipt(receipt,MIRROR,"GHoT"))
        self.assertFalse(receipt["statement"]["signer_is_org_trust_root"])
        self.assertFalse(receipt["statement"]["admission"])
    def test_role_alias_and_signature_changes_refuse(self):
        r=sign_statement(custody_statement(MIRROR,"GHoT"))
        with self.assertRaises(CustodyHold):
            verify_local_receipt(r,MIRROR,"reLATTE")
        bad=copy.deepcopy(r)
        bad["statement"]["admission"]=True
        with self.assertRaises(CustodyHold):
            verify_local_receipt(bad,MIRROR,"GHoT")
        bad=copy.deepcopy(r)
        bad["signing"]["signature"]="busted"
        with self.assertRaises(CustodyHold):
            verify_local_receipt(bad,MIRROR,"GHoT")
    def test_mirror_missing_is_never_inferred(self):
        with self.assertRaises(CustodyHold):
            load_evidence(ROOT/"fixtures/riff-raft-007/NOT-PRESENT.json")
    def test_no_unsanctioned_store_claims(self):
        with self.assertRaises(CustodyHold):
            custody_statement(MIRROR,"some-external-custodian")

if __name__=="__main__":
    unittest.main(verbosity=2)
