"""Terminal demo of the SDK's stateful score-following result.

For the clearest third-party integration example, start with
`sdk_host_app_example.py`. This file is kept as a compact tracker behavior demo
with imperfect note windows.
"""

from pathlib import Path

from strobato_sdk import StrobatoEngine


def main() -> None:
    score_path = Path(__file__).with_name("simple_score.musicxml")

    # A sheet music platform would create the SDK engine when opening a score view.
    engine = StrobatoEngine(measures_per_page=2)
    engine.load_score(score_path)

    # Each item represents the latest note window detected by the host platform.
    note_windows = [
        ("Searching from the opening phrase", ["E", "D#", "E"]),
        ("Locked as measure 2 arrives", ["E", "D#", "E", "D#", "E", "B"]),
        ("Still locked with one wrong note", ["E", "D#", "E", "F", "E", "B"]),
        ("Lost after unrelated notes", ["X", "Y", "Z", "Q", "R"]),
        ("Recovered near measure 3 and page turns", ["D", "C", "A"]),
        (
            "Stays on the same page after recovery",
            ["E", "D#", "E", "D#", "E", "B", "D", "C", "A"],
        ),
    ]

    print("Strobato SDK integration demo")
    print("-----------------------------")

    for index, (label, note_window) in enumerate(note_windows, start=1):
        result = engine.update_with_notes(note_window)

        print(f"Update {index}: {label}")
        print(f"  input_notes: {note_window}")
        print(f"  current_measure: {result.current_measure}")
        print(f"  current_note_index: {result.current_note_index}")
        print(f"  confidence_score: {result.confidence_score}")
        print(f"  page_turn_signal: {result.page_turn_signal}")
        print(f"  tracking_status: {result.tracking_status}")
        print()

    print("Latest SDK state")
    print(f"  get_current_measure(): {engine.get_current_measure()}")
    print(f"  get_confidence(): {engine.get_confidence()}")
    print(f"  should_turn_page(): {engine.should_turn_page()}")
    print(f"  get_tracking_status(): {engine.get_tracking_status()}")


if __name__ == "__main__":
    main()
