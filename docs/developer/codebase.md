---
icon: lucide/map
---

# Codebase tour

Follow the data flow when deciding where a change belongs:

```text
HMMSequence -> Step -> HMMFrame -> Rich rows -> Live playback
```

## Packages

| Location | Responsibility |
| --- | --- |
| `models.py` | `Step`, `HMMFrame`, and shared types |
| `sequence/` | Path rules and step compilation |
| `render/` | Lattice rows, geometry, labels, and frame rendering |
| `playback/` | Timing, terminal output, and session lifecycle |
| `presets/` | Demo and random path builders |
| `exceptions.py` | Public exception hierarchy |

## Common changes

| Change | Start in |
| --- | --- |
| Built-in animation examples | `presets/demo.py` or `presets/random.py` |
| Legal state moves | `sequence/builder.py` |
| Step-to-frame validation | `sequence/compiler.py` |
| Transition shape | `render/geometry.py` |
| Rows or labels | `render/rows.py`, `render/emissions.py`, or `render/lattice.py` |
| Timing or live output | `playback/engine.py` |
| Background lifecycle | `playback/session.py` |
| Work-driven progress | `playback/progress.py` |
| Convenience options | `playback/options.py` or `playback/helpers.py` |
