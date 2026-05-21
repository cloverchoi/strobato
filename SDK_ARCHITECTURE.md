# SDK ARCHITECTURE

## Core System

Input:
- MusicXML score
- live microphone audio

Output:
- current_measure
- confidence_score
- page_turn_signal

## Pipeline

1. Parse MusicXML
2. Extract note sequences
3. Listen to live audio
4. Detect notes/pitch
5. Compare recent notes to score
6. Estimate current measure
7. Send synchronization events

## Example SDK Usage

```python
from strobato_sdk import StrobatoEngine

engine = StrobatoEngine(score="fur_elise.musicxml")

result = engine.update(
    live_notes=["E", "D#", "E", "D#", "E", "B"]
)

print(result.current_measure)
print(result.confidence_score)
print(result.page_turn_signal)
```
