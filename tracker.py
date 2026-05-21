"""Stateful real-time tracking on top of simulated note matching."""

from __future__ import annotations

from dataclasses import dataclass

from strobato_sdk.matcher import MatchResult, infer_current_position
from strobato_sdk.score_map import ScoreReferenceMap

SEARCHING = "searching"
LOCKED = "locked"
UNCERTAIN = "uncertain"
LOST = "lost"


@dataclass
class ScoreTracker:
    """Maintains score-following state as note windows arrive over time."""

    reference_map: ScoreReferenceMap
    current_measure: int | None = None
    current_note_index: int | None = None
    confidence_score: float = 0.0
    tracking_status: str = SEARCHING
    locked_update_count: int = 0

    def update(self, live_notes: list[str]) -> MatchResult:
        match = infer_current_position(
            self.reference_map,
            live_notes,
            preferred_note_index=self.current_note_index,
        )

        if match.current_note is None or match.confidence_score < 0.2:
            self.confidence_score = round(self.confidence_score * 0.25, 2)
            self.tracking_status = LOST
            return self._current_result()

        if self.current_note_index is None:
            self._accept(match)
            self.tracking_status = self._status_for(match.confidence_score)
            self.locked_update_count = 1 if self.tracking_status == LOCKED else 0
            return self._current_result()

        movement = match.current_note_index - self.current_note_index
        if movement < -2 and match.confidence_score < 0.9:
            self.confidence_score = self._decay_confidence(match.confidence_score * 0.65)
            self.locked_update_count = 0
            self.tracking_status = UNCERTAIN
            return self._current_result()

        plausible_jump_limit = max(5, len(live_notes) + 2)
        big_jump = movement > plausible_jump_limit and self.tracking_status == LOCKED
        if big_jump and match.confidence_score < 0.9:
            self.confidence_score = self._decay_confidence(match.confidence_score * 0.75)
            self.locked_update_count = 0
            self.tracking_status = UNCERTAIN
            return self._current_result()

        self._accept(match)
        if match.confidence_score >= 0.55:
            self.tracking_status = LOCKED
            self.locked_update_count += 1
        elif match.confidence_score >= 0.3:
            self.tracking_status = UNCERTAIN
            self.locked_update_count = 0
        else:
            self.tracking_status = LOST
            self.locked_update_count = 0

        return self._current_result()

    def reset(self) -> None:
        self.current_measure = None
        self.current_note_index = None
        self.confidence_score = 0.0
        self.tracking_status = SEARCHING
        self.locked_update_count = 0

    def _accept(self, match: MatchResult) -> None:
        self.current_measure = match.current_measure
        self.current_note_index = match.current_note_index
        self.confidence_score = self._smooth_confidence(match.confidence_score)

    def _smooth_confidence(self, new_confidence: float) -> float:
        if self.tracking_status in {SEARCHING, LOST}:
            return round(new_confidence, 2)
        return round((self.confidence_score * 0.6) + (new_confidence * 0.4), 2)

    def _decay_confidence(self, new_confidence: float) -> float:
        return round((self.confidence_score * 0.75) + (new_confidence * 0.25), 2)

    def _status_for(self, confidence: float) -> str:
        if confidence >= 0.55:
            return LOCKED
        if confidence >= 0.3:
            return UNCERTAIN
        return LOST

    def _current_result(self) -> MatchResult:
        current_note = None
        if self.current_note_index is not None:
            current_note = self.reference_map.notes[self.current_note_index]

        return MatchResult(
            current_note=current_note,
            current_measure=self.current_measure,
            current_note_index=self.current_note_index,
            confidence_score=self.confidence_score,
        )
