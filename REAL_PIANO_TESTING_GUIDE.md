# Real Piano Testing Guide

This guide is for the first experimental Strobato live piano test.

The goal is not perfection yet. The goal is to learn what the microphone hears,
what notes Strobato detects, and whether the score follower can stay near the
right measure.

## 1. Install Microphone Dependencies

From the repository root:

```bash
python3 -m pip install sounddevice numpy
```

If macOS asks for microphone permission, allow it for your terminal app.

## 2. Run The Live Score-Following Demo

Start with logging turned on:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --log runs/test1.csv
```

To test the same workflow without a microphone, use demo mode:

```bash
PYTHONPATH=src python3 examples/live_score_following_demo.py --demo --log runs/demo_test.csv
```

## 3. Recommended Piano Setup

- Use a real piano, keyboard, or piano app with speaker output.
- Keep the room quiet.
- Put the microphone close to the instrument, but not so close that the sound distorts.
- Play one note at a time.
- Avoid pedal for the first test.
- Avoid chords for now.

This prototype is monophonic. It is trying to hear one clear note at a time.

## 4. What To Play First

The current live demo loads `examples/simple_score.musicxml`.

Play this simple sequence slowly:

```text
E4, D#4, E4, D#4, E4, B3, D4, C4, A3
```

Pause briefly between notes. A good first speed is about one note every half
second.

## 5. What Good Output Looks Like

Good output does not need to be perfect. Look for:

- detected note windows that roughly match what you played
- `tracking_status` moving from `searching` or `uncertain` into `locked`
- `current_measure` moving forward
- `confidence_score` rising as the phrase becomes clearer
- `page_turn_signal` becoming `True` when the demo crosses into the next page

Example shape:

```text
Detected note window: E4, D#4, E4, D#4, E4, B3
Score position
  current_measure: 2
  confidence_score: 0.65
  tracking_status: locked
  page_turn_signal: False
```

## 6. What Bad Output Looks Like

Write down what happened if you see:

- no detected notes even when playing clearly
- many repeated duplicate notes, like `E4, E4, E4, E4`
- wrong octaves, like `E5` when you played `E4`
- unrelated notes, like `A#4` when you played `E4`
- `tracking_status` stays `lost`
- `current_measure` jumps far forward or backward
- `page_turn_signal` fires too early

## 7. How To Stop The Demo

Press:

```text
Ctrl+C
```

The CSV log should already be saved under `runs/`.

## 8. What To Write Down When Something Fails

For each issue, write:

- what command you ran
- what instrument/source you used
- where the microphone was placed
- what notes you played
- what Strobato printed
- whether the CSV log was saved
- the path to the CSV file, such as `runs/test1.csv`
- whether the room was noisy
- whether you used pedal or played notes close together

The CSV file is especially useful because it shows detected note windows,
measure estimates, confidence, tracking status, and page-turn signals over time.

## 9. Reminder

This is still experimental. It uses simple FFT-based pitch estimation and does
not detect chords yet. The first real piano test is mainly about collecting
failure cases so the next algorithm change can be grounded in real evidence.
