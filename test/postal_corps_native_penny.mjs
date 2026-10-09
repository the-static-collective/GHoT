#!/usr/bin/env node
// Source-native PENNY-014 reader. Uses private synthetic test identities only.
// "Candidate" must never mutate the Treasury by its mere existence.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const [candidatePath, treasuryModule] = process.argv.slice(2);
if (!candidatePath || !treasuryModule) throw Error("usage: node proof.mjs CANDIDATES PATH_TO_NATIVE_PENNY_014.mjs");
const {newKeys,createWorld,attest,append,inspectWorld}=await import(pathToFileURL(resolve(treasuryModule)).href);
const v=JSON.parse(readFileSync(candidatePath,'utf8'));
assert.equal(v.source,'LEMONPRESS_NATIVE_DISPATCH_001');
assert.equal(v.source_dispatch_state,'service_selected');
assert.equal(v.route_state,'WORK_REVIEW_READY');
assert.equal(v.full_measure.deed_state,'NOT_AWARDED');
assert.equal(v.full_measure.official_full_measure_event_created,false);
assert.equal(v.penny.status,'NO_TREASURY_EVENT');
assert.equal(v.penny.book_coins,0);
assert.equal(v.penny.active_units,0);
assert.equal(v.penny.released_units,0);
assert.equal(v.penny.work_witness_proof,null);
assert.equal(v.penny.candidate_work_payloads.length,2);

const [steward,witness,boxCustodian,boxCounter,holder1,holder2]=
 Array.from({length:6},()=>newKeys());
let world=createWorld({
  stewardPublicKey:steward.publicKey,
  workWitnessPublicKey:witness.publicKey,
  boxes:[{
    boxId:'box:simulation-001',
    custodianPublicKey:boxCustodian.publicKey,
    counterPublicKey:boxCounter.publicKey,
    backingTermsRef:'terms:fixture-only',
  }],
  holders:[
    {holderId:'person:synthetic-carrier1',publicKey:holder1.publicKey},
    {holderId:'person:synthetic-carrier2',publicKey:holder2.publicKey},
  ],
});
const before=inspectWorld(world);
assert.equal(before.workProducedPending,0);
assert.equal(before.outstandingPennyUnits,0);
assert.equal(before.boxBookCoinCount,0);

// Raw unsigned postal candidates cannot manufacture PENNY ledger WORK.
assert.throws(()=>append(world,steward,'WORK',{
  certificate:{payload:v.penny.candidate_work_payloads[0]}
},new Date().toISOString()));

// A separate *synthetic* native PENNY work witness elects to sign the specific
// claims in this isolated test. This is not a Full Measure official deed and
// doesn't claim a real human, compensated service, payment or physical backing.
for (const payload of v.penny.candidate_work_payloads) {
  const certificate=attest('work_witness',payload,witness);
  world=append(world,steward,'WORK',{certificate},new Date().toISOString());
}
const after=inspectWorld(world);
assert.equal(after.workProducedPending,2);
assert.equal(after.workFundedReleased,0);
assert.equal(after.outstandingPennyUnits,0);
assert.equal(after.boxBookCoinCount,0);
assert.equal(after.freeCoinBacking,0);
assert.equal(after.bankSettledFunds,0);
assert.equal(after.interestEarned,0);
console.log('REAL PENNY-014 MODULE PASS: unsigned proposals 0; separate synthetic witness creates pending 2; active 0; backing 0; cash 0.');
