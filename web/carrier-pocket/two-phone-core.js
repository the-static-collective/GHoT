/* POSTAL-CORPS-003 -- bounded 2-phone signed QR experiment.
   One synthetic route, two independent keys, one accepted-leg preflight,
   one pickup claim, one verified return. No civil/physical/economic proof.
   Browser and Node 22 WebCrypto compatible. No network side effects.
*/
(function(g){
"use strict";
const T=g.crypto?.subtle;
const enc=new TextEncoder();
const D_ROUTE="PostEmahh-n-Postal-Corps-001-Route|";
const D_EVT="PostEmahh-n-Postal-Corps-001-Event|";
const D_CH="PostEmahh-n-Carrier-Pocket-Challenge-v0|";
const D_RE="PostEmahh-n-Carrier-Pocket-Response-v0|";
const SCOPE="SYNTHETIC_CUSTODY_CLAIM_ONLY";
const hex=/^[0-9a-f]{64}$/;
const ref=/^[a-z][a-z0-9-]{2,63}$/;
function ok(test,message){if(!test)throw Error(message);}
function canonical(v){
 if(v===null||typeof v!=="object")return JSON.stringify(v);
 if(Array.isArray(v))return "["+v.map(canonical).join(",")+"]";
 const names=Object.keys(v).sort();
 return "{"+names.map(k=>JSON.stringify(k)+":"+canonical(v[k])).join(",")+"}";
}
function raw(v){return enc.encode(typeof v==="string"?v:canonical(v));}
function b64(b){
 let s="";for(const ch of new Uint8Array(b))s+=String.fromCharCode(ch);
 return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
}
function deb64(s){
 ok(typeof s==="string"&&/^[A-Za-z0-9_-]+$/.test(s),"invalid base64url");
 const a=atob(s.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-s.length%4)%4));
 return Uint8Array.from(a,v=>v.charCodeAt(0));
}
async function hexhash(v){return Array.from(new Uint8Array(await T.digest("SHA-256",raw(v)))).map(x=>x.toString(16).padStart(2,"0")).join("");}
function publicJwk(k){return {kty:k.kty,crv:k.crv,x:k.x,y:k.y};}
function jwkShape(k){return k&&k.kty==="EC"&&k.crv==="P-256"&&typeof k.x==="string"&&typeof k.y==="string";}
async function verify(key,text,sig){
 ok(jwkShape(key),"not a P-256 role");
 const imported=await T.importKey("jwk",publicJwk(key),{name:"ECDSA",namedCurve:"P-256"},false,["verify"]);
 return T.verify({name:"ECDSA",hash:"SHA-256"},imported,deb64(sig),raw(text));
}
async function sign(pair,text){return b64(await T.sign({name:"ECDSA",hash:"SHA-256"},pair.privateKey,raw(text)));}
async function newKey(){const pair=await T.generateKey({name:"ECDSA",namedCurve:"P-256"},false,["sign","verify"]);
 return {pair,publicJwk:publicJwk(await T.exportKey("jwk",pair.publicKey))};}
