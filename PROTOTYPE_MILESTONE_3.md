# Strobato Prototype Milestone 3

## 1. Successful Visual Live Demo Summary

Strobato successfully powered a visual host-app demo from live piano input.

The browser-based demo was framed as a generic sheet music platform, "Host Sheet Music App," with Strobato running as invisible SDK infrastructure underneath. Live microphone input flowed through the Strobato pipeline and updated the on-screen current measure, confidence, tracking status, and compressed note window.

This milestone proves that Strobato is not only producing terminal output. It can drive a visible sheet music experience that resembles how a third-party app could embed the SDK.

## 2. What Worked

The visual live microphone demo successfully showed:

- Browser updates from live piano input.
- Current measure advancing through the score.
- Current measure reaching measure 8.
- Tracking status staying locked.
- Confidence reaching `0.83`.
- Compressed note window showing the full sequence:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

The tested score was:

```text
examples/c_major_longer_test.musicxml
```

## 3. Evidence From The Browser State

Observed browser state during the successful run:

- `current_measure`: reached `8`
- `confidence_score`: reached `0.83`
- `tracking_status`: stayed `locked`
- `compressed note window`: `C4, D4, E4, F4, G4, A4, B4, C5`

This means the live pipeline successfully connected:

```text
live piano audio -> detected note events -> score follower -> browser UI
```

## 4. Remaining Issue: UI / Browser Lag Around G4

One issue appeared during the run: the browser UI lagged around `G4`.

This appears to be a visual/demo responsiveness issue rather than a core score-following failure. The SDK still reached measure 8 and remained locked, but the browser update loop felt slightly delayed.

This should be addressed before an investor-facing recording, because the visual demo needs to feel smooth and immediate.

## 5. Current Architecture From Live Piano To Browser Update

The current live visual architecture is:

```text
live piano audio
  -> microphone input
  -> pitch estimation
  -> octave stabilization
  -> startup warmup filtering
  -> transition-glitch filtering
  -> same-note repeat compression
  -> compressed note window
  -> StrobatoEngine
  -> current measure / confidence / tracking status / page-turn signal
  -> local browser visual demo
  -> highlighted measure in Host Sheet Music App
```

The browser is not the core product. It is a demonstration surface showing how a third-party sheet music app could use Strobato's SDK output.

## 6. Why This Matters For The SDK / Product Vision

This milestone makes the product vision tangible.

Strobato is intended to be invisible infrastructure, not a standalone sheet music app. This demo shows that a host app can keep the user-facing sheet music experience while Strobato supplies live-following intelligence underneath.

For the SDK/product story, this proves:

- The SDK can load a MusicXML score.
- The SDK can follow live piano input.
- The SDK can return useful live state.
- A host interface can react to that state.
- Measure highlighting and future page turning can be powered by Strobato without making Strobato the visible consumer app.

This is a meaningful investor-demo step because the value is visible: a pianist plays, and the sheet music interface follows.

## 7. Recommended Next Milestones

Recommended next milestones:

1. Reduce UI polling and browser lag.
2. Add a demo recording workflow.
3. Improve visual page-turn animation.
4. Test one simple non-scale melody.
5. Prepare an investor-facing demo script.

The next best technical step is smoothing the browser update loop so the visual layer feels as reliable as the SDK state underneath.

## 8. Exact Command To Reproduce The Visual Live Demo

Install optional microphone dependencies:

```bash
python3 -m pip install sounddevice numpy
```

Run the visual live microphone demo:

```bash
PYTHONPATH=src python3 examples/visual_demo.py --score examples/c_major_longer_test.musicxml --live
```

Open the browser:

```text
http://127.0.0.1:8765
```

Play this sequence clearly, one note at a time:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

Expected successful result:

- Current measure reaches `8`
- Confidence reaches about `0.83`
- Tracking status remains `locked`
- Compressed note window shows `C4, D4, E4, F4, G4, A4, B4, C5`
