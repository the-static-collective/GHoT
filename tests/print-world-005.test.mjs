#!/usr/bin/env node
import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyHeld,printQuestInbox} from '../ghot/public_print_world_005.mjs';
const copy=x=>structuredClone(x);
function fixture(){
 return {
   schema:'ghot.public-print-handoff-004/v0',
   state:'PREPARED_LOCAL_HANDOFF_R3_HOLD',
   packet_id:'ghot-print-venue-004:'+'a'.repeat(64),
   local_pdf_sha256:'b'.repeat(64),local_pdf_bytes:454,
   venue_kind:'LIBRARY_PUBLIC',venue_ref:'local:public-library-001',
   source_ref:'local:test-pdf-001',
   pdf_preflight:{pages:2,media_boxes_pt:[{width:612,height:792}]},
   print_intent:{copies:1,sensitivity:'PUBLIC'},
   machine_vendor_and_model_verified:false,
   venue_capabilities_and_fees_verified:false,
   native_relatte_owner_admitted:false,
   actual_print_order_submitted:false,
   document_data_uploaded:false,emails_sent:0,network_requests:0,
   payment_taken:false,retrieval_code_issued:false,
   paper_consumed:0,pages_physically_printed:0,
   physical_copies_collected:0,external_vendor_receipt_obtained:false
 };
}
test('Full Measure quest remains optional, proposal-only and source pinned',()=>{
  const q=printQuestInbox(fixture());
  assert.equal(q.schema,'static.field-test-inbox/v0');
  const [e]=q.entries;
  assert.equal(e.status,'PHYSICAL_UNVERIFIED');
  assert.equal(e.condition,'READY_FOR_FIELD_TEST');
  assert.equal(e.source_commit,'f62d8f2ae9a9077430bc1ef6fc4a17ea00f2affd');
  assert.match(e.id,/^public-print-/);
  assert.ok(!JSON.stringify(e).includes('private_key'));
});
test('distinct venues yield distinct bounded human questions',()=>{
  for(const venue of ['LIBRARY_PUBLIC','XEROX_MFP','FEDEX_OFFICE']){
    const f=fixture();f.venue_kind=venue;
    assert.equal(printQuestInbox(f).entries[0].status,'PHYSICAL_UNVERIFIED');
  }
});
test('private job must not leak into Full Measure public quest',()=>{
  const f=fixture();f.print_intent.sensitivity='PRIVATE';
  assert.throws(()=>printQuestInbox(f),/PRIVATE_DOCUMENT_MAY_NOT_BECOME_PUBLIC_QUEST/);
});
test('forged printer starts, paid job or physical collection rejected',()=>{
  for(const [name,value] of [
    ['actual_print_order_submitted',true],
    ['document_data_uploaded',true],['network_requests',1],
    ['emails_sent',1],['payment_taken',true],['retrieval_code_issued',true],
    ['paper_consumed',1],['pages_physically_printed',2],
    ['physical_copies_collected',1],['native_relatte_owner_admitted',true],
    ['external_vendor_receipt_obtained',true],
    ['machine_vendor_and_model_verified',true],
    ['venue_capabilities_and_fees_verified',true]
  ]){
    const f=fixture();f[name]=value;
    assert.throws(()=>verifyHeld(f),/FORGED_PRINT_PAYMENT_OR_PHYSICAL_EFFECT/,name);
  }
});
test('PDF page count, target and packet fingerprint remain mandatory',()=>{
 for(const [k,v] of [['packet_id','bogus'],['local_pdf_sha256','oops'],
                      ['source_ref','../../oops'],['venue_kind','PRINT_ANYTHING']]){
   const f=fixture();f[k]=v;
   assert.throws(()=>verifyHeld(f));
 }
 for(const pages of [-1,0,251,1.4]){
   const f=fixture();f.pdf_preflight.pages=pages;
   assert.throws(()=>verifyHeld(f),/NATIVE_PDF_PREFLIGHT_REQUIRED/);
 }
});
test('unbounded copies and confidentiality label fail',()=>{
  const f=fixture();f.print_intent.copies=2000000;
  assert.throws(()=>verifyHeld(f),/BOUNDED_PRINT_INTENT_REQUIRED/);
  f.print_intent.copies=1;f.print_intent.sensitivity='RESTRICTED';
  assert.throws(()=>verifyHeld(f),/BOUNDED_PRINT_INTENT_REQUIRED/);
});
test('unexpected source status fails closed',()=>{
 const f=fixture();f.state='PAGES_PHYSICALLY_PRINTED';
 assert.throws(()=>verifyHeld(f),/SOURCE_NOT_PREPARED_AND_HELD/);
});
