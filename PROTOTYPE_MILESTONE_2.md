# Strobato Prototype Milestone 2

## 1. Successful Live Test Summary

Strobato successfully followed a longer live piano test using microphone input and a matching MusicXML score.

This test moved beyond the first five-note C major validation and proved that the prototype can follow a full one-octave ascending melody in real time.

The live microphone pipeline produced usable note events, and the score follower tracked the musician across all eight measures.

## 2. Exact Sequence Tested

The musician played:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

The matching MusicXML score was:

```text
examples/c_major_longer_test.musicxml
```

The score uses one note per measure, making measure tracking easy to verify.

## 3. Result

Strobato tracked the performance from measure 1 through measure 8:

- `C4` to measure 1
- `D4` to measure 2
- `E4` to measure 3
- `F4` to measure 4
- `G4` to measure 5
- `A4` to measure 6
- `B4` to measure 7
- `C5` to measure 8

## 4. Tracking Status

Tracking status stayed locked from `D4` onward.

This is important because the system did not merely identify isolated notes. It maintained a continuing estimate of the musician's position as the melody advanced through the score.

## 5. Confidence

Confidence reached `0.83`.

That is a strong result for the current prototype because the system is still using:

- simple monophonic pitch detection
- lightweight note-event compression
- a small stateful score follower
- no machine learning model
- no chord detection

## 6. Current Architecture

The current architecture remains SDK-first.

For score loading:

```text
MusicXML score
  -> parser
  -> score reference map
  -> flattened expected note timeline
```

For live following:

```text
microphone audio
  -> pitch estimation
  -> octave stabilization
  -> startup warmup filtering
  -> transition-glitch filtering
  -> same-note repeat compression
  -> StrobatoEngine
  -> current measure / note index / confidence / tracking status / page-turn signal
```

The central SDK object is still `StrobatoEngine`. A host sheet music app can load a MusicXML score, send note events into the engine, and receive score-following output.

## 7. What This Proves Technically

This milestone proves that Strobato can complete the core live-following loop:

```text
live piano audio -> detected notes -> compressed note events -> score position
```

It also proves:

- MusicXML can be used as the expected score source.
- The SDK can track a live performer across multiple measures.
- The tracker can stay locked over a longer simple melody.
- The microphone pipeline is good enough for controlled monophonic validation.
- Strobato can expose useful developer-facing state: measure, note index, confidence, tracking status, and page-turn signal.

This is meaningful because it demonstrates the core product premise: Strobato can act as invisible score-following infrastructure inside another sheet music app.

## 8. What Remains Limited / Experimental

The prototype is still experimental.

Current limitations:

- Monophonic only: one clear note at a time.
- No chord detection.
- No polyphonic piano transcription.
- No advanced ML pitch detection yet.
- Real piano overtones can still create occasional noisy notes.
- Note-event compression is tuned for simple tests, not all musical phrasing.
- Rhythm and tempo are only lightly represented.
- Page turns are still threshold-based and need stronger live validation.
- The demo is terminal-based and developer-facing.

The live microphone path should continue to be treated as a prototype until it has been tested across more melodies, tempos, rooms, microphones, and instruments.

## 9. Recommended Next Milestones

Recommended next technical milestones:

1. Test a simple melody beyond a scale.
2. Connect the visual host-app demo to live tracking output.
3. Record a page-turn demo using a longer score.
4. Improve noisy-note rejection using real test logs.
5. Define a future ML/inference roadmap for stronger pitch and onset detection.

The safest next step is a simple melody that is still monophonic but less predictable than an ascending scale.

## 10. Exact Command To Reproduce The Test

Install optional microphone dependencies:

```bash
python3 -m pip install sounddevice numpy
```

Run the full-octave live microphone score-following test:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --score examples/c_major_longer_test.musicxml --candidate-frames 2 --startup-frames 3 --repeat-gap-seconds 0.35
```

Play this sequence clearly, one note at a time:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

Optional CSV logging:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --score examples/c_major_longer_test.musicxml --candidate-frames 2 --startup-frames 3 --repeat-gap-seconds 0.35 --log runs/c_major_longer_live_test.csv
```
