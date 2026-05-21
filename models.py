"""Small data objects shared by the parser, matcher, and engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NoteEvent:
    pitch: str
    measure_number: int
    duration: float | None = None


@dataclass(frozen=True)
class Measure:
    number: int
    notes: tuple[NoteEvent, ...]


@dataclass(frozen=True)
class Score:
    measures: tuple[Measure, ...]

    @property
    def notes(self) -> tuple[NoteEvent, ...]:
        return tuple(note for measure in self.measures for note in measure.notes)


@dataclass(frozen=True)
class SyncResult:
    current_measure: int | None
    current_note_index: int | None
    confidence_score: float
    page_turn_signal: bool
    tracking_status: str
