# RADIO HOUSE 004 — clickable Linux node + signed LAN experiment

This is runnable experimental software, not an installed Rock Impact or Kinship service. A **local** operator controls when a worker computer may contribute spare computation. It builds on RADIO HOUSE 001 / 002 / 003 and uses GHoT's existing reLATTE P-256 signature profile.

## Real click interface

The worker serves a browser dashboard exclusively on http://127.0.0.1:8787/ with:
- **Enable / Withdraw** voluntary compute. Disabled is the default.
- **Recording / Live / Editing / Confirm idle / Unknown** — manual operator states.
- An OBS/FFmpeg/arecord process check (any matching process forces HOLD).
- Existing GHoT Linux power, thermal, and CPU probe (missing evidence => HOLD).
- Signed inbox proposals, **Approve locally**, **Step ×1 / ×10**, **Cancel**, and **Verify**.

**A click is not a grant from a church, a radio station, or reLATTE.** Incoming signed messages remain proposals until the receiving computer's operator explicitly approves. No periodic execution worker exists: only the owner's clicks can advance work, at most ten 256-byte chunks per call. The worker recomputes and signs a result; the requester independently verifies it.

## Bootstrap two separate operators

Python 3.10+, OpenSSL and GHoT repository checkout on both Linux computers.

On the **requesting** computer:

~~~sh
python3 -m ghot.radio_house_004 requester-init --root ~/radio-house-requester
python3 -m ghot.radio_house_004 identity --root ~/radio-house-requester --role requester > requester-public.json
~~~

Transfer **only** requester-public.json by a separately verified human channel to the worker operator. Never share the private PEM.

On the **worker** computer (only after a real invitation):

~~~sh
python3 -m ghot.radio_house_004 worker-init --root ~/radio-house-worker \
  --requester-pin /verified/path/requester-public.json
python3 -m ghot.radio_house_004 identity --root ~/radio-house-worker --role worker > worker-public.json
python3 -m ghot.radio_house_004 serve --root ~/radio-house-worker \
  --admin-port 8787 --intake-port 8788
~~~

Transfer only worker-public.json to the requester. Verify key fingerprints by another trusted channel.

Locally open **http://127.0.0.1:8787/** in the **worker's** browser. Do not expose or SSH-forward that admin port. The second HTTP listener, port 8788, accepts only exact signed proposals and signed-result queries, not approvals or media commands.

## Physical network route

Both listeners bind only to 127.0.0.1, by design. For two actual Linux machines, enable the separately permitted **SSH forwarding-only** link. Ensure the worker's sshd grants a dedicated key the permitted open destination **only** 127.0.0.1:8788. Example authorized_keys restrictions for a separately provisioned tunnel account:

~~~text
restrict,port-forwarding,permitopen="127.0.0.1:8788" ssh-ed25519 <PUBLIC-KEY-FROM-REQUESTER> radio-house-tunnel
~~~

SSH account restrictions and known_hosts host-key pinning need independent system administrator review. Never reuse a privileged operator account for tunneling. On the requester:

~~~sh
ssh -N -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8788:127.0.0.1:8788 radio-tunnel@WORKER_HOST
~~~

This is a **real authenticated SSH transport path**; the GHoT payload is separately P-256 signed and still needs worker-owner approval. No automatic port opening, domain configuration or deployment is performed by this repository. The two actual physical machines must consent and be field-tested.

On the requester:

~~~sh
python3 -m ghot.radio_house_004 send --root ~/radio-house-requester \
  --worker-pin /verified/path/worker-public.json \
  --job-id public-work-001 --text "A deliberately public test input"
~~~

This saves a signed original bundle in the local requester outbox, then posts it through 127.0.0.1:8788. The worker **does not automatically compute**. Its human operator must click **Enable**, **Confirm idle** and **Approve locally**, then Step. If OBS is running or monitoring is unavailable, the gate HOLDS; do not bypass this with synthetic power providers outside CI.

To retrieve the signed output, use the saved original crossing file from the outbox (replace the hash with the printed crossing ID):

~~~sh
python3 -m ghot.radio_house_004 poll --root ~/radio-house-requester \
  --worker-pin /verified/path/worker-public.json \
  --bundle ~/radio-house-requester/outbox/relatte-crossing-v0_<SHA256>.json
~~~

The requester recomputes the exact SHA-256 locally, independently verifies the worker's native signed HELD and EXECUTED receipts, then retains a copy under its own received directory. A crossing expires in at most 900 seconds; a later experiment must add a renewable authenticated result-query protocol for asynchronous jobs.

## Proof and limitations

CI uses **two actual separate OS processes**, two independent directories/private keys, two loopback TCP listeners, HTTP source intake, manual click-equivalent owner API calls and a signed result returned to the requester CLI. It also runs 001–003 inherited safety tests and the 004 hostile suite.

The software can be **installed on separate Linux computers with the SSH steps above**, but the CI proof **is not** a physical two-machine test or a live Nigeria–Minnesota link.

Before any actual ministry workstation runs this during broadcasting: independently configure OBS WebSocket monitoring for recording/streaming states and resource reservations with Linux cgroups/limits. Merely clicking idle and scanning process names cannot guarantee stream safety; the process scanner deliberately blocks all OBS processes even if they appear idle. GHoT's power probe may fail closed on hardware without accessible sensors. A localhost admin dashboard is for a trusted single-user machine; it is not hardened for untrusted local accounts. Dedicated SSH tunnel provisioning requires its own system security review.

No cloud accounts, no personal ministry, counseling or donor information, no recordings or copyrighted material, no arbitrary remote shell, no radio rights, no real payment/compensation or guaranteed energy savings. Public ASCII text hashing is the **only** externally proposed computation in 004. Native reLATTE signing and receipt **syntax** is used; no sovereign R3 receiver capability was conferred.

**SIGNED != AUTHORIZED. ARRIVED != ADMITTED. IDLE CLAIM != SAFE LIVESTREAM. LOCAL RECEIPT != DONATION. COMPUTER != CHURCH.**
