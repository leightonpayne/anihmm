---
icon: lucide/triangle-alert
---

# Exceptions

All public failures inherit from `AnihmmError`.

| Exception | Meaning |
| --- | --- |
| `AnimationConfigError` | Invalid rendering or playback option |
| `SequenceError` | Invalid sequence operation |
| `InvalidTransitionError` | Illegal node or transition |
| `FrameCompilationError` | A step or frame cannot be rendered |
| `SessionError` | Background playback failed |
| `AnimationTimeoutError` | A session did not stop before its timeout |

Catch the narrowest type useful to your application.

::: anihmm.exceptions
