# Strobato Examples

These examples are local developer demos. They are here to show how the SDK can
be used by a host sheet music app, not to turn Strobato into a standalone app.

Run commands from the repository root.

## Recommended First Examples

```bash
PYTHONPATH=src .venv/bin/python examples/sdk_host_app_example.py
```

Shows how a third-party sheet music app would load a score, send note windows
to `StrobatoEngine`, and decide whether to highlight a measure or turn a page.

```bash
PYTHONPATH=src .venv/bin/python examples/visual_demo.py --score examples/c_major_longer_test.musicxml
```

Starts the browser-based host-app demo in replay mode.

## Simulated Score Following

- `sdk_host_app_example.py`: clean SDK integration example for host apps
- `integration_demo.py`: older SDK state demo with imperfect note windows
- `simulated_following.py`: small terminal walkthrough of simulated following

## Visual Demo

- `visual_demo.py`: local browser demo framed as a host sheet music app

Useful live demo command:

```bash
PYTHONPATH=src .venv/bin/python examples/visual_demo.py --score examples/c_major_longer_test.musicxml --live --latency-mode balanced --port 8779
```

## Pitch And Microphone Experiments

These are experimental and optional. They require `sounddevice` and `numpy` for
real microphone input.

- `pitch_detection_demo.py`: converts fake frequencies into note names
- `pitch_calibration_demo.py`: asks you to play known notes and records results
- `live_microphone_demo.py`: prints live detected note events
- `live_score_following_demo.py`: connects microphone notes to `StrobatoEngine`

Demo mode does not require a microphone:

```bash
PYTHONPATH=src .venv/bin/python examples/live_score_following_demo.py --demo
```

## MusicXML Scores

- `simple_score.musicxml`: short first test score
- `longer_sample_score.musicxml`: longer repeated-pattern score for tracker tests
- `c_major_scale_test.musicxml`: five-note C major validation score
- `c_major_longer_test.musicxml`: eight-note C major validation score
