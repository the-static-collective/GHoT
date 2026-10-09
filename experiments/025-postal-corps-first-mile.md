# POSTAL-CORPS-001 — The First Mile

**Status: signed synthetic two-carrier custody chain only.** No actual people, post, property, cash, coins, payment, or real carrier route was operated.

## Source ownership

- LemonPRESS Dispatch Gate 001 owns recipient fulfillment and dispatch states; pinned source PR 17 at SHA 62a20ebf1e5b65ed8ff1ad3559e2b8779e4656be.
- Full Measure owns Garden pledges, confirmed Deeds, and authoritative events. Here we emit a local, unadmitted Full Measure postal quest draft only; no native Full Measure event is created.
- PENNY-014 owns work, custody, release, and financial authorization. Source PR 17 pinned at a36777cb87bcfb6b7706b910ba18c4c4b24c73a3. We only produce candidate work data for separately witnessed native review.
- GHoT owns this signable carrier simulation, using its existing reLATTE-compatible P-256 signature profile.

## Ten-step synthetic handoff

One native LemonPRESS Dispatch Gate record in service_selected state is hashed and origin-signed. One simulated parcel hash and six distinct pinned role identities are attached.

    OFFERED
      -> carrier1 accepts
      -> origin + carrier1 sign pickup claim
      -> carrier1 + relay sign handoff claim
      -> carrier2 accepts
      -> relay + carrier2 sign next pickup claim
      -> carrier2 + recipient sign delivery claim
      -> carrier1 signs work report
      -> carrier2 signs work report
      -> independent witness signs leg1 assessment
      -> independent witness signs leg2 assessment
      -> WORK_REVIEW_READY

REFUSE_LEG1, REFUSE_LEG2, LOST_LEG1, LOST_LEG2 and recipient DISPUTE are allowed at bounded states. They stop progression. Dispute after review removes the read-only proposed work candidates. These signatures indicate claims, not independently observed custody or delivery. Cold replay refuses tampered route, prior hashes, signatures, signer roles and impossible or duplicated transitions.

## Source contract validation

Native source proof uses the real LemonPRESS Dispatch Gate 001 Python module to create a deliberately synthetic service-selected record without postage or tender. GHoT validates and signs it, then emits candidate projections for Full Measure and PENNY.

The Full Measure projection always says NOT_AWARDED and LOCAL_PROPOSAL_ONLY. It is a source-informed draft, not a confirmed Full Measure Deed or official event.

The PENNY projection always reports 0 active/released units, 0 physical book coins, 0 payment and 0 admitted Treasury events. If both synthetic witness claims exist, exactly two candidate work payloads become available for separate source review. The native PENNY-014 test shows:
- unsigned proposals alone do not mutate PENNY;
- an attempted native WORK without independent work-witness signature is refused;
- a **separately** synthetic, explicitly authorized PENNY witness may admit the two sample WORK records; result PENDING 2, ACTIVE 0, BOX COINS 0, CASH 0.
This is not real work, a wage, a public token, or physical custody.

## Run

Python 3 + OpenSSL:

    python3 -m unittest discover -s test -p test_postal_corps.py -v

Against pinned independent checkouts:

    python3 test/postal_corps_native_lemon.py --lemon /path/to/lemonPRESS --out /tmp/postal-candidates.json
    node test/postal_corps_native_penny.mjs /tmp/postal-candidates.json /path/to/Jubilee-treasury/src/penny-work-matter-014.mjs

The dedicated GitHub Actions job checks exact repo commit pins and archives only public-safe specimen candidate JSON. Signing keys remain ephemeral in the runner and are not archived.

## Real-world deployment gates

1. **Postal law:** in the United States, the Private Express Statutes regulate compensated private carriage of letters. A PENNY, quest reward, or barter does not automatically create an exemption. Review eligible goods, the definition of a letter, existing-carrier handoffs, and local law before any live delivery.
2. **Labor/consent:** explicitly offered, lawful, voluntary work with real compensation arrangements independent of unsupported future token backing; people may refuse safely.
3. **Security/privacy:** authenticated carrier onboarding, revocation, trusted handoff witnesses, no private residential addresses in public proofs, minimized access to routing data.
4. **Physical custody:** genuine seal, sender, site and recipient observation; signed report is not proof that a physical object actually moved.
5. **Full Measure:** human-authorized real Garden project, pledge, report and separately confirmed Deed via source API. The GHoT proposal is not canonical.
6. **PENNY:** actual agreed work terms, source-authorized work proof, legal and independent backing audit, settlement compliance before any live payout.
7. **Operational reliability:** durable claim-once spool, crash recovery and dispute handling before sending people into the field. This prototype is in-memory only.

**Laws:** QUEST != OBLIGATION. ROUTE PROPOSAL != CARRIER CONTRACT. HANDOFF CLAIM != POSSESSION. WITNESS != DEED. WORK CANDIDATE != PENNY. PENDING != PAYABLE. TOKEN != CASH. LABEL != POSTAGE. REFUSAL IS LAWFUL.

Cross-project references:
- LemonPRESS PR #17: https://github.com/the-static-collective/lemonPRESS/pull/17
- PENNY-014 PR #17: https://github.com/the-static-collective/Jubilee-treasury/pull/17
- Full Measure: https://github.com/the-static-collective/full-measure-world-layer
- PostEmahh'n source constitution: https://github.com/the-static-collective/Jubilee-Engine-VM/pull/12