function assertDispatch(d){
 ok(d&&d.dispatch_version==="dispatch-gate-001"&&d.state==="service_selected"
   &&d.postage===null&&d.recipient_id?.startsWith("specimen:")
   &&d.carrier_selection?.carrier==="POSTAL-CORPS-SIMULATION"
   &&d.carrier_selection?.service==="offline-specimen"
   &&d.carrier_selection?.state==="human_selected"
   &&d.privacy?.record_disposition==="local_only"
   &&hex.test(d.packet_manifest_sha256)&&ref.test(d.packet_id)
   &&Array.isArray(d.events)&&d.events.length===1
   &&d.events[0].event==="service_selected",
   "only a selected, synthetic LemonPRESS fixture is accepted");
}
async function makeRoute(dispatch,pins,parcelHash,origin,routeId="route-specimen-001"){
 assertDispatch(dispatch);ok(hex.test(parcelHash)&&ref.test(routeId),"route or parcel ID invalid");
 const roles=["origin","carrier1","relay","carrier2","recipient","witness"];
 ok(pins&&Object.keys(pins).sort().join("|")===roles.slice().sort().join("|"),"six role public keys required");
 ok(roles.every(r=>jwkShape(pins[r])),"bad public role key");
 ok(new Set(roles.map(r=>canonical(publicJwk(pins[r])))).size===6,"role keys cannot be shared");
 ok(canonical(pins.origin)===canonical(origin.publicJwk),"origin device key not enrolled");
 const dHash=await hexhash(dispatch);
 const base={
  schema:"postemahhn.postal-corps-route/v0",route_id:routeId,
  parcel_id:dispatch.packet_id,parcel_sha256:parcelHash,
  source_dispatch_sha256:dHash,
  source_manifest_sha256:dispatch.packet_manifest_sha256,
  source_dispatch_state:"service_selected",
  classification:"synthetic_parcel_no_real_carriage",role_pins:pins
 };
 return {...base,source_signature:await sign(origin.pair,D_ROUTE+canonical(base))};
}
async function verifyRoute(route,dispatch){
 assertDispatch(dispatch);
 ok(route&&route.schema==="postemahhn.postal-corps-route/v0"
    &&route.classification==="synthetic_parcel_no_real_carriage"
    &&route.parcel_id===dispatch.packet_id
    &&route.source_manifest_sha256===dispatch.packet_manifest_sha256
    &&route.source_dispatch_sha256===await hexhash(dispatch)
    &&route.source_dispatch_state==="service_selected"
    &&hex.test(route.parcel_sha256)&&ref.test(route.route_id),"route/dispatch mismatch");
 ok(new Set(Object.values(route.role_pins).map(canonical)).size===6,"role keys not independent");
 const copy={...route};delete copy.source_signature;
 ok(await verify(route.role_pins.origin,D_ROUTE+canonical(copy),route.source_signature),
    "route signature invalid");
 return true;
}
function eventBody(route,action,seq,state,prev,evidence){
 return {schema:"postemahhn.postal-corps-event/v0",
 seq,prior_event_sha256:prev,route_id:route.route_id,
 state_before:state,action,evidence_sha256:evidence};
}
async function verifyHistory(route,dispatch,events){
 await verifyRoute(route,dispatch);
 ok(Array.isArray(events)&&events.length<=2,"only two-event synthetic trial admitted");
 let head=null,st="OFFERED";
 for(let i=0;i<events.length;i++){
  const p=events[i],b=p?.body;
  const action=i===0?"ACCEPT_LEG1":"PICKUP_LEG1";
  const roleSet=i===0?["carrier1"]:["origin","carrier1"];
  ok(b?.schema==="postemahhn.postal-corps-event/v0"
     &&b.seq===i+1&&b.route_id===route.route_id
     &&b.prior_event_sha256===head&&b.state_before===st
     &&b.action===action&&hex.test(b.evidence_sha256)
     &&p.signatures&&Object.keys(p.signatures).sort().join("|")===roleSet.sort().join("|"),
     "stale or unauthorized signed history");
  for(const r of roleSet)ok(await verify(route.role_pins[r],
      D_EVT+canonical(b),p.signatures[r]),"history signature invalid: "+r);
  head=await hexhash(p);st=i===0?"LEG1_ACCEPTED":"LEG1_MOVING_CLAIM";
 }
 return {state:st,head,event_count:events.length};
}
async function acceptLeg(route,dispatch,actor,evidenceHash){
 await verifyRoute(route,dispatch);
 ok(canonical(actor.publicJwk)===canonical(route.role_pins.carrier1),"not authorized first carrier");
 ok(hex.test(evidenceHash),"synthetic evidence hash required");
 const b=eventBody(route,"ACCEPT_LEG1",1,"OFFERED",null,evidenceHash);
 const pkt={body:b,signatures:{carrier1:await sign(actor.pair,D_EVT+canonical(b))}};
 await verifyHistory(route,dispatch,[pkt]);
 return pkt;
}
async function issue(route,dispatch,events,actor,evidenceHash,clock=Math.floor(Date.now()/1000)){
 const s=await verifyHistory(route,dispatch,events);
 ok(s.state==="LEG1_ACCEPTED"&&canonical(actor.publicJwk)===canonical(route.role_pins.origin),
    "only enrolled origin can offer pickup after accepted leg");
 ok(hex.test(evidenceHash),"evidence SHA required");
 const event=eventBody(route,"PICKUP_LEG1",2,s.state,s.head,evidenceHash);
 const nonce=Array.from(g.crypto.getRandomValues(new Uint8Array(16))).map(n=>n.toString(16).padStart(2,"0")).join("");
 const body={
  schema:"postemahhn.carrier-pocket-challenge/v0",
  route_hash:await hexhash(route),parcel_sha256:route.parcel_sha256,
  event,initiator:"origin",responder:"carrier1",nonce,
  issued_at:clock,expires_at:clock+300,scope:SCOPE
 };
 return {body,initiator_proof:await sign(actor.pair,D_CH+canonical(body)),
 event_proof:await sign(actor.pair,D_EVT+canonical(event))};
}
async function checkOffer(route,dispatch,events,offer,clock=Math.floor(Date.now()/1000)){
 const s=await verifyHistory(route,dispatch,events);
 const b=offer?.body,e=b?.event;
 ok(s.state==="LEG1_ACCEPTED"&&e?.schema==="postemahhn.postal-corps-event/v0"
    &&e.action==="PICKUP_LEG1"&&e.seq===2&&e.state_before==="LEG1_ACCEPTED"
    &&e.prior_event_sha256===s.head&&e.route_id===route.route_id
    &&hex.test(e.evidence_sha256),"stale handoff or wrong event");
 ok(b.schema==="postemahhn.carrier-pocket-challenge/v0"
    &&b.scope===SCOPE&&b.initiator==="origin"&&b.responder==="carrier1"
    &&b.route_hash===await hexhash(route)
    &&b.parcel_sha256===route.parcel_sha256
    &&/^[0-9a-f]{32}$/.test(b.nonce)
    &&Number.isInteger(b.issued_at)&&Number.isInteger(b.expires_at)
    &&b.expires_at-b.issued_at===300
    &&clock>=b.issued_at-60&&clock<=b.expires_at,"QR route/expiry/scope mismatch");
 ok(await verify(route.role_pins.origin,D_CH+canonical(b),offer.initiator_proof),
    "issuer QR signature invalid");
 ok(await verify(route.role_pins.origin,D_EVT+canonical(e),offer.event_proof),
    "issuer native event signature invalid");
 return true;
}
async function respond(route,dispatch,events,offer,actor,clock){
 await checkOffer(route,dispatch,events,offer,clock);
 ok(canonical(actor.publicJwk)===canonical(route.role_pins.carrier1),
    "responder key not pinned to carrier1");
 const b=offer.body;
 const body={
  schema:"postemahhn.carrier-pocket-response/v0",
  challenge_sha256:await hexhash(offer),nonce:b.nonce,
  event_sha256:await hexhash(b.event),responder:"carrier1",scope:SCOPE
 };
 return {challenge:offer,response_body:body,
   response_proof:await sign(actor.pair,D_RE+canonical(body)),
   event_proof:await sign(actor.pair,D_EVT+canonical(b.event))};
}
async function checkReply(route,dispatch,events,issued,reply,clock){
 await checkOffer(route,dispatch,events,issued,clock);
 ok(reply&&canonical(reply.challenge)===canonical(issued),"reply challenge not issued here");
 const b=issued.body,p=reply.response_body;
 ok(p?.schema==="postemahhn.carrier-pocket-response/v0"
    &&p.challenge_sha256===await hexhash(issued)
    &&p.event_sha256===await hexhash(b.event)
    &&p.nonce===b.nonce&&p.responder==="carrier1"&&p.scope===SCOPE,
    "reply does not bind this nonce/event");
 ok(await verify(route.role_pins.carrier1,D_RE+canonical(p),reply.response_proof),
    "carrier response signature invalid");
 ok(await verify(route.role_pins.carrier1,D_EVT+canonical(b.event),reply.event_proof),
    "carrier event signature invalid");
 const pkt={body:b.event,signatures:{origin:issued.event_proof,carrier1:reply.event_proof}};
 const proposed=[...events,pkt];
 await verifyHistory(route,dispatch,proposed);
 return {event:pkt,events:proposed,head:await hexhash(pkt)};
}
async function syncTail(route,dispatch,events,pkt){
 const mine=await verifyHistory(route,dispatch,events);
 ok(mine.event_count===1&&pkt?.body?.seq===2,"sync must extend one prior event");
 const all=[...events,pkt];const good=await verifyHistory(route,dispatch,all);
 return {events:all,head:good.head};
}
const api={canonical,raw,b64,deb64,hexhash,publicJwk,newKey,sign,verify,
 assertDispatch,makeRoute,verifyRoute,verifyHistory,acceptLeg,issue,
 checkOffer,respond,checkReply,syncTail};
g.Pocket003=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
