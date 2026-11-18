---
icon: lucide/layers
---

# Rendering pipeline

## 1. Describe a step

`HMMSequence` produces `Step` objects. A step can contain:

- committed transitions
- one transition being previewed
- emission labels
- temporary flashes

Steps express intent, not screen coordinates.

## 2. Compile a frame

`compile_step()` validates the path and turns it into an `HMMFrame`. The frame
stores active nodes, cells, styles, overlays, and labels without rendering text.

## 3. Resolve geometry

`transition_cells()` maps transitions such as `M1 -> D2` to lattice cells. If a
path is semantically correct but looks wrong, inspect this layer first.

## 4. Render rows

`render_frame()` builds Rich text rows, then applies cell styles, glyph overlays,
and emission labels. Reserved label rows keep every frame the same height.

## 5. Play frames

`animate_frames()` owns timing, repetition, cancellation, and non-terminal
auto-disable. `AnimationSession` and `AsyncAnimationSession` add background
lifecycle control around that same engine. `ProgressSession` maintains its own
persistent Rich `Live` region, compiling settled and candidate frames as
application work advances the path.

## Debug in this order

1. Check the `Step` transition names.
2. Check the compiled `HMMFrame`.
3. Check `transition_cells()` output.
4. Check row and emission rendering.
5. Check `playback/engine.py` or `playback/progress.py` for timing, refresh, or
   state-advance artifacts.
