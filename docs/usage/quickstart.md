---
icon: lucide/package-open
---

# Quickstart

Wrap the work you want to animate:

```python
from anihmm import ProcessingOptions, processing_animation

with processing_animation(
    ProcessingOptions.random(emissions="SEARCHING")
):
    run_your_work()
```

The animation runs in the background and stops when the block exits. When
output is redirected or captured, `anihmm` stays quiet automatically.

## Configure it

Pass options to `ProcessingOptions.random()` for the path and
`PlaybackOptions.background()` for playback.

| Option               | Effect                                           |
| -------------------- | ------------------------------------------------ |
| `columns`            | Set the lattice width                            |
| `emissions="TEXT"`   | Emit fixed text on a random path                 |
| `emissions=5`        | Emit exactly five random symbols                 |
| `seed=7`             | Reproduce the same series of changing paths      |
| `fps`                | Set playback speed                               |
| `hold_final_seconds` | Hold the last frame before repeating             |

Next, browse the [visual examples](example.md) or choose a lower-level API in
the [Python API guide](inputs.md).
