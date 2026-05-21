# Strobato Prototype Milestone 1

## 1. What Strobato Can Do Now

Strobato can now follow a simple live piano melody through a MusicXML score.

The current prototype can:

- Load a MusicXML score.
- Convert that score into an internal reference map.
- Accept simulated note input for stable SDK testing.
- Accept experimental live microphone input.
- Convert rough microphone pitch estimates into note names.
- Compress noisy microphone detections into musical note events.
- Track the musician's current measure and note index.
- Return confidence, tracking status, and page-turn signals through the SDK.

The most important result is that Strobato is still SDK-first. It is not a standalone sheet music app. It is infrastructure that another sheet music platform could embed.

## 2. What The Real Piano Test Proved

The first real live score-following test worked against the dedicated C major validation score.

The musician played:

```text
C4, D4, E4, F4, G4
```

Strobato tracked:

- `C4` to measure 1
- `D4` to measure 2
- `E4` to measure 3
- `F4` to measure 4
- `G4` to measure 5

Tracking stayed mostly locked, with confidence around `0.78-0.80`.

There was one stray `B3` before `G4`, but the tracker recovered and still reached the correct final measure. That matters because real microphone input will never be perfectly clean.

## 3. Current Architecture

The prototype is organized as a small SDK pipeline:

```text
MusicXML score
  -> score parser
  -> score reference map
  -> stateful score tracker
  -> SDK result
```

For live audio, the pipeline is:

```text
microphone audio
  -> pitch estimate
  -> stabilized note name
  -> note-event compression
  -> StrobatoEngine
  -> current measure / confidence / tracking status / page-turn signal
```

The main SDK entry point is `StrobatoEngine`.

The public SDK methods include:

- `load_score()`
- `update_with_notes()`
- `update_from_input()`
- `get_current_measure()`
- `get_current_note_index()`
- `get_confidence()`
- `should_turn_page()`
- `get_tracking_status()`
- `reset()`

The important design boundary is that pitch detection and score following are separate. Pitch detection asks, "What note did the microphone hear?" Score following asks, "Where does that note stream fit in the score?"

## 4. Current Limitations

The prototype is still intentionally narrow.

Current limitations:

- Works best with one clear note at a time.
- Does not support chords yet.
- Does not support polyphonic piano transcription.
- Uses simple pitch estimation, not advanced machine learning.
- Can still produce occasional wrong notes from microphone noise or piano overtones.
- The tracker has only been validated on a very simple melody.
- Page turning is simulated from measure/page thresholds.
- Confidence is useful but still prototype-level.
- The visual demo is only an integration demo, not a real product app.

## 5. What Is Still Experimental

The live microphone path is experimental.

Experimental pieces include:

- Microphone capture.
- Autocorrelation pitch estimation.
- Octave stabilization.
- Startup warmup filtering.
- Transition-glitch filtering.
- Same-note repeat suppression.
- Real-time terminal output.
- CSV logging for test runs.

The stable core remains the SDK architecture and simulated note-following path.

## 6. Next Technical Milestones

The next safest milestones are:

1. Test more short melodies against matching MusicXML scores.
2. Add a few simple validation scores beyond C major.
3. Improve robustness to one or two wrong live notes.
4. Improve confidence scoring for live microphone input.
5. Add more realistic rhythm and duration handling from MusicXML.
6. Test repeated notes intentionally played after silence.
7. Test simple page-turn thresholds on a longer live melody.
8. Keep logging real piano failures so fixes are driven by evidence.

Do not jump to chords, full piano transcription, or a consumer app yet. The next step is making monophonic live following reliable.

## 7. Why This Matters For An SDK / Investor Demo

This milestone proves the core business idea in a small but meaningful way.

Strobato can behave like invisible infrastructure inside a host sheet music app. The host app can keep its own interface, score viewer, accounts, library, and user experience. Strobato supplies the live-following intelligence underneath.

For an SDK demo, this is valuable because it shows:

- A third-party app could load a score.
- The musician can play live piano.
- Strobato can infer the current measure.
- The host app could highlight the measure or turn pages automatically.
- The same SDK works with simulated notes and experimental microphone notes.

This is not yet a finished product, but it is a working proof that the live-following loop is possible.

## 8. Commands To Reproduce The Successful Test

Install optional microphone dependencies:

```bash
python3 -m pip install sounddevice numpy
```

Run the C major scale live test:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --score examples/c_major_scale_test.musicxml --candidate-frames 2 --startup-frames 3 --repeat-gap-seconds 0.35
```

Play this melody clearly, one note at a time:

```text
C4, D4, E4, F4, G4
```

Optional CSV logging:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --score examples/c_major_scale_test.musicxml --candidate-frames 2 --startup-frames 3 --repeat-gap-seconds 0.35 --log runs/c_major_live_test.csv
```

Run the simulated version of the same validation through tests:

```bash
.venv/bin/python -m pytest -q
```

## 9. Next Test: Longer C Major Validation

Prototype Milestone 2 should test a slightly longer one-note-at-a-time melody:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

The matching MusicXML score is:

```text
examples/c_major_longer_test.musicxml
```

Run the longer live microphone test with:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --score examples/c_major_longer_test.musicxml --candidate-frames 2 --startup-frames 3 --repeat-gap-seconds 0.35
```

This test checks whether the same live microphone pipeline can stay locked across eight simple measures instead of five.
