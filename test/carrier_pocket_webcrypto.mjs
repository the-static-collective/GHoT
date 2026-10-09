#!/usr/bin/env node
// POSTAL-CORPS-002 WebCrypto interoperability fixture.
// PRIVATE TEST JWK is written only to the local temporary test folder.
// Production pocket never exports the nonextractable private CryptoKey.
import {readFileSync,writeFileSync} from "node:fs";
import {webcrypto} from "node:crypto";
const {subtle}=webcrypto;
const enc=new TextEncoder();
const [cmd,...params]=process.argv.slice(2);
const canon=v=>v===null||typeof v!=="object"?
  JSON.stringify(v):
  Array.isArray(v)?"["+v.map(canon).join(",")+"]":
  "{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+canon(v[k])).join(",")+"}";
const bytes=s=>enc.encode(s);
const b64=b=>Buffer.from(b).toString("base64url");
const fromB64=s=>Buffer.from(s,"base64url");
const hash=async b=>Buffer.from(await subtle.digest("SHA-256",b)).toString("hex");
const onlyPub=jwk=>({kty:jwk.kty,crv:jwk.crv,x:jwk.x,y:jwk.y});
async function importPub(pub){return subtle.importKey(
  "jwk",onlyPub(pub),{name:"ECDSA",namedCurve:"P-256"},false,["verify"]);
}
async function verify(pub,message,sig){
  return subtle.verify({name:"ECDSA",hash:"SHA-256"},await importPub(pub),
                       fromB64(sig),bytes(message));
}
if(cmd==="generate"){
  const [out]=params;
  const kp=await subtle.generateKey({name:"ECDSA",namedCurve:"P-256"},true,["sign","verify"]);
  const pub=onlyPub(await subtle.exportKey("jwk",kp.publicKey));
  const priv=await subtle.exportKey("jwk",kp.privateKey);
  writeFileSync(out,JSON.stringify({public:pub,private:priv},null,2));
  process.stdout.write("generated-ephemeral-webcrypto-fixture\n");
}else if(cmd==="respond"){
  const [identityFile,routeFile,qrFile,out]=params;
  const keys=JSON.parse(readFileSync(identityFile));
  const route=JSON.parse(readFileSync(routeFile));
  const q=JSON.parse(readFileSync(qrFile));
  const b=q.body,evt=b.event;
  if(b.responder!=="relay"||b.initiator!=="carrier1"||
     evt.action!=="HANDOFF_RELAY"||
     b.scope!=="SYNTHETIC_CUSTODY_CLAIM_ONLY")throw Error("Unexpected fixture scope");
  const own=route.role_pins.relay;
  if(canon(keys.public)!==canon(own))throw Error("Browser public key not registered");
  const copy={...route};delete copy.source_signature;
  if(!await verify(route.role_pins.origin,
    "PostEmahh-n-Postal-Corps-001-Route|"+canon(copy),
    route.source_signature))throw Error("Origin route proof invalid");
  if(!await verify(route.role_pins.carrier1,
    "PostEmahh-n-Carrier-Pocket-Challenge-v0|"+canon(b),
    q.initiator_proof))throw Error("QR challenge proof invalid");
  if(!await verify(route.role_pins.carrier1,
    "PostEmahh-n-Postal-Corps-001-Event|"+canon(evt),
    q.event_proof))throw Error("QR event proof invalid");
  const actualRouteHash=await hash(bytes(canon(route)));
  if(b.route_hash!==actualRouteHash||b.parcel_sha256!==route.parcel_sha256)
    throw Error("Wrong route/parcel");
  const now=Math.floor(Date.now()/1000);
  if(now>b.expires_at||now<b.issued_at-60)throw Error("Expired QR challenge");
  const body={
    schema:"postemahhn.carrier-pocket-response/v0",
    challenge_sha256:await hash(bytes(canon(q))),
    nonce:b.nonce,
    event_sha256:await hash(bytes(canon(evt))),
    responder:"relay",scope:"SYNTHETIC_CUSTODY_CLAIM_ONLY",
  };
  const key=await subtle.importKey("jwk",keys.private,
    {name:"ECDSA",namedCurve:"P-256"},false,["sign"]);
  const sign=async payload=>b64(await subtle.sign(
    {name:"ECDSA",hash:"SHA-256"},key,bytes(payload)
  ));
  const response={
    challenge:q,response_body:body,
    response_proof:await sign("PostEmahh-n-Carrier-Pocket-Response-v0|"+canon(body)),
    event_proof:await sign("PostEmahh-n-Postal-Corps-001-Event|"+canon(evt)),
  };
  writeFileSync(out,JSON.stringify(response,null,2));
  process.stdout.write("native-WebCrypto-ES256-Qr-response-created\n");
}else{
  throw Error("usage: node carrier_pocket_webcrypto.mjs generate OUT | respond IDENTITY ROUTE QR OUT");
}
