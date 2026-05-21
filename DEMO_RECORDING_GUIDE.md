# Strobato Demo Recording Guide

This guide is for recording the current visual live demo for investors, advisors, or early product conversations.

The goal is to show Strobato as invisible SDK infrastructure inside a host sheet music app.

## 1. Start The Visual Live Demo

From the repository root, run:

```bash
PYTHONPATH=src python3 examples/visual_demo.py --score examples/c_major_longer_test.musicxml --live
```

This starts the local visual demo using the longer C major test score.

## 2. Open The Browser URL

Open:

```text
http://127.0.0.1:8765
```

The page should show a generic app called:

```text
Host Sheet Music App
```

It should also show:

```text
Powered by Strobato SDK
```

## 3. Notes To Play

Play one clear note at a time:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

Use a steady pace. Do not play chords yet.

## 4. What The Viewer Should See

The viewer should see:

- Eight measure boxes on screen.
- The current measure highlight moving forward.
- The compressed note window growing:

```text
C4, D4, E4, F4, G4, A4, B4, C5
```

- `tracking_status` staying mostly `locked`.
- `confidence_score` rising toward about `0.83`.
- The current measure reaching `8`.

This demonstrates live piano input driving a visual sheet music interface.

## 5. Plain-English Explanation

Use this explanation:

```text
Strobato is not trying to be another sheet music app. It is an SDK that a sheet music app could embed. The musician plays piano, Strobato listens, turns the audio into note events, compares those notes to the MusicXML score, and tells the host app which measure the musician is currently playing.
```

Even simpler:

```text
The app is showing the sheet music. Strobato is the invisible layer underneath that figures out where the performer is in the score.
```

## 6. If The Port Is Already In Use

If `8765` is already busy, run the demo on another port:

```bash
PYTHONPATH=src python3 examples/visual_demo.py --score examples/c_major_longer_test.musicxml --live --port 8766
```

Then open:

```text
http://127.0.0.1:8766
```

## 7. What To Record

Use your normal screen recording tool.

Record:

- The browser window showing `Host Sheet Music App`.
- The measure highlight moving as you play.
- The developer panel showing:
  - current measure
  - confidence score
  - tracking status
  - compressed note window
- Your hands or keyboard only if easy; the screen is the most important part.

Avoid recording setup steps unless the audience needs technical detail.

## 8. 30-Second Demo Narration Script

```text
This is Strobato running as an SDK inside a fake host sheet music app. I am going to play a simple live piano melody. As I play, Strobato listens through the microphone, turns the audio into note events, matches those notes against the MusicXML score, and updates the current measure on screen. The important part is that the sheet music app stays the user-facing product, while Strobato powers the live-following intelligence underneath.
```

## 9. 60-Second Investor Narration Script

```text
Strobato is infrastructure for digital sheet music platforms. Instead of building another consumer sheet music app, we are building the live-following layer that existing platforms could integrate.

In this demo, the browser is a fake host sheet music app. The score is loaded from MusicXML. I play live piano into the microphone, and Strobato converts the audio into a clean note stream. The SDK then compares that stream to the score and returns the current measure, confidence, tracking status, and page-turn signal.

As I play C4 through C5, you can see the highlighted measure advance in real time. This proves the core loop: live performance in, score position out. The next step is improving reliability across more melodies, noisier rooms, and eventually more complex music.
```

## 10. Current Limitations To Disclose Honestly

Say this plainly if asked:

- This is a prototype.
- It currently works best with one clear note at a time.
- It does not detect chords yet.
- It does not do full polyphonic piano transcription.
- Pitch detection can still be affected by room noise, microphone placement, and piano overtones.
- The current visual demo is local and developer-facing.
- Page turning is present as an SDK signal, but the visual page-turn demo still needs polish.
- The next technical goal is testing simple melodies beyond scales and improving demo smoothness.

This honesty helps the demo land correctly: the milestone is not "finished product," it is "working live-following SDK proof."
