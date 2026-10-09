#!/usr/bin/env node
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {review,verifyGhot005,validateSelection} from '../ghot/print_work_review_006.mjs';

export function fakeGardenStore(source,status='confirmed'){
  const circle='circle-print006',projectId='project-print006',pledgeId='pledge-print006';
  const maker='person-maker006',steward='person-steward006';
  const times=[
    '2026-10-09T10:00:00.000Z',
    '2026-10-09T10:01:00.000Z',
    '2026-10-09T10:02:00.000Z',
    '2026-10-09T10:03:00.000Z'
  ];
  const kinds=['pledge.proposed','pledge.accepted','pledge.reported_complete','pledge.confirmed'];
  const actors=[maker,steward,maker,steward];
  const events=kinds.map((eventType,i)=>({
    id:'event-print006-'+i,circleId:circle,aggregateType:'pledge',
    aggregateId:pledgeId,eventType,actorId:actors[i],
    createdAt:times[i],
    payload:i===0?{projectId,description:'Deliver physical print of selected source'}:
      i===3?{projectId,pledgeId,pledgedBy:maker}:{projectId,pledgeId}
  })).slice(0,status==='confirmed'?4:3);
  // Fixture imitates fields of a local Full Measure store. It is NOT a
  // signed or real-world human confirmation.
  const project={
    id:projectId,circleId:circle,openedBy:steward,
    title:'Return with a printed page',story:'Proposed public print',
    locationNote:null,desiredDate:null,status:'active',
    needs:[],createdAt:times[0],completedAt:null
  };
  const pledge={
    id:pledgeId,projectId:project.id,needId:null,pledgedBy:maker,
    offerId:null,description:'Print and independently present the page',
    quantity:1,unit:'page',status,
    createdAt:times[0],acceptedAt:times[1],reportedCompleteAt:times[2],
    confirmedAt:status==='confirmed'?times[3]:null
  };
  const store={
    projects:[project],pledges:[pledge],domainEvents:events,
    circleMembers:[
      {circleId:circle,userId:maker,role:'member'},
      {circleId:circle,userId:steward,role:'steward'}
    ]
  };
  const selection={
    schema:'ghot.print-work-review-selection-006/v0',
    source_composition_id:source.composition_id,
    source_quest_id:source.full_measure_quest.quest_id,
    project_id:project.id,pledge_id:pledge.id,
    local_review_ref:'local-review:human-quest-006'
  };
  return {store,selection};
}
const ROOT=process.env.FM_DONOR_ROOT;
const PENNY=process.env.PENNY_DONOR_ROOT;
const SOURCE=process.env.GHOT_005_PROOF_PATH;
const enabled=!!ROOT&&!!PENNY&&!!SOURCE;
const clone=x=>structuredClone(x);
const source=enabled?JSON.parse(readFileSync(resolve(SOURCE),'utf8')):null;
const go=(data)=>review({source,fullMeasureRoot:ROOT,pennyRoot:PENNY,...data});

