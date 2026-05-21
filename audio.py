"""Optional note input sources for Strobato.

Pitch detection and score following are two different jobs:

- Pitch detection listens to sound and guesses note names such as "E4".
- Score following takes those note names and decides where they fit in the score.

This module prepares that boundary without adding real microphone input yet.
"""

from __future__ import annotations

from typing import Protocol

from strobato_sdk.pitch import frequency_to_note_name


class NoteInput(Protocol):
    """Shared interface for anything that can provide recent note names."""

    def get_note_window(self) -> list[str]:
        """Return the latest notes for the score follower to process."""
        ...


class SimulatedNoteInput:
    """Simple note source for tests, demos, and SDK integration prototypes.

    This keeps the current MVP behavior: a host app or demo provides note names
    directly, such as ["E4", "D#4", "E4"]. Each call returns the next window.
    """

    def __init__(self, note_windows: list[list[str]] | None = None):
        self.note_windows = note_windows or []
        self._index = 0

    def get_note_window(self) -> list[str]:
        """Return the next simulated note window."""
        if not self.note_windows:
            return []

        note_window = self.note_windows[min(self._index, len(self.note_windows) - 1)]
        self._index += 1
        return note_window

    def reset(self) -> None:
        """Start reading simulated windows from the beginning again."""
        self._index = 0


class AudioNoteInput:
    """Placeholder for future microphone-based note detection.

    A later version can use tools such as librosa, aubio, CREPE, or another pitch
    detector here. That detector would listen to live audio, estimate note names,
    and return the same kind of note window as SimulatedNoteInput.
    """

    def __init__(self, sample_rate: int = 44100, window_size: int = 10):
        self.sample_rate = sample_rate
        self.window_size = window_size
        self._detected_frequencies: list[float] = []

    def add_detected_frequencies(self, frequencies_hz: list[float]) -> None:
        """Store fake detected frequencies for demos and future detector tests.

        This is not microphone input. It simply shows where a future pitch
        detector would hand frequencies to the note-conversion layer.
        """
        self._detected_frequencies.extend(frequencies_hz)

    def get_note_window(self) -> list[str]:
        """Return detected note names from live audio.

        Real microphone pitch detection is intentionally not implemented yet. If
        fake detected frequencies were added, convert them to note names using
        pitch.py. Otherwise, return an empty list.
        """
        if not self._detected_frequencies:
            return []

        notes = [
            note_name
            for note_name in (
                frequency_to_note_name(frequency)
                for frequency in self._detected_frequencies[-self.window_size :]
            )
            if note_name is not None
        ]
        return notes
