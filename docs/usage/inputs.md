---
icon: lucide/code-xml
---

# Python API

Import the common API from `anihmm`.

## Choose the smallest API that fits

| Need | Use |
| --- | --- |
| Animate a block of work | `processing_animation()` |
| Advance a path as steps finish | `progress_animation()` |
| Animate an async block | `async_processing_animation()` |
| Start and stop manually | `AnimationSession` |
| Play an existing frame list | `animate_frames()` |
| Build a preset | `anihmm.presets` |
| Build a custom path | `HMMSequence` |
| Render one frame | `anihmm.render.render_frame()` |

## Context manager

The usual synchronous entry point is covered in the [Quickstart](quickstart.md).

Use the async version inside an event loop:

```python
from anihmm import ProcessingOptions, async_processing_animation

async with async_processing_animation(ProcessingOptions.random()):
    await run_your_work()
```

## Manual session

Use a session when a context manager does not fit your control flow:

```python
from anihmm import AnimationSession
from anihmm.presets import build_random_frames

session = AnimationSession(lambda: build_random_frames(seed=7), repeat=True)
session.start()
try:
    run_your_work()
finally:
    session.stop()
    session.wait()
```

`wait()` also surfaces errors raised by the playback thread. Its optional
`timeout` raises `AnimationTimeoutError` when the thread does not stop in time.

## Frames

Use the lower-level API when you need the frames themselves:

```python
from anihmm import animate_frames
from anihmm.presets import build_random_frames

frames = build_random_frames(columns=8, seed=7, emissions="SEARCHING")
animate_frames(frames)
```

### Render one finished frame

```python
from rich.console import Console

from anihmm.presets import build_random_path_frame
from anihmm.render import render_frame

frame = build_random_path_frame(columns=8, emissions="COMPLETE")
Console().print(render_frame(frame))
```

### Replace an animation with its result

Reuse one Rich console so the completed frame replaces the live region. Use the
same column count to keep the loading and result lattices aligned:

```python
from rich.console import Console

from anihmm import (
    PlaybackOptions,
    ProcessingOptions,
    print_frame_in_place,
    processing_animation,
)
from anihmm.presets import build_random_path_frame

columns = 8
console = Console()
with processing_animation(
    ProcessingOptions.random(columns=columns, emissions="SEARCHING"),
    PlaybackOptions.background(console=console),
):
    run_your_work()

print_frame_in_place(
    build_random_path_frame(columns=columns, emissions="COMPLETE"),
    console=console,
)
```

## Terminal behavior

Animations are disabled automatically for redirected or captured output. Set
`enabled=True` only when the destination supports terminal control output:

```python
from anihmm import PlaybackOptions, processing_animation

with processing_animation(playback=PlaybackOptions.background(enabled=True)):
    run_your_work()
```

Context managers surface playback failures when they exit. Manual sessions
must call `wait()` after `stop()` for the same reason.

## Imports

Use the package root for application code. Reach into a subpackage only for a
focused lower-level API:

| Package | Purpose |
| --- | --- |
| `anihmm.sequence` | Build and compile semantic paths |
| `anihmm.render` | Render frames and inspect geometry |
| `anihmm.playback` | Control playback and sessions |
| `anihmm.presets` | Build demo and random frames |
| `anihmm.exceptions` | Catch specific public errors |

Names prefixed with `_` are internal. Catch public exception classes rather
than matching message text. See the [Sequence Builder](sequences.md) for custom
paths.