test('006 rejects source not linked to original GHoT held composition',()=>{
  if(!enabled)return;
  assert.equal(verifyGhot005(source).composition_id,source.composition_id);
  let forged=clone(source);
  forged.penny_work_candidate.pending_penny_units_created=1;
  assert.throws(()=>verifyGhot005(forged),/GHOT_COMPOSITION_SHA256_MISMATCH/);
  let bad=clone(source);
  bad.full_measure_hold_choice.disposition='ACCEPT';
  assert.throws(()=>verifyGhot005(bad));
});
test('006 exact source/quest/pledge selection cannot be arbitrarily rebound',()=>{
  if(!enabled)return;
  const {selection}=fakeGardenStore(source);
  assert.equal(validateSelection(selection,source).project_id,'project-print006');
  const fake=clone(selection);fake.source_quest_id='another-quest-id';
  assert.throws(()=>validateSelection(fake,source),/REVIEW_SOURCE_SELECTION_MISMATCH/);
});
test('real native Full Measure confirmed local record permits only PENNY review',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  const cut=await go({store,selection});
  assert.equal(cut.full_measure_local_record_state,'CONFIRMED_BY_LOCAL_STORE');
  assert.equal(cut.full_measure_sheet_deed_count,1);
  assert.equal(cut.penny_review.status,'REVIEW_ELIGIBLE_ONLY_NEEDS_INDEPENDENT_WORK_WITNESS');
  assert.equal(cut.penny_review.treasury_work_events_appended,0);
  assert.equal(cut.penny_review.work_quantity_authorized,0);
  assert.equal(cut.penny_review.coin_backing_deposits_verified,0);
  assert.equal(cut.penny_review.pending_penny_units_created,0);
  assert.equal(cut.penny_review.active_penny_units_issued,0);
  assert.equal(cut.native_penny_check.outstandingPennyUnits,0);
  assert.equal(cut.native_penny_check.boxBookCoinCount,0);
  assert.equal(cut.native_penny_check.sourceEventCount,0);
  assert.equal(cut.full_measure_human_identity_authenticated,false);
  assert.equal(cut.source_export_signature_verified,false);
  assert.equal(cut.actual_physical_print_independently_verified,false);
  assert.equal(cut.real_relatte_crossing,false);
});
test('unconfirmed report yields no Deed and no PENNY review-eligible state',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source,'reported_complete');
  const cut=await go({store,selection});
  assert.equal(cut.full_measure_sheet_deed_count,0);
  assert.equal(cut.full_measure_local_record_state,'REPORTED_NOT_CONFIRMED');
  assert.equal(cut.penny_review.status,'HOLD_UNCONFIRMED_FULL_MEASURE_REPORT');
  assert.equal(cut.penny_review.pending_penny_units_created,0);
});
test('self-confirmation cannot become a Deed or PENNY review',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  store.domainEvents[3].actorId=store.pledges[0].pledgedBy;
  await assert.rejects(go({store,selection}),/NATIVE_FULLMEASURE_ROLE_OR_TRANSITION_REFUSED_confirm/);
});
test('unrecognized confirming actor cannot self-promote to steward',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  store.domainEvents[3].actorId='person-unauthorized006';
  await assert.rejects(go({store,selection}),/NATIVE_FULLMEASURE_ROLE_OR_TRANSITION_REFUSED_confirm/);
});
test('missing confirmation but confirmed pledge state refuses',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  store.domainEvents.pop();
  await assert.rejects(go({store,selection}),/HISTORY_MISSING_OR_OUT_OF_ORDER/);
});
test('duplicate confirmation, forged branch history or vanished report refuses',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  store.domainEvents[2].eventType='pledge.withdrawn';
  await assert.rejects(go({store,selection}),/UNEXPECTED_OR_FOREIGN_PLEDGE_HISTORY/);
  const b=fakeGardenStore(source);
  b.store.domainEvents[3].id=b.store.domainEvents[2].id;
  await assert.rejects(go(b),/DUPLICATE_EVENT_ID/);
  const c=fakeGardenStore(source);
  c.store.domainEvents[2].eventType='pledge.confirmed';
  await assert.rejects(go(c),/EVENT_BENEFICIARY_CONTRADICTION/);
});
test('reordered and inconsistent Full Measure timestamps fail',async()=>{
  if(!enabled)return;
  const {store,selection}=fakeGardenStore(source);
  store.domainEvents[3].createdAt=store.domainEvents[1].createdAt;
  await assert.rejects(go({store,selection}),/HISTORY_MISSING_OR_OUT_OF_ORDER|EVENT_TIME_NON_MONOTONIC/);
  const b=fakeGardenStore(source);b.store.pledges[0].confirmedAt='2026-10-09T11:00:00.000Z';
  await assert.rejects(go(b),/PLEDGE_STATUS_TIMESTAMP_INCONSISTENT/);
});
test('cross-project event, false beneficiary, or missing member refuses',async()=>{
  if(!enabled)return;
  const a=fakeGardenStore(source);
  a.store.domainEvents[3].payload.pledgedBy='person-different006';
  await assert.rejects(go(a),/EVENT_BENEFICIARY_CONTRADICTION/);
  const b=fakeGardenStore(source);
  b.store.domainEvents[3].payload.projectId='project-foreign006';
  await assert.rejects(go(b),/EVENT_PROJECT_CONTRADICTION/);
  const c=fakeGardenStore(source);
  c.store.circleMembers=c.store.circleMembers.slice(0,1);
  await assert.rejects(go(c),/MEMBER_OR_OPENER_NOT_IN_SOURCE_CIRCLE/);
});
test('full source review does not import a synthetic job as monetary WORK',async()=>{
  if(!enabled)return;
  const a=fakeGardenStore(source);
  a.store.pledges[0].quantity=9999;
  const candidate=await go(a);
  assert.equal(candidate.penny_review.work_quantity_authorized,0);
  assert.equal(candidate.penny_review.active_penny_units_issued,0);
  assert.equal(candidate.native_penny_check.sourceEventCount,0);
});
