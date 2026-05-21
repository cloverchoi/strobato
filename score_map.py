"""Build the internal expected-performance map used by the matcher."""

from __future__ import annotations

from dataclasses import dataclass

from strobato_sdk.models import Score


@dataclass(frozen=True)
class ExpectedNote:
    """One expected note in the flattened score timeline."""

    pitch: str
    measure_number: int
    note_index: int
    measure_note_index: int
    duration: float | None
    page_number: int


@dataclass(frozen=True)
class MeasureReference:
    """Score-map details for one measure."""

    measure_number: int
    page_number: int
    start_note_index: int | None
    end_note_index: int | None
    note_names: tuple[str, ...]
    durations: tuple[float | None, ...]


@dataclass(frozen=True)
class ScoreReferenceMap:
    """Flattened map of what the score is expected to sound like."""

    measures: tuple[MeasureReference, ...]
    notes: tuple[ExpectedNote, ...]

    @property
    def pitches(self) -> tuple[str, ...]:
        return tuple(note.pitch for note in self.notes)


def build_score_reference_map(
    score: Score,
    measures_per_page: int = 4,
) -> ScoreReferenceMap:
    """Convert a parsed score into a flattened expected-performance timeline."""
    if measures_per_page < 1:
        raise ValueError("measures_per_page must be at least 1")

    expected_notes: list[ExpectedNote] = []
    measure_references: list[MeasureReference] = []

    for measure_position, measure in enumerate(score.measures):
        page_number = (measure_position // measures_per_page) + 1
        start_note_index = len(expected_notes) if measure.notes else None

        for note_position, note in enumerate(measure.notes):
            expected_notes.append(
                ExpectedNote(
                    pitch=note.pitch,
                    measure_number=measure.number,
                    note_index=len(expected_notes),
                    measure_note_index=note_position,
                    duration=note.duration,
                    page_number=page_number,
                )
            )

        end_note_index = len(expected_notes) - 1 if measure.notes else None
        measure_references.append(
            MeasureReference(
                measure_number=measure.number,
                page_number=page_number,
                start_note_index=start_note_index,
                end_note_index=end_note_index,
                note_names=tuple(note.pitch for note in measure.notes),
                durations=tuple(note.duration for note in measure.notes),
            )
        )

    return ScoreReferenceMap(
        measures=tuple(measure_references),
        notes=tuple(expected_notes),
    )
