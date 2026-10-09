#!/usr/bin/env node
/** PRINT-WITNESS-006: Full Measure local confirmed contribution -> PENNY work REVIEW.
 *
 * Critical: Full Measure's current local store is unauthenticated. These are
 * local record-consistency checks using actual Full Measure authorization and
 * projection code. They are NOT verification of real people, a physical print,
 * a signed independent witness, or spendable PENNY. Never append WORK/DEPOSIT.
 */
import {createHash} from 'node:crypto';
import {existsSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

const FM_REV='c9206d5055ad574a23acb2eceb5f8785a4ad64fe';
const PENNY_REV='a36777cb87bcfb6b7706b910ba18c4c4b24c73a3';
const REF=/^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$/;
const SHA=/^[a-f0-9]{64}$/;
const TIMES=/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/;
const fail=s=>{throw Error('PRINT_WITNESS_006_HOLD: '+s)};
const ok=(v,s)=>{if(!v)fail(s)};
const hash=x=>createHash('sha256').update(x).digest('hex');
const canonical=o=>JSON.stringify(o);
const ref=(v,s)=>ok(typeof v==='string'&&REF.test(v),s);
const time=(v,s)=>ok(typeof v==='string'&&TIMES.test(v)&&
  !Number.isNaN(Date.parse(v))&&new Date(v).toISOString()===v,s);
const object=(v,s)=>ok(v&&typeof v==='object'&&!Array.isArray(v),s);
const exact=(v,fields,s)=>{object(v,s);ok(Object.keys(v).sort().join('|')===fields.slice().sort().join('|'),s)};
function pinned(root,sha){
  ok(typeof root==='string'&&root.startsWith('/'),'ABSOLUTE_DONOR_PATH_REQUIRED');
  const dir=resolve(root);
  let head;
  try{head=execFileSync('git',['rev-parse','HEAD'],{cwd:dir,encoding:'utf8',timeout:10000,
    stdio:['ignore','pipe','ignore']}).trim();}
  catch{fail('DONOR_REVISION_UNAVAILABLE')}
  ok(head===sha,'DONOR_REVISION_MISMATCH');
  return dir;
}
export function verifyGhot005(raw){
  object(raw,'GHOT_COMPOSITION_REQUIRED');
  const {composition_id,...body}=raw;
  ok(raw.schema==='ghot.print-world-005/v0'&&
     raw.status==='NATIVE_FULL_MEASURE_QUEST_PENNY_ZERO_HOLD',
     'ORIGINAL_GHOT_005_HELD_PROOF_REQUIRED');
  ok(composition_id==='ghot-print-world-005:'+hash(canonical(body)),
    'GHOT_COMPOSITION_SHA256_MISMATCH');
  const q=raw.full_measure_quest;
  ok(q?.schema==='full-measure.field-quest-card/v0'&&
     q?.truth_state==='PROPOSAL'&&q?.deed_state==='NOT_AWARDED'&&
     q?.participation_state==='NOT_PLEDGED'&&
     raw.full_measure_hold_choice?.quest_id===q.quest_id&&
     raw.full_measure_hold_choice?.disposition==='HOLD'&&
     raw.full_measure_hold_choice?.deed_state==='NOT_AWARDED',
     'GHOT_005_FULLMEASURE_NOT_HELD');
  ok(raw.penny_work_candidate?.pending_penny_units_created===0&&
     raw.penny_work_candidate?.active_penny_units_issued===0&&
     raw.native_penny_zero_genesis?.sourceEventCount===0&&
     raw.native_penny_zero_genesis?.outstandingPennyUnits===0&&
     raw.native_penny_zero_genesis?.boxBookCoinCount===0&&
     raw.physical_pages_collected===0&&raw.payment_performed===false&&
     raw.real_relatte_crossing===false&&raw.garden_event_created===false&&
     raw.canonical_penny_event_created===false,'GHOT_005_FORGED_PRIOR_AUTHORITY');
  ok(typeof raw.ghot_source_packet_id==='string'&&
     /^ghot-print-venue-004:[a-f0-9]{64}$/.test(raw.ghot_source_packet_id)&&
     SHA.test(raw.ghot_pdf_sha256),'GHOT_005_PDF_SOURCE_MISSING');
  return raw;
}
export function validateSelection(selection,source){
  exact(selection,['schema','source_composition_id','source_quest_id',
    'project_id','pledge_id','local_review_ref'],'REVIEW_SELECTION_FIELDS_INVALID');
  ok(selection.schema==='ghot.print-work-review-selection-006/v0'&&
     selection.source_composition_id===source.composition_id&&
     selection.source_quest_id===source.full_measure_quest.quest_id,
     'REVIEW_SOURCE_SELECTION_MISMATCH');
  for(const key of ['project_id','pledge_id','local_review_ref'])
    ref(selection[key],'REVIEW_SELECTION_REFERENCE_INVALID');
  return selection;
}
const eventKind={
  'pledge.proposed':'proposed',
  'pledge.accepted':'accepted',
  'pledge.reported_complete':'reported_complete',
  'pledge.confirmed':'confirmed'
};
export async function review({source,store,selection,fullMeasureRoot,pennyRoot}){
  const original=verifyGhot005(source);
  const selected=validateSelection(selection,original);
  object(store,'FULLMEASURE_STORE_OBJECT_REQUIRED');
  ok(Array.isArray(store.projects)&&store.projects.length<=1000&&
     Array.isArray(store.pledges)&&store.pledges.length<=4000&&
     Array.isArray(store.domainEvents)&&store.domainEvents.length<=16000&&
     Array.isArray(store.circleMembers)&&store.circleMembers.length<=5000,
     'FULLMEASURE_BOUNDED_CANONICAL_STORE_REQUIRED');
  const fmAuth=await import(pathToFileURL(resolve(fullMeasureRoot,'src/lib/pledgeAuthority.ts')).href);
  const fmSheet=await import(pathToFileURL(resolve(fullMeasureRoot,'src/lib/fullMeasure.ts')).href);
  const penny=await import(pathToFileURL(resolve(pennyRoot,'src/penny-work-matter-014.mjs')).href);
  const projects=store.projects.filter(x=>x?.id===selected.project_id);
  const pledges=store.pledges.filter(x=>x?.id===selected.pledge_id);
  ok(projects.length===1&&pledges.length===1,'PROJECT_OR_PLEDGE_MISSING_OR_DUPLICATE');
  const project=projects[0],pledge=pledges[0];
  ref(project.id,'PROJECT_ID_INVALID');ref(project.circleId,'PROJECT_CIRCLE_ID_INVALID');
  ref(project.openedBy,'PROJECT_OPENER_ID_INVALID');ref(pledge.pledgedBy,'PLEDGER_ID_INVALID');
  ok(pledge.projectId===project.id&&pledge.pledgedBy!==project.openedBy,
     'PROJECT_PLEDGE_PARTICULAR_OR_SEPARATE_ACTORS_INVALID');
  ok(['confirmed','reported_complete'].includes(pledge.status),'PLEDGE_NOT_REPORTED');
  const members=store.circleMembers.filter(m=>m.circleId===project.circleId);
  const member=(actor)=>members.some(m=>m.userId===actor&&['member','steward'].includes(m.role));
  const witness=(actor)=>actor===project.openedBy||
    members.some(m=>m.userId===actor&&m.role==='steward');
  ok(member(pledge.pledgedBy)&&member(project.openedBy),
     'MEMBER_OR_OPENER_NOT_IN_SOURCE_CIRCLE');
  const events=store.domainEvents.filter(x=>x?.aggregateType==='pledge'&&x?.aggregateId===pledge.id);
  ok(events.length>=3&&events.length<=4,'MISSING_OR_CONFLICTING_PLEDGE_HISTORY');
  const unique=new Set();const seq=[];
  for(const e of events){
    object(e,'PLEDGE_EVENT_MALFORMED');
    ref(e.id,'PLEDGE_EVENT_ID_INVALID');
    ok(!unique.has(e.id),'DUPLICATE_EVENT_ID');unique.add(e.id);
    time(e.createdAt,'EVENT_DATE_INVALID');
    ok(e.circleId===project.circleId&&e.aggregateType==='pledge'&&
       e.aggregateId===pledge.id&&eventKind[e.eventType],
       'UNEXPECTED_OR_FOREIGN_PLEDGE_HISTORY');
    object(e.payload,'EVENT_PAYLOAD_REQUIRED');
    ok(e.payload.projectId===project.id,
       'EVENT_PROJECT_CONTRADICTION');
    if(e.eventType!=='pledge.proposed'){
      ok(e.payload.pledgeId===pledge.id,'EVENT_PLEDGE_CONTRADICTION');
    }
    if(e.eventType==='pledge.confirmed')
      ok(e.payload.pledgedBy===pledge.pledgedBy,'EVENT_BENEFICIARY_CONTRADICTION');
    ref(e.actorId,'EVENT_ACTOR_ID_INVALID');
    seq.push(e);
  }
  seq.sort((a,b)=>a.createdAt.localeCompare(b.createdAt));
  const expected=pledge.status==='confirmed'
    ? ['pledge.proposed','pledge.accepted','pledge.reported_complete','pledge.confirmed']
    : ['pledge.proposed','pledge.accepted','pledge.reported_complete'];
  ok(seq.length===expected.length&&seq.every((e,i)=>e.eventType===expected[i]),
     'HISTORY_MISSING_OR_OUT_OF_ORDER');
  for(let i=1;i<seq.length;i++)
    ok(seq[i].createdAt>seq[i-1].createdAt,'EVENT_TIME_NON_MONOTONIC');
  ok(seq[0].actorId===pledge.pledgedBy,'PLEDGE_PROPOSAL_NOT_BY_CONTRIBUTOR');
  const steps=[
    {action:'accept',status:'proposed',e:seq[1]},
    {action:'report_complete',status:'accepted',e:seq[2]}
  ];
  if(pledge.status==='confirmed')
    steps.push({action:'confirm',status:'reported_complete',e:seq[3]});
  for(const s of steps){
    const allowed=fmAuth.authorizePledgeTransition({
      action:s.action,currentStatus:s.status,
      isOpenerOrSteward:witness(s.e.actorId),
      isPledgeAuthor:s.e.actorId===pledge.pledgedBy
    });
    ok(allowed.ok===true,'NATIVE_FULLMEASURE_ROLE_OR_TRANSITION_REFUSED_'+s.action);
  }
  ok(pledge.acceptedAt===seq[1].createdAt&&
     pledge.reportedCompleteAt===seq[2].createdAt&&
     (pledge.status==='confirmed'
       ? pledge.confirmedAt===seq[3].createdAt
       : pledge.confirmedAt===null),'PLEDGE_STATUS_TIMESTAMP_INCONSISTENT');
  ok(seq[1].actorId!==pledge.pledgedBy&&
     (pledge.status!=='confirmed'||seq[3].actorId!==pledge.pledgedBy),
     'CONTRIBUTOR_CANNOT_WITNESS_OWN_WORK');
  // The Full Measure sheet is the real source implementation, but output is
  // not signed by any identity. Source store is not authenticated externally.
  const sheet=fmSheet.buildFullMeasureSheet({
    userId:pledge.pledgedBy,offers:[],
    projects:[{...project,pledges:[pledge]}],
    receipts:[],capacities:[],events:seq
  });
  const deed=sheet.measures.find(m=>m.key==='deed')?.value??0;
  ok(deed===(pledge.status==='confirmed'?1:0),
     'NATIVE_FULL_MEASURE_DEED_PROJECTION_CONTRADICTION');

  // Native PENNY-014: validate empty policy and inspect unchanged zero ledger.
  const keys=Array.from({length:5},()=>penny.newKeys());
  const world=penny.createWorld({
    stewardPublicKey:keys[0].publicKey,workWitnessPublicKey:keys[1].publicKey,
    boxes:[{boxId:'box-print-review-006',custodianPublicKey:keys[2].publicKey,
      counterPublicKey:keys[3].publicKey,
      backingTermsRef:'terms-uncommitted-physical-coins-006'}],
    holders:[{holderId:'node:print-work-006',publicKey:keys[4].publicKey}]
  });
  const s=penny.inspectWorld(world);
  ok(world.events.length===0&&s.sourceEventCount===0&&
     s.workProducedPending===0&&s.workFundedReleased===0&&
     s.outstandingPennyUnits===0&&s.boxBookCoinCount===0&&
     s.bankSettledFunds===0&&s.interestEarned===0&&
     s.heldInRealCustodyVerifiedBySoftware===false,
     'PENNY_MUST_REMAIN_UNISSUED_AND_UNBACKED');
  const confirmed=pledge.status==='confirmed';
  const sourceTrace=hash(JSON.stringify(seq));
  const sourcePledge=hash(JSON.stringify(pledge));
  const body={
    schema:'ghot.print-work-review-006/v0',
    originating_ghot_composition_id:source.composition_id,
    ghot_source_pdf_sha256:source.ghot_pdf_sha256,
    full_measure_source_revision:FM_REV,
    full_measure_source_history_digest:'sha256:'+sourceTrace,
    full_measure_source_pledge_digest:'sha256:'+sourcePledge,
    full_measure_source_event_count:seq.length,
    full_measure_transition_checker:'NATIVE_FULL_MEASURE_PLEDGE_AUTHORITY',
    full_measure_sheet_deed_count:deed,
    full_measure_local_record_state:confirmed?'CONFIRMED_BY_LOCAL_STORE':'REPORTED_NOT_CONFIRMED',
    full_measure_human_identity_authenticated:false,
    actual_physical_print_independently_verified:false,
    source_export_signature_verified:false,
    source_selected_by_local_operator_only:true,
    penny_native_source_revision:PENNY_REV,
    penny_review:{
      schema:'jubilee.print-work-review-candidate-006/v0',
      subject_trace_sha256:sourceTrace,
      source_work_reference:'print-work:'+sourcePledge.slice(0,40),
      status:confirmed?'REVIEW_ELIGIBLE_ONLY_NEEDS_INDEPENDENT_WORK_WITNESS':
        'HOLD_UNCONFIRMED_FULL_MEASURE_REPORT',
      human_witness_identity_verified:false,
      penny_work_witness_attestation_present:false,
      work_terms_accepted:false,
      work_quantity_authorized:0,
      coin_backing_deposits_verified:0,
      treasury_work_events_appended:0,
      pending_penny_units_created:0,
      active_penny_units_issued:0,
      financial_transfer_performed:false,
      automatic_treasury_apply:false
    },
    native_penny_check:{
      sourceEventCount:s.sourceEventCount,
      workProducedPending:s.workProducedPending,
      workFundedReleased:s.workFundedReleased,
      outstandingPennyUnits:s.outstandingPennyUnits,
      boxBookCoinCount:s.boxBookCoinCount
    },
    full_measure_canonical_store_modified:false,
    vendor_submission_performed:false,
    real_relatte_crossing:false,
    status:'LOCAL_HUMAN_RECORD_TO_PENNY_REVIEW_NO_ALLOCATION'
  };
  return {...body,review_id:'ghot-print-witness-006:'+hash(JSON.stringify(body))};
}
async function main(){
  ok(process.argv.length===8,
    'USAGE: FM_CHECKOUT PENNY_CHECKOUT SOURCE_005.json LOCAL_FM_STORE.json SELECTION.json OUTPUT_NEW.json');
  const [full,penny,source,store,selection,out]=process.argv.slice(2);
  const fm=pinned(full,FM_REV),pen=pinned(penny,PENNY_REV);
  const get=path=>{
    const data=readFileSync(resolve(path));
    ok(data.length>0&&data.length<2_000_000,'BOUNDED_LOCAL_INPUT_REQUIRED');
    return JSON.parse(data.toString('utf8'));
  };
  const result=await review({fullMeasureRoot:fm,pennyRoot:pen,
    source:get(source),store:get(store),selection:get(selection)});
  const destination=resolve(out);
  ok(!existsSync(destination),'OUTPUT_EXISTS_NO_SILENT_RETRY');
  writeFileSync(destination,JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
  console.log(JSON.stringify({
    status:result.status,review_id:result.review_id,
    fm_record_state:result.full_measure_local_record_state,
    fm_deed_count:result.full_measure_sheet_deed_count,
    penny_review:result.penny_review.status,
    pending:0,active:0,backing:0
  },null,2));
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))
  main().catch(e=>{console.error(e.message);process.exitCode=2});
