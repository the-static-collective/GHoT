# Experiment 001 — One Body

## Question

Can one ordinary computer express itself as a GHoT body, accept a bounded task, execute locally, and leave a reconstructible receipt without internet access?

## Procedure

From the repository root:

```bash
python3 ghot/reference_node.py probe
python3 ghot/reference_node.py echo "hello heap"
python3 ghot/reference_node.py hash "hello heap"
python3 ghot/reference_node.py info
```

Inspect:

```bash
find .ghot -type f -maxdepth 2 -print
```

## Expected evidence

- stable local `node-id`;
- BODY record containing host architecture/resources;
- TASK record for each bounded request;
- RECEIPT record tied to the task;
- SHA-256 hash over returned output;
- no network requirement.

## Pass

Experiment passes if the machine can be disconnected from the internet before execution and all four commands still work.

## Next mutation

Experiment 002 will run the reference node on two machines and cross one task over an isolated LAN.
