"""Small pitch helpers for converting frequencies into note names.

Pitch detection is the step that listens to sound and estimates a frequency.
A frequency is measured in Hertz, or cycles per second. For example, the note
A4 is standardized at 440 Hz, which means the sound wave vibrates 440 times per
second.

Once we have a frequency, this module converts it into the nearest piano note
name. Score following happens after that: the tracker compares note names to the
MusicXML score and decides where the performer is.
"""

from __future__ import annotations

import math

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
A4_FREQUENCY = 440.0
A4_MIDI_NUMBER = 69


def frequency_to_midi(frequency_hz: float | int | None) -> int | None:
    """Convert a frequency in Hz to the nearest MIDI note number.

    MIDI note 69 is A4. Because A4 is defined as 440 Hz, we can measure how many
    half-steps a frequency is above or below 440 and round to the nearest note.
    """
    if frequency_hz is None or frequency_hz <= 0:
        return None

    half_steps_from_a4 = 12 * math.log2(float(frequency_hz) / A4_FREQUENCY)
    return round(A4_MIDI_NUMBER + half_steps_from_a4)


def midi_to_note_name(midi_number: int | None) -> str | None:
    """Convert a MIDI note number to a piano-style note name such as C4."""
    if midi_number is None:
        return None

    note_name = NOTE_NAMES[midi_number % 12]
    octave = (midi_number // 12) - 1
    return f"{note_name}{octave}"


def frequency_to_note_name(frequency_hz: float | int | None) -> str | None:
    """Convert a frequency in Hz to the nearest piano note name."""
    return midi_to_note_name(frequency_to_midi(frequency_hz))


def note_name_to_midi(note_name: str | None) -> int | None:
    """Convert a note name such as A4 or C#5 to a MIDI note number."""
    if note_name is None:
        return None

    normalized = note_name.strip().replace("♯", "#").replace("♭", "b")
    if not normalized:
        return None

    pitch_class = normalized[0].upper()
    rest = normalized[1:]
    if rest.startswith(("#", "b")):
        pitch_class += rest[0]
        rest = rest[1:]

    if not rest or not rest.lstrip("-").isdigit():
        return None

    pitch_class = _flat_to_sharp(pitch_class)
    if pitch_class not in NOTE_NAMES:
        return None

    octave = int(rest)
    return NOTE_NAMES.index(pitch_class) + ((octave + 1) * 12)


def normalize_note_name(note_name: str | None, ignore_octave: bool = True) -> str:
    """Normalize note names for comparison.

    When ignore_octave is true, E, E4, and E5 all become E. That is useful for
    the current MVP because the sample score stores pitch classes only. Later,
    octave-aware matching can set ignore_octave to false.
    """
    if note_name is None:
        return ""

    normalized = note_name.strip().replace("♯", "#").replace("♭", "b")
    if not normalized:
        return ""

    pitch_class = normalized[0].upper()
    rest = normalized[1:]
    if rest.startswith(("#", "b")):
        pitch_class += rest[0]
        rest = rest[1:]

    pitch_class = _flat_to_sharp(pitch_class)
    if ignore_octave:
        return pitch_class

    return f"{pitch_class}{rest}"


def _flat_to_sharp(note_name: str) -> str:
    flats = {
        "Db": "C#",
        "Eb": "D#",
        "Gb": "F#",
        "Ab": "G#",
        "Bb": "A#",
    }
    return flats.get(note_name, note_name)
