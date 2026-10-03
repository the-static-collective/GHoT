# External Adapter Manifest 001

GHoT may execute donor-owned bounded instruments without learning donor semantics.

The owner opts in explicitly through:

```text
GHOT_ADAPTER_MANIFESTS=/path/to/adapter-manifest.json
```

Multiple manifests use the platform path separator.

GHoT does **not** crawl arbitrary repositories looking for executable code.

## Manifest

```json
{
  "schema": "ghot.external-adapter-manifest/v0",
  "adapter_id": "example.instrument",
  "capabilities": [{
    "capability": "creative.example.transform",
    "protocol": "stdin-json/stdout-json-v0",
    "command": "node",
    "args": ["adapter.cjs"],
    "timeout_seconds": 10,
    "limits": {
      "network": false,
      "arbitrary_shell": false
    }
  }]
}
```

The command receives the task payload as JSON on stdin and must emit one JSON object on stdout.

## Boundary

The manifest declares an executable capability. It does not transfer donor semantics or authority into GHoT.

```text
MANIFEST != AUTHORITY
CAPABILITY != EXECUTION
GHOT != DONOR SEMANTICS
ADAPTER PROCESS != ARBITRARY SHELL
```

Only exact manifest-declared capabilities may be run through this path. There is no caller-supplied command or shell string.
