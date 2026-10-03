# Executor Pantry

The Executor Pantry is how a GHoT body answers:

> **What can this body actually do right now?**

It does not assume identical software across machines. It inspects the local machine for known executors and translates what it finds into bounded capability offers.

## V0 executors

- Python
- Git
- ffmpeg
- ffprobe
- llama.cpp
- whisper.cpp
- Piper
- ImageMagick

The registry is deliberately explicit. Discovery is not permission to execute arbitrary programs.

## Example

A machine with Python, Git and ffmpeg/ffprobe may emit roughly:

```json
{
  "executors": [
    {
      "name": "ffprobe",
      "available": true,
      "path": "/usr/bin/ffprobe",
      "capabilities": [
        "runtime.ffprobe.version",
        "media.probe"
      ]
    }
  ],
  "offers": [
    {
      "capability": "media.probe",
      "executor": "ffprobe",
      "available": true
    }
  ]
}
```

Another body without ffprobe simply does not advertise `media.probe`.

That difference is the point.

## Authority boundary

The pantry has no generic `shell.exec`.

Each useful executable gets an adapter that owns:

- accepted input shape;
- exact subprocess arguments;
- timeout;
- allowed filesystem behavior;
- network behavior;
- expected output shape.

The remote network layer can request a capability. It cannot provide arbitrary command lines.

## First real adapter

`media.probe` accepts a **local file path only** and invokes ffprobe with fixed arguments to return structured media metadata.

This is intentionally modest. It proves that an installed external tool can become a useful GHoT organ without exposing a remote shell.

## Future adapters

The next practical set:

- `media.transcode.audio`
- `media.transcode.video`
- `speech.transcribe.local`
- `speech.synthesize.local`
- `llm.infer.local`
- `image.inspect.local`
- `image.transform.local`
- `git.inspect.local`

Each should remain separately bounded and independently withdrawable.
