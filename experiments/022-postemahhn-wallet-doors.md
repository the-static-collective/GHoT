# PostEmahh'n MAIL-003 — Wallets As Doors, Not Money

**Status:** experimental P-256 wallet-style permission adapter in GHoT, stacked after MAIL-002. No coins, on-chain transactions, seed phrases, Ethereum/Solana/Bitcoin signing integration, or real print execution.

## Architectural hypothesis

A personal digital address receives sealed MAIL. A print station presents a signed, narrowly scoped challenge. The recipient's **wallet-style local key** signs only that challenge, preserving the exact mail, PDF SHA, intended station and short expiry. An optional independent guardian key may be required. A station checks its own recorded challenge, the current recipient mail release from MAIL-002, and each role proof before it places a PDF into the HELD print spool.

The wallet is a **keyring for permissions**, not a treasury. The signing interface should show human-readable purpose, receiving station, document hash, requested effect and expiration before displaying an Approve control.

### Demo mechanisms actually implemented

- Native GHoT P-256 signers and domain-separated canonical signed challenge/approval messages.
- Station challenge signed by station identity. Client signs only after verifying a trusted station key and passing explicit approval.
- One mandatory recipient owner role; optional second *independent* guardian key, forming a 2-of-2 print-staging policy.
- Station, mail crossing ID, exact PDF digest, one-time 128-bit nonce, policy hash, and expiry included in signed request.
- Challenge must exist in station's local issued registry. A used challenge is marked consumed. Repeated presentation is refused.
- Existing recipient-owned MAIL-002 signed release remains mandatory. A wallet-door approval cannot replace it.
- Successful staging signs a reLATTE ReceiptV0 asserting **HELD** only. No custody transfer, paper appearance, fund movement, token issuance, transaction broadcast, or financial wallet permission.

### Deliberate nonclaims

These are P-256 **prototype key controls**, not working MetaMask, Phantom, Bitcoin, Ledger, WalletConnect, or WebAuthn/passkey integrations. Cryptocurrency wallet chains use different verification profiles, and smart-contract wallets can require contract-based signature validation. Names, addresses and QR codes alone are not signer proof.

Do **not** connect a cryptocurrency spending key to print staging without dedicated, audited, chain-specific message verification. A test permit must never be interpretable as an EIP-7702 delegation, arbitrary transaction, token approval, or other financial act.

Future adapter registry candidates:

- `ghot.p256-local/v0`: tested P-256 ownership and optional guardian threshold.
- `webauthn.rp-bound/v1`: browser/passkey challenge and origin/RP verification; **not implemented**.
- `evm.siwe/v1`: nonce-based external wallet authentication; **not implemented**.
- `evm.eip712/v1`: typed permit signing with proper EIP-712 hashing and domain isolation; **not implemented**.
- `evm.eip1271/v1`: smart-contract wallet proof verification with the required chain context; **not implemented**.
- `bitcoin.bip322/v1`: Bitcoin proof of address control; **not implemented**.
- `solana.ed25519/v1`: independently defined domain-separated Ed25519 envelope; **not implemented**.

An optional external crypto-wallet identity may be *linked* as evidence of control, but must not inherit the PostEmahh'n address's mail decryption key, printer permission or control of deposits. Store no mnemonic/seed phrase.

## Tests

Use Python 3, OpenSSL and the same cryptography package from MAIL-002:

```bash
python3 -m pip install 'cryptography>=43,<47'
python3 -m unittest discover -s test -p test_postemahhn_wallet_door.py -v
```

The test generates independent source, recipient, guardian and station keys. It sends a sealed PDF, issues a station-signed challenge, approves it with a policy-specified key (or two), verifies the still-required recipient print release, stages HELD, and refuses a replay. Negative tests cover missing consent, forged station, forged guardian, different crossing, altered hash, expired request, unauthorized wallet role and forbidden asset powers.

### Future phone UX (not yet implemented)

Scan QR at physical station -> verify station public key against independently pinned station identity -> select received letter -> show typed summary -> phone signs short-lived challenge -> if required guardian cosigns -> select "release to this station" -> station holds printable PDF -> printer asks for **separate** locally authorized device action.

WebAuthn passkeys are a promising phone-native form, but they are **not equivalent** to the existing raw P-256 private-key signature: their authenticator data, origin and RP ID checks need a separate verifier.

**Laws:** WALLET != BANK. CONTACT ADDRESS != FUNDS ADDRESS. AUTHENTICATION != AUTHORIZATION. SIGNATURE != IDENTITY. STAGE != PRINT. PRINT != DELIVERED. GUARDIAN != OWNER. ONE SIGNATURE != UNIVERSAL PERMISSION.

References: [GHoT MAIL-002](https://github.com/the-static-collective/GHoT/pull/114), [PostEmahh'n constitutional source](https://github.com/the-static-collective/Jubilee-Engine-VM/pull/12), [EIP-712](https://eips.ethereum.org/EIPS/eip-712), [ERC-4361](https://eips.ethereum.org/EIPS/eip-4361), [WebAuthn](https://www.w3.org/TR/webauthn-3/).
