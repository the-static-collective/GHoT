# MAIL-005 — External Wallet Witnesses, Not Financial Wallet Permissions

Status: bounded independent verifier adapter in GHoT, stacked after MAIL-004.

## New capability

A Solana-compatible Ed25519 wallet can sign an **off-chain** PostEmahh'n message as evidence of key control. That witness is not a print permit, token authority, blockchain transaction or transfer of account ownership.

There are TWO separately verified signatures to associate the wallet with the PostEmahh'n recipient:

- the recipient's existing P-256 postal key signs the wallet linkage;
- the Ed25519 external wallet signs the same strictly typed linkage.

A later wallet signature can witness one specific existing MAIL-003 station request, including its crossing/request ID, PDF SHA-256, recipient address, station and linked wallet ID. Replaying the witness for a different request fails. Its temporal bounds come from the signed MAIL-003 challenge and temporary wallet linkage.

The proof is generated for wallet signMessage on the precise UTF-8 bytes returned by solana_link_bytes or permit_bytes. It is verified against the canonical 32-byte Solana Ed25519 address decoded from base58. No wallet provider or chain RPC is contacted by the server module.

## Independent, deliberately incompatible verifier profiles

| Profile | Status |
| --- | --- |
| solana.ed25519-signed-message/v0 | Executable off-chain cryptographic proof |
| evm.siwe-eip4361/v1 | Explicitly unsupported |
| evm.typed-eip712/v1 | Explicitly unsupported |
| evm.smart-eip1271/v1 | Explicitly unsupported |
| bitcoin.bip322/v1 | Explicitly unsupported |

The EVM and Bitcoin paths must **not** use the Solana Ed25519 verifier; they require their respective standards-based semantics. Unsupported profiles raise errors and cannot be treated as verified. Smart-contract wallet proofs may depend on the selected chain and current on-chain code/state; no such authority is claimed by GHoT.

## Run

    python3 -m pip install 'cryptography>=43,<47' 'cbor2>=5.6,<6'
    python3 -m unittest discover -s test -p test_postemahhn_external_wallets.py -v

The test uses independent local Ed25519/P-256 test keys. It proves linkage and one-request authentication, then rejects wrong wallet/owner signatures, swapped request/recipient, altered documents, expired link, inappropriate financial permissions, and chain-profile impersonation.

There is no connected wallet UI, no hardware wallet support, no public account binding service and no real-world print submission. The existing MAIL-002 recipient release, MAIL-003 owner/guardian approval and MAIL-004 passkey gate remain separately necessary for the composite print-door workflow.

## Next adapters

Ethereum: use SIWE (ERC-4361) with ERC-191 verification for EOAs, and ERC-1271 contract signature checks for smart-contract accounts on the selected chain. EIP-712 requires proper typed-data hashing and signing, not raw JSON signatures.

Bitcoin: use actual BIP-322 script and witness-stack verification, including the relevant script/consensus checks. Do not silently accept legacy signmessage signatures as equivalent.

Solana: future wallet-provider browser integration may request signMessage with the exact typed bytes. Never request signTransaction or signAllTransactions for PostEmahh'n mail authentication.

WALLET != BANK. ADDRESS LINK != WALLET CUSTODY. AUTHENTICATED != AUTHORIZED. VERIFIED != PRINTED. NO SIGNED MESSAGE MAY GRANT SPENDING OR TOKENS.

References:
- https://www.w3.org/TR/webauthn/
- https://eips.ethereum.org/EIPS/eip-4361
- https://github.com/bitcoin/bips/blob/master/bip-0322.mediawiki
- MAIL-004: https://github.com/the-static-collective/GHoT/pull/116

## Browser signMessage laboratory (unverified with a real extension)

The new static browser proof page is web/postemahhn-external-wallet-lab.html. On a browser with an injected Solana-compatible wallet implementing connect() and signMessage(), the user may:

1. Paste a PostEmahh'n owner-approved link body, inspect the wallet address and narrow permission, and explicitly ask that wallet to sign the exact domain-separated linkage bytes.
2. Export the signed link packet to the verifier to prove ownership of the Ed25519 public address.
3. After separately verifying a real MAIL-003 station challenge with the trusted GHoT station key, paste that request, the link packet, and the recipient policy; the wallet can sign exactly that request as an off-chain verification message.
4. Carry the resulting proof JSON back to verify_external(). Wallet sign-in never replaces recipient mail release, guardian approval, passkey user verification, or device-local print admission.

This is a manual demonstration page, not a connected hosted PostEmahh'n wallet app. Browser provider compatibility and live user approval have **not** been tested. The page cannot independently authenticate the incoming station signature; always use the trusted server verifier before asking the wallet to sign. The signing bytes are exposed for inspection and have separate fixed application domain prefixes.
