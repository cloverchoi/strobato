"""Small terminal walkthrough of simulated score following."""

from pathlib import Path

from strobato_sdk import StrobatoEngine


def main() -> None:
    score_path = Path(__file__).with_name("simple_score.musicxml")
    engine = StrobatoEngine(score=score_path, measures_per_page=2)

    steps = [
        ("Measure 1 starts clearly", ["E", "D#", "E"]),
        ("The player reaches measure 2", ["E", "D#", "E", "D#", "E", "B"]),
        ("One note is missed, but the SDK still follows", ["E", "D#", "E", "E", "B"]),
        (
            "One extra note is played, but the SDK stays close",
            ["E", "D#", "E", "G", "D#", "E", "B"],
        ),
        (
            "The player enters measure 3, so the page can turn",
            ["E", "D#", "E", "D#", "E", "B", "D", "C", "A"],
        ),
    ]

    print("Strobato simulated score-following demo")
    print("---------------------------------------")

    for label, live_notes in steps:
        result = engine.update_with_notes(live_notes=live_notes)
        page_turn = "yes" if result.page_turn_signal else "no"
        print(label)
        print(f"  played notes: {', '.join(live_notes)}")
        print(f"  current measure: {result.current_measure}")
        print(f"  confidence: {result.confidence_score}")
        print(f"  page turn: {page_turn}")
        print(f"  tracking status: {result.tracking_status}")
        print()


if __name__ == "__main__":
    main()
