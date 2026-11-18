---
icon: lucide/git-branch
---

# Sequence builder

Use `HMMSequence` to describe a path in states instead of screen coordinates.

```python
from anihmm import HMMSequence, compile_steps

sequence = HMMSequence()
for symbol in "SEARCH":
    sequence.settle("M")
    sequence.emit(symbol)
sequence.finish()

frames = compile_steps(sequence.build())
```

## Actions

| Method | Effect |
| --- | --- |
| `cycle("M")` | Preview the next state without committing it |
| `settle("M")` | Move to and commit the next state |
| `emit("A")` | Label the current match or insertion state |
| `flash_current()` | Flash the current state for one step |
| `finish()` | Fill remaining bounded columns with deletions, then commit `E` |

State kinds are `M` (match), `I` (insertion), and `D` (deletion). Methods return
the sequence, so calls may be chained.

Every settled match or insertion state must emit exactly one symbol before the
sequence can preview or commit another transition, finish, or build. Deletion
states do not emit.

## Bounds and validation

Pass `columns` to keep the path inside a fixed lattice:

```python
sequence = HMMSequence(columns=8)
```

When a bounded path finishes early, `finish()` advances through a deletion
state for every remaining column before moving to `E`. The builder rejects
illegal moves, duplicate emissions, and invalid terminal symbols. Failures are
reported as `SequenceError` or `InvalidTransitionError`.

Each compiled frame contains the full path so far. Retaining every frame uses
quadratic memory as a path grows, so custom animations should remain
terminal-sized.

For direct `Step` construction, import `Step`, `compile_step`, and
`compile_steps` from `anihmm.sequence`.
