"""Simulated note matching against the full score reference map."""

from __future__ import annotations

from dataclasses import dataclass

from strobato_sdk.pitch import normalize_note_name
from strobato_sdk.score_map import ExpectedNote, ScoreReferenceMap

MIN_WINDOW_SIZE = 5
MAX_WINDOW_SIZE = 20


@dataclass(frozen=True)
class _MatchCandidate:
    current_note: ExpectedNote
    similarity: float
    start_index: int
    end_index: int


@dataclass(frozen=True)
class MatchResult:
    current_note: ExpectedNote | None
    current_measure: int | None
    current_note_index: int | None
    confidence_score: float


def infer_current_position(
    reference_map: ScoreReferenceMap,
    live_notes: list[str],
    preferred_note_index: int | None = None,
) -> MatchResult:
    score_notes = reference_map.notes
    normalized_live_notes = [_normalize_pitch(note) for note in live_notes if note.strip()]

    if not score_notes or not normalized_live_notes:
        return MatchResult(
            current_note=None,
            current_measure=None,
            current_note_index=None,
            confidence_score=0.0,
        )

    window_size = min(MAX_WINDOW_SIZE, len(score_notes), len(normalized_live_notes))
    recent_live_notes = normalized_live_notes[-window_size:]

    candidates = _find_candidates(
        score_notes,
        recent_live_notes,
        preferred_note_index=preferred_note_index,
    )
    if not candidates:
        return MatchResult(
            current_note=None,
            current_measure=None,
            current_note_index=None,
            confidence_score=0.0,
        )

    best_candidate = candidates[0]
    second_best = next(
        (
            candidate
            for candidate in candidates[1:]
            if candidate.end_index != best_candidate.end_index
        ),
        None,
    )

    confidence = _confidence_for(best_candidate, second_best, window_size)
    current_note = best_candidate.current_note
    return MatchResult(
        current_note=current_note,
        current_measure=current_note.measure_number,
        current_note_index=current_note.note_index,
        confidence_score=confidence,
    )


def _find_candidates(
    score_notes: tuple[ExpectedNote, ...],
    live_notes: list[str],
    preferred_note_index: int | None = None,
) -> list[_MatchCandidate]:
    candidates: list[_MatchCandidate] = []
    live_count = len(live_notes)
    shortest_score_window = max(1, live_count - 2)
    longest_score_window = min(MAX_WINDOW_SIZE, live_count + 2, len(score_notes))

    for end_index in range(len(score_notes)):
        for score_window_size in range(shortest_score_window, longest_score_window + 1):
            start_index = end_index - score_window_size + 1
            if start_index < 0:
                continue

            score_window = score_notes[start_index : end_index + 1]
            score_pitches = [note.pitch for note in score_window]
            distance = _edit_distance(live_notes, score_pitches)
            similarity = 1 - (distance / max(len(live_notes), len(score_pitches)))
            candidates.append(
                _MatchCandidate(
                    current_note=score_notes[end_index],
                    similarity=similarity,
                    start_index=start_index,
                    end_index=end_index,
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (
            _ranking_score(candidate, preferred_note_index),
            -candidate.end_index,
            -abs((candidate.end_index - candidate.start_index + 1) - live_count),
        ),
        reverse=True,
    )


def _ranking_score(
    candidate: _MatchCandidate,
    preferred_note_index: int | None,
) -> float:
    if preferred_note_index is None:
        return candidate.similarity

    movement = candidate.end_index - preferred_note_index
    if movement >= 0:
        forward_bonus = max(0.0, 0.08 - (movement * 0.01))
        return candidate.similarity + forward_bonus

    small_correction_bonus = max(0.0, 0.04 - (abs(movement) * 0.01))
    backward_penalty = 0.12 if movement < -2 else 0.0
    return candidate.similarity + small_correction_bonus - backward_penalty


def _edit_distance(left: list[str], right: list[str]) -> int:
    previous_row = list(range(len(right) + 1))

    for left_index, left_note in enumerate(left, start=1):
        current_row = [left_index]
        for right_index, right_note in enumerate(right, start=1):
            insertion = current_row[right_index - 1] + 1
            deletion = previous_row[right_index] + 1
            substitution = previous_row[right_index - 1] + (left_note != right_note)
            current_row.append(min(insertion, deletion, substitution))
        previous_row = current_row

    return previous_row[-1]


def _confidence_for(
    best_candidate: _MatchCandidate,
    second_best: _MatchCandidate | None,
    live_window_size: int,
) -> float:
    confidence = best_candidate.similarity

    if live_window_size < MIN_WINDOW_SIZE:
        confidence *= 0.8

    if second_best is not None:
        gap = best_candidate.similarity - second_best.similarity
        uniqueness = 0.65 + min(max(gap, 0.0) / 0.25, 1.0) * 0.35
        confidence *= uniqueness

    return round(max(0.0, min(confidence, 1.0)), 2)


def _normalize_pitch(note: str) -> str:
    return normalize_note_name(note, ignore_octave=True)


def infer_current_note(
    reference_map: ScoreReferenceMap,
    live_notes: list[str],
) -> tuple[ExpectedNote | None, float]:
    """Compatibility helper for older internal callers."""
    result = infer_current_position(reference_map, live_notes)
    return result.current_note, result.confidence_score
