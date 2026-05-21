from pathlib import Path

from strobato_sdk import AudioNoteInput, SimulatedNoteInput, StrobatoEngine


def test_simulated_note_input_feeds_the_score_follower():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )
    note_input = SimulatedNoteInput(
        [
            ["E4", "D#4", "E4"],
            ["E4", "D#4", "E4", "D#4", "E4", "B3"],
        ]
    )

    first_result = engine.update_from_input(note_input)
    second_result = engine.update_from_input(note_input)

    assert first_result.current_measure == 1
    assert second_result.current_measure == 2
    assert second_result.tracking_status == "locked"


def test_audio_note_input_placeholder_has_the_same_interface():
    note_input = AudioNoteInput()

    assert note_input.get_note_window() == []


def test_audio_note_input_can_convert_fake_frequencies_to_notes():
    note_input = AudioNoteInput(window_size=3)

    note_input.add_detected_frequencies([440.0, 261.63])

    assert note_input.get_note_window() == ["A4", "C4"]
