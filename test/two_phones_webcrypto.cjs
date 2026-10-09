#!/usr/bin/env node
/* POSTAL-CORPS-003: independently generated origin and carrier1 WebCrypto
   keys, no network calls, four actually encoded QR transfers, and a
   GHoT-native station reconciliation artifact for Python to verify.
   Only test keys exist in process memory. */
"use strict";
const {readFileSync,writeFileSync}=require("node:fs");
const assert=require("node:assert/strict");
const C=require("../web/carrier-pocket/two-phone-core.js");
const qrgen=require("../web/carrier-pocket/vendor/qrgen.min.js");
const [dispatchFile,out]=process.argv.slice(2);
if(!dispatchFile||!out)throw Error("usage: node two_phones_webcrypto.cjs dispatch.json output.json");
const dispatch=JSON.parse(readFileSync(dispatchFile,"utf-8"));
async function attemptReject(test,label){
 await assert.rejects(test,undefined,label);
}
(async()=>{
 const A=await C.newKey(),B=await C.newKey();
 const relay=await C.newKey(),carrier2=await C.newKey();
 const recipient=await C.newKey(),witness=await C.newKey();
 const pins={origin:A.publicJwk,carrier1:B.publicJwk,relay:relay.publicJwk,
             carrier2:carrier2.publicJwk,recipient:recipient.publicJwk,witness:witness.publicJwk};
 assert.notDeepEqual(A.publicJwk,B.publicJwk);
 const parcelHash=await C.hexhash("synthetic-book-in-envelope-no-physical-object");
 const route=await C.makeRoute(dispatch,pins,parcelHash,A);
 const setup={dispatch,route};
 assert.equal(await C.verifyRoute(route,dispatch),true);
 // Phone B accepts an optional synthetic leg. A verifies that exact signature.
 const acceptance=await C.acceptLeg(route,dispatch,B,
                       await C.hexhash("carrier-B-voluntary-synthetic-acceptance"));
 const Aevents=[acceptance],Bevents=[acceptance];
 assert.equal((await C.verifyHistory(route,dispatch,Aevents)).state,"LEG1_ACCEPTED");
 // Origin Phone A signs a QR and carrier Phone B independently verifies it.
 const qr=await C.issue(route,dispatch,Aevents,A,await C.hexhash("fictional-seal"));
 assert.equal(await C.checkOffer(route,dispatch,Bevents,qr),true);
 const response=await C.respond(route,dispatch,Bevents,qr,B);
 const confirmed=await C.checkReply(route,dispatch,Aevents,qr,response);
 const bSynced=await C.syncTail(route,dispatch,Bevents,confirmed.event);
 assert.deepEqual(bSynced.events,confirmed.events);
 assert.equal(bSynced.head,confirmed.head);
 const payloads=[
   {type:"accept",packet:acceptance},
   {type:"offer",challenge:qr},
   {type:"reply",response},
   {type:"sync",packet:confirmed.event,head:confirmed.head},
 ];
 // These are real local QR Model 2 encodes. No CDN, no external requests.
 const sizes=[];
 for(const data of payloads){
   const json=C.canonical(data);
   const qrObj=qrgen.QrCode.encodeText(json,qrgen.QrCode.Ecc.LOW);
   assert.ok(qrObj.size>0 && qrObj.size<=177);
   sizes.push({type:data.type,chars:json.length,qr_modules:qrObj.size});
 }
 // Tampering / substitution must always fail without side effects.
 const other=await C.newKey();
 const wrongRoute=structuredClone(route);
 wrongRoute.role_pins.carrier1=other.publicJwk;
 await attemptReject(()=>C.verifyRoute(wrongRoute,dispatch),"route pin substitution");
 const badAccept=structuredClone(acceptance);
 badAccept.signatures.carrier1=(await C.sign(other.pair,
    "PostEmahh-n-Postal-Corps-001-Event|"+C.canonical(acceptance.body)));
 await attemptReject(()=>C.verifyHistory(route,dispatch,[badAccept]),"wrong carrier signature");
 const changedReply=structuredClone(response);changedReply.response_body.nonce="0".repeat(32);
 await attemptReject(()=>C.checkReply(route,dispatch,Aevents,qr,changedReply),"nonce substitution");
 const changedQR=structuredClone(qr);changedQR.body.parcel_sha256="0".repeat(64);
 await attemptReject(()=>C.checkOffer(route,dispatch,Aevents,changedQR),"wrong parcel");
 await attemptReject(()=>C.checkOffer(route,dispatch,Aevents,qr,qr.body.expires_at+1),
    "expired QR");
 const forgedTail=structuredClone(confirmed.event);
 forgedTail.body.prior_event_sha256="f".repeat(64);
 await attemptReject(()=>C.syncTail(route,dispatch,Bevents,forgedTail),"divergent tail");
 const duplicateHash=await C.hexhash("duplicate");
 await attemptReject(()=>C.issue(route,dispatch,confirmed.events,A,
    duplicateHash),"duplicate issue");
 const bundle={
   schema:"postemahhn.two-phones-fieldkit/v0",
   classification:"synthetic_no_real_carriage",
   dispatch,route,events:confirmed.events,challenge:qr,response,
   claimed_head:confirmed.head,physical_parcel_observed:false,
   penny_units_released:0,full_measure_deeds:0,
 };
 writeFileSync(out,JSON.stringify(bundle,null,2)+"\n");
 console.log("TWO PHONE PROOF PASS: two independent P-256 keys; signed route; four QR encodes; head "+confirmed.head);
 console.log(JSON.stringify(sizes));
})().catch(e=>{console.error(e);process.exitCode=1;});
