"""Example: how a host sheet music app could integrate Strobato.

This is not a standalone Strobato app. Think of it as the code a third-party
sheet music reader might write inside its own score viewer.
"""

from __future__ import annotations

from pathlib import Path

from strobato_sdk import StrobatoEngine
from strobato_sdk.models import SyncResult


SCORE_PATH = Path(__file__).with_name("c_major_longer_test.musicxml")


# Each update is a recent rolling window of notes. In a real host app, these
# notes might come from microphone pitch detection. For this SDK example, they
# are simple simulated note names so the integration is easy to understand.
SIMULATED_NOTE_WINDOWS = [
    ["C4"],
    ["C4", "D4"],
    ["C4", "D4", "E4"],
    ["C4", "D4", "E4", "F4"],
    ["C4", "D4", "E4", "F4", "G4"],
    ["C4", "D4", "E4", "F4", "G4", "A4"],
    ["C4", "D4", "E4", "F4", "G4", "A4", "B4"],
    ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"],
]


def host_app_decision(result: SyncResult) -> dict[str, str | int | bool | None]:
    """Translate Strobato's SDK result into host-app UI decisions.

    Strobato tells the host app where the musician probably is. The host app
    still owns the product experience: highlighting measures, turning pages,
    and deciding how much confidence is enough to update the screen.
    """
    highlight_measure = result.current_measure
    should_highlight = (
        result.current_measure is not None
        and result.tracking_status in {"locked", "uncertain"}
        and result.confidence_score >= 0.45
    )

    return {
        "highlight_measure": highlight_measure if should_highlight else None,
        "turn_page": result.page_turn_signal,
        "screen_state": _screen_state(result.tracking_status),
    }


def _screen_state(tracking_status: str) -> str:
    """Use friendly host-app wording for the SDK tracking state."""
    if tracking_status == "locked":
        return "following"
    if tracking_status == "uncertain":
        return "following carefully"
    if tracking_status == "lost":
        return "listening for recovery"
    return "listening"


def format_host_app_update(
    update_number: int,
    notes: list[str],
    result: SyncResult,
    decision: dict[str, str | int | bool | None],
) -> str:
    """Build one clean console block for a developer reading the example."""
    page_action = "turn page" if decision["turn_page"] else "stay on page"
    highlight = decision["highlight_measure"] or "none yet"

    return "\n".join(
        [
            f"Host update {update_number}",
            f"  simulated_note_window: {notes}",
            f"  current_measure: {result.current_measure}",
            f"  current_note_index: {result.current_note_index}",
            f"  confidence_score: {result.confidence_score:.2f}",
            f"  tracking_status: {result.tracking_status}",
            f"  page_turn_signal: {result.page_turn_signal}",
            f"  host_highlight_measure: {highlight}",
            f"  host_page_action: {page_action}",
            f"  host_screen_state: {decision['screen_state']}",
        ]
    )


def run_host_app_example() -> list[dict[str, object]]:
    """Run the simulated integration and return structured updates.

    Returning the updates makes this example easy to test while keeping the
    printed output beginner-friendly.
    """
    engine = StrobatoEngine(measures_per_page=2)
    engine.load_score(SCORE_PATH)

    updates = []
    for update_number, notes in enumerate(SIMULATED_NOTE_WINDOWS, start=1):
        result = engine.update_with_notes(notes)
        decision = host_app_decision(result)
        updates.append(
            {
                "update_number": update_number,
                "notes": notes,
                "result": result,
                "decision": decision,
                "text": format_host_app_update(update_number, notes, result, decision),
            }
        )

    return updates


def main() -> None:
    print("Host Sheet Music App + Strobato SDK")
    print("-----------------------------------")
    print(f"Loaded MusicXML score: {SCORE_PATH.name}")
    print()

    for update in run_host_app_example():
        print(update["text"])
        print()


if __name__ == "__main__":
    main()
