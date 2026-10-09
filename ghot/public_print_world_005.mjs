#!/usr/bin/env node
/* PUBLIC-PRINT-WORLD-005: GHoT held PDF to native Full Measure and PENNY-014.
 * No vendor submission, Full Measure pledge/witness/deed, or PENNY event.
 */
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const FM_SHA='c9206d5055ad574a23acb2eceb5f8785a4ad64fe';
const PENNY_SHA='a36777cb87bcfb6b7706b910ba18c4c4b24c73a3';
const GHOT_SHA='f62d8f2ae9a9077430bc1ef6fc4a17ea00f2affd';
const sha=value=>createHash('sha256').update(value).digest('hex');
const fail=s=>{throw Error('PRINT_WORLD_005_HOLD:'+s)};
const must=(condition,message)=>{if(!condition)fail(message)};
const REF=/^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$/;
const SHA=/^[a-f0-9]{64}$/;
function pin(root,commit){
  must(typeof root==='string'&&root.startsWith('/'),'ABSOLUTE_DONOR_ROOT_REQUIRED');
  let actual;
  try{actual=execFileSync('git',['rev-parse','HEAD'],
    {cwd:resolve(root),encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:10000}).trim();}
  catch{fail('DONOR_HEAD_NOT_VERIFIABLE')}
  must(actual===commit,'DONOR_REVISION_NOT_PINNED');
  return resolve(root);
}
export function verifyHeld(p){
  must(p&&typeof p==='object'&&!Array.isArray(p),'GHOT_SOURCE_PACKET_REQUIRED');
  must(p.schema==='ghot.public-print-handoff-004/v0'&&
       p.state==='PREPARED_LOCAL_HANDOFF_R3_HOLD','SOURCE_NOT_PREPARED_AND_HELD');
  must(typeof p.packet_id==='string'&&/^ghot-print-venue-004:[a-f0-9]{64}$/.test(p.packet_id)&&
       typeof p.local_pdf_sha256==='string'&&SHA.test(p.local_pdf_sha256),
       'SOURCE_FINGERPRINT_INVALID');
  must(['XEROX_MFP','LIBRARY_PUBLIC','FEDEX_OFFICE'].includes(p.venue_kind),
       'UNEXPECTED_PUBLIC_PRINT_ROUTE');
  must(REF.test(p.source_ref)&&REF.test(p.venue_ref),'SOURCE_REFERENCES_INVALID');
  must(Number.isSafeInteger(p.pdf_preflight?.pages)&&p.pdf_preflight.pages>=1&&
       p.pdf_preflight.pages<=250,'NATIVE_PDF_PREFLIGHT_REQUIRED');
  must(Number.isSafeInteger(p.print_intent?.copies)&&p.print_intent.copies>=1&&
       p.print_intent.copies<=20&&
       ['PUBLIC','PRIVATE'].includes(p.print_intent.sensitivity),
       'BOUNDED_PRINT_INTENT_REQUIRED');
  must(p.machine_vendor_and_model_verified===false&&
       p.venue_capabilities_and_fees_verified===false&&
       p.native_relatte_owner_admitted===false&&
       p.actual_print_order_submitted===false&&
       p.document_data_uploaded===false&&
       p.emails_sent===0&&p.network_requests===0&&
       p.payment_taken===false&&p.retrieval_code_issued===false&&
       p.paper_consumed===0&&p.pages_physically_printed===0&&
       p.physical_copies_collected===0&&
       p.external_vendor_receipt_obtained===false,
       'FORGED_PRINT_PAYMENT_OR_PHYSICAL_EFFECT');
  return p;
}
export function printQuestInbox(p){
  verifyHeld(p);
  must(p.print_intent.sensitivity==='PUBLIC',
       'PRIVATE_DOCUMENT_MAY_NOT_BECOME_PUBLIC_QUEST');
  const venueLabel={
    XEROX_MFP:'an operator-authorized Xerox printer',
    LIBRARY_PUBLIC:'a library print release desk',
    FEDEX_OFFICE:'a FedEx Office service counter'
  }[p.venue_kind];
  const e={
    schema:'static.field-test-entry/v0',
    id:'public-print-'+p.packet_id.slice(-28),
    source_project:'GHoT Public Print Venues 004',
    source_repository:'the-static-collective/GHoT',
    source_commit:GHOT_SHA,
    source_path:'ghot/public_print_venues_004.py',
    source_gate:'PREPARED_LOCAL_HANDOFF_R3_HOLD',
    title:'Return with the page',
    question:'Can a volunteer manually submit the selected public-safe PDF at '+
      venueLabel+' and independently report whether an actual page was collected?',
    scale:'SPARK',
    required_materials:[
      'The approved public-safe document',
      'Independent venue instructions and any separately approved payment',
      'A separate human observer and private external receipt record'
    ],
    procedure:[
      'Check current local venue policy before sharing any document',
      'Submit and pay only through an independent, expressly authorized operator action',
      'Record a genuine external receipt privately or record the absence of one',
      'Ask another authorized human to observe any collected physical pages'
    ],
    safety_boundaries:[
      'Never publish private document contents or site credentials',
      'This quest draft does not submit files, operate printers or pay',
      'Venue acceptance is not proof of physical output',
      'PENNY work and coin backing require separate authority and consent'
    ],
    return_evidence:[
      'A separately observed venue result or refusal',
      'A privately retained external receipt reference, if any',
      'A human-witnessed page collection or explicit unresolved result'
    ],
    condition:'READY_FOR_FIELD_TEST',condition_ref:null,
    possible_descendant:'A Garden pledge may be opened only by authorized humans',
    status:'PHYSICAL_UNVERIFIED',
    provenance_note:'Held source packet '+p.packet_id+
      '; PDF fingerprint sha256:'+p.local_pdf_sha256.slice(0,16)+
      '; no vendor submission occurred'
  };
  return {schema:'static.field-test-inbox/v0',entries:[e]};
}
export async function compose(p,fullRoot,pennyRoot){
  verifyHeld(p);
  const fm=await import(pathToFileURL(resolve(fullRoot,'src/lib/fieldQuestEngine.ts')).href);
  const penny=await import(pathToFileURL(resolve(pennyRoot,'src/penny-work-matter-014.mjs')).href);
  const input=printQuestInbox(p);
  const verified=fm.verifyFieldTestInbox(input);
  const [card]=fm.drawQuestCards(verified);
  const choice=fm.decideQuest(card,'HOLD');
  const garden=fm.projectGardenDraft(card);
  must(card.truth_state==='PROPOSAL'&&card.deed_state==='NOT_AWARDED'&&
       card.participation_state==='NOT_PLEDGED'&&
       choice.scope==='LOCAL_PROPOSAL_ONLY','FULL_MEASURE_DEED_OR_PLEDGE_LAUNDERED');
  // The native PENNY code verifies an empty, synthetic-policy genesis.
  // Signing keys never leave this process; no WORK or DEPOSIT event is signed.
  const k=Array.from({length:5},()=>penny.newKeys());
  const world=penny.createWorld({
    stewardPublicKey:k[0].publicKey,
    workWitnessPublicKey:k[1].publicKey,
    boxes:[{boxId:'box-simulated-print-005',
      custodianPublicKey:k[2].publicKey,counterPublicKey:k[3].publicKey,
      backingTermsRef:'terms-no-real-backing-005'}],
    holders:[{holderId:'node:print-quest-005',publicKey:k[4].publicKey}]
  });
  must(world.events.length===0,'UNAUTHORIZED_TREASURY_EVENT');
  const state=penny.inspectWorld(world);
  must(state.sourceEventCount===0&&state.workProducedPending===0&&
       state.workFundedReleased===0&&state.outstandingPennyUnits===0&&
       state.boxBookCoinCount===0&&state.bankSettledFunds===0&&
       state.interestEarned===0&&state.heldInRealCustodyVerifiedBySoftware===false,
       'PENNY_WITHOUT_VERIFIED_WORK_OR_COIN_BACKING');
  const body={
    schema:'ghot.print-world-005/v0',
    ghot_source_packet_id:p.packet_id,
    ghot_pdf_sha256:p.local_pdf_sha256,
    venue_kind:p.venue_kind,
    full_measure_donor_commit:FM_SHA,
    full_measure_quest:card,
    full_measure_hold_choice:choice,
    full_measure_garden_draft:garden,
    penny_donor_commit:PENNY_SHA,
    penny_work_candidate:{
      schema:'ghot.penny-work-possibility-005/v0',
      quest_id:card.quest_id,
      source_has_no_human_confirmed_deed:true,
      verified_work_witness_present:false,
      work_units_allocated:0,
      coin_custody_units_verified:0,
      pending_penny_units_created:0,
      active_penny_units_issued:0,
      status:'WORK_CANDIDATE_ONLY_NO_MONETARY_CONSEQUENCE'
    },
    native_penny_zero_genesis:{
      sourceEventCount:state.sourceEventCount,
      workProducedPending:state.workProducedPending,
      workFundedReleased:state.workFundedReleased,
      outstandingPennyUnits:state.outstandingPennyUnits,
      boxBookCoinCount:state.boxBookCoinCount,
      bankSettledFunds:state.bankSettledFunds,
      interestEarned:state.interestEarned
    },
    physical_pages_collected:0,
    payment_performed:false,
    garden_event_created:false,
    canonical_penny_event_created:false,
    real_relatte_crossing:false,
    physical_printer_access_claimed:false,
    status:'NATIVE_FULL_MEASURE_QUEST_PENNY_ZERO_HOLD'
  };
  return {...body,composition_id:'ghot-print-world-005:'+sha(JSON.stringify(body))};
}
async function main(){
  must(process.argv.length===6,'USAGE FULL_MEASURE_ROOT PENNY_ROOT GHOT_SOURCE.json NEW_OUTPUT.json');
  const [fmDir,treasDir,inFile,outFile]=process.argv.slice(2);
  const fm=pin(fmDir,FM_SHA),penny=pin(treasDir,PENNY_SHA);
  const raw=readFileSync(resolve(inFile));
  must(raw.length>0&&raw.length<100000,'BOUNDED_SOURCE_PACKET_REQUIRED');
  const result=await compose(JSON.parse(raw.toString('utf8')),fm,penny);
  const output=resolve(outFile);
  must(!existsSync(output),'OCCURRENCE_EXISTS_NO_AUTORETRY');
  writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
  console.log(JSON.stringify({status:result.status,
    quest_id:result.full_measure_quest.quest_id,
    deeds:0,penny_pending:0,penny_issued:0,printed_pages:0},null,2));
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))
  main().catch(e=>{console.error(e.message);process.exitCode=2});
