"""Public SDK engine for following a score from simulated notes."""

from __future__ import annotations

from pathlib import Path

from strobato_sdk.audio import NoteInput
from strobato_sdk.models import Score, SyncResult
from strobato_sdk.musicxml import parse_musicxml
from strobato_sdk.score_map import ScoreReferenceMap, build_score_reference_map
from strobato_sdk.tracker import SEARCHING, ScoreTracker


class StrobatoEngine:
    """Small SDK object that a sheet music app can integrate.

    The first MVP accepts MusicXML and simulated note names. A host app calls
    `update_with_notes()` whenever it has a recent window of played notes, then
    reads the current measure, confidence, and page-turn signal.
    """

    def __init__(
        self,
        score: str | Path | Score | None = None,
        measures_per_page: int = 4,
    ):
        if measures_per_page < 1:
            raise ValueError("measures_per_page must be at least 1")

        self.measures_per_page = measures_per_page
        self.score: Score | None = None
        self.reference_map: ScoreReferenceMap | None = None
        self.tracker: ScoreTracker | None = None
        self._current_measure: int | None = None
        self._current_note_index: int | None = None
        self._confidence_score = 0.0
        self._page_turn_signal = False
        self._tracking_status = SEARCHING
        self._last_page_index = 0

        if score is not None:
            self.load_score(score)

    def load_score(self, score: str | Path | Score) -> None:
        """Load the MusicXML score that the SDK should follow.

        A third-party sheet music app should call this when the user opens a
        piece. For the first MVP, the score can be a MusicXML file path or an
        already-parsed Score object.
        """
        self.score = parse_musicxml(score) if isinstance(score, (str, Path)) else score
        self.reference_map = build_score_reference_map(
            self.score,
            measures_per_page=self.measures_per_page,
        )
        self.tracker = ScoreTracker(self.reference_map)
        self.reset()

    def update_with_notes(self, live_notes: list[str]) -> SyncResult:
        """Send the SDK a recent window of played notes.

        The notes are simulated strings such as ["E", "D#", "E"]. The SDK uses
        that window to estimate the current measure, confidence, and whether the
        host app should turn the page.
        """
        if self.tracker is None:
            raise ValueError("No score loaded. Call load_score() first.")

        previous_page_index = self._last_page_index
        match = self.tracker.update(live_notes)

        if match.current_note is None:
            self._current_measure = match.current_measure
            self._current_note_index = match.current_note_index
            self._confidence_score = match.confidence_score
            self._page_turn_signal = False
            self._tracking_status = self.tracker.tracking_status
            return SyncResult(
                current_measure=self._current_measure,
                current_note_index=self._current_note_index,
                confidence_score=match.confidence_score,
                page_turn_signal=False,
                tracking_status=self._tracking_status,
            )

        page_index = match.current_note.page_number - 1
        page_turn_signal = page_index > previous_page_index
        self._last_page_index = page_index
        self._current_measure = match.current_measure
        self._current_note_index = match.current_note_index
        self._confidence_score = match.confidence_score
        self._page_turn_signal = page_turn_signal
        self._tracking_status = self.tracker.tracking_status

        return SyncResult(
            current_measure=self._current_measure,
            current_note_index=self._current_note_index,
            confidence_score=self._confidence_score,
            page_turn_signal=self._page_turn_signal,
            tracking_status=self._tracking_status,
        )

    def update_from_input(self, note_input: NoteInput) -> SyncResult:
        """Read one note window from a note input source and update tracking.

        Today, that input source is usually SimulatedNoteInput. Later, the same
        method can accept AudioNoteInput once microphone pitch detection exists.
        """
        return self.update_with_notes(note_input.get_note_window())

    def get_current_measure(self) -> int | None:
        """Return the latest measure estimate.

        Sheet music apps can use this to highlight the measure the performer is
        most likely playing right now.
        """
        return self._current_measure

    def get_current_note_index(self) -> int | None:
        """Return the latest note index in the flattened score timeline.

        This lets a host app connect the live-following result back to an exact
        note position, not just a measure number.
        """
        return self._current_note_index

    def get_confidence(self) -> float:
        """Return how confident the SDK is in the latest measure estimate.

        A value near 1.0 means the recent notes strongly match the score. Lower
        values mean the playing was imperfect or the location is ambiguous.
        """
        return self._confidence_score

    def should_turn_page(self) -> bool:
        """Return whether the host sheet music app should turn the page now.

        This is true only when the latest update crosses from an earlier page
        into a later page.
        """
        return self._page_turn_signal

    def get_tracking_status(self) -> str:
        """Return the latest tracking state: searching, locked, uncertain, or lost."""
        return self._tracking_status

    def get_tracking_metrics(self) -> dict[str, int | float | str | None]:
        """Return lightweight debug metrics for demos and prototypes."""
        return {
            "current_measure": self._current_measure,
            "current_note_index": self._current_note_index,
            "confidence_score": self._confidence_score,
            "tracking_status": self._tracking_status,
            "locked_update_count": self.tracker.locked_update_count
            if self.tracker is not None
            else 0,
        }

    def reset(self) -> None:
        """Clear the current playback position while keeping the loaded score.

        A host app can call this when the musician restarts the piece, jumps to
        another place, or closes and reopens playback controls.
        """
        self._current_measure = None
        self._current_note_index = None
        self._confidence_score = 0.0
        self._page_turn_signal = False
        self._tracking_status = SEARCHING
        self._last_page_index = 0
        if self.tracker is not None:
            self.tracker.reset()

    def update(self, live_notes: list[str]) -> SyncResult:
        """Compatibility alias for update_with_notes()."""
        return self.update_with_notes(live_notes)
