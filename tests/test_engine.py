from pathlib import Path

from strobato_sdk import StrobatoEngine
from strobato_sdk.models import Measure, NoteEvent, Score


def _score(measures: list[list[str]]) -> Score:
    built_measures = []
    for measure_number, pitches in enumerate(measures, start=1):
        built_measures.append(
            Measure(
                number=measure_number,
                notes=tuple(
                    NoteEvent(pitch=pitch, measure_number=measure_number)
                    for pitch in pitches
                ),
            )
        )
    return Score(measures=tuple(built_measures))


def test_engine_infers_current_measure_from_simulated_notes():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )

    result = engine.update(["E", "D#", "E", "D#", "E", "B"])

    assert result.current_measure == 2
    assert result.current_note_index == 5
    assert result.confidence_score >= 0.85
    assert result.page_turn_signal is False
    assert result.tracking_status == "locked"


def test_public_sdk_methods_expose_latest_state():
    engine = StrobatoEngine(measures_per_page=2)

    engine.load_score(Path("examples/simple_score.musicxml"))
    result = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])

    assert engine.get_current_measure() == result.current_measure
    assert engine.get_current_note_index() == result.current_note_index
    assert engine.get_confidence() == result.confidence_score
    assert engine.should_turn_page() == result.page_turn_signal
    assert engine.get_tracking_status() == result.tracking_status


def test_reset_clears_position_but_keeps_loaded_score():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )

    engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])
    engine.reset()
    result = engine.update_with_notes(["E", "D#", "E"])

    assert engine.get_current_measure() is not None
    assert result.current_measure == engine.get_current_measure()


def test_engine_handles_one_wrong_note():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    exact_result = engine.update(["E", "D#", "E", "D#", "E", "B"])
    imperfect_result = engine.update(["E", "D#", "E", "F", "E", "B"])

    assert imperfect_result.current_measure == 2
    assert imperfect_result.current_note_index == 5
    assert 0.0 < imperfect_result.confidence_score < exact_result.confidence_score
    assert imperfect_result.tracking_status == "locked"


def test_engine_handles_extra_note():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    result = engine.update(["E", "D#", "E", "G", "D#", "E", "B"])

    assert result.current_measure == 2
    assert result.current_note_index == 5
    assert 0.0 < result.confidence_score < 1.0
    assert result.tracking_status in {"locked", "uncertain"}


def test_engine_handles_missing_note():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    result = engine.update(["E", "D#", "E", "E", "B"])

    assert result.current_measure == 2
    assert result.current_note_index == 5
    assert 0.0 < result.confidence_score < 1.0
    assert result.tracking_status in {"locked", "uncertain"}


def test_engine_handles_repeated_notes():
    engine = StrobatoEngine(
        score=_score(
            [
                ["C", "C", "C"],
                ["D", "D", "E"],
                ["F", "G", "A"],
            ]
        )
    )

    result = engine.update(["C", "C", "C", "D", "D", "E"])

    assert result.current_measure == 2
    assert result.confidence_score >= 0.85
    assert result.tracking_status == "locked"


def test_engine_lowers_confidence_for_ambiguous_match():
    engine = StrobatoEngine(
        score=_score(
            [
                ["C", "D", "E"],
                ["F", "G", "A"],
                ["C", "D", "E"],
                ["B", "C", "D"],
            ]
        )
    )

    result = engine.update(["C", "D", "E"])

    assert result.current_measure == 1
    assert 0.0 < result.confidence_score < 0.8
    assert result.tracking_status == "uncertain"


def test_engine_sends_page_turn_signal_once_when_new_page_is_reached():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )

    first_result = engine.update(["E", "D#", "E", "D#", "E", "B", "D"])
    second_result = engine.update(["E", "D#", "E", "D#", "E", "B", "D"])

    assert first_result.current_measure == 3
    assert first_result.current_note_index == 6
    assert first_result.page_turn_signal is True
    assert first_result.tracking_status == "locked"
    assert second_result.current_measure == 3
    assert second_result.page_turn_signal is False


def test_engine_finds_pattern_from_measure_2_in_full_score_map():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    result = engine.update_with_notes(["D#", "E", "B"])

    assert result.current_measure == 2
    assert result.current_note_index == 5


def test_engine_finds_pattern_from_measure_3_in_full_score_map():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    result = engine.update_with_notes(["D", "C", "A"])

    assert result.current_measure == 3
    assert result.current_note_index == 8


def test_engine_locks_onto_c_major_scale_test_score():
    engine = StrobatoEngine(
        score=Path("examples/c_major_scale_test.musicxml"),
        measures_per_page=2,
    )

    result = engine.update_with_notes(["C4", "D4", "E4", "F4", "G4"])

    assert result.current_measure == 5
    assert result.current_note_index == 4
    assert result.confidence_score >= 0.85
    assert result.tracking_status == "locked"


def test_engine_locks_onto_longer_c_major_test_score():
    engine = StrobatoEngine(
        score=Path("examples/c_major_longer_test.musicxml"),
        measures_per_page=4,
    )

    notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    results = []
    for note_count in range(1, len(notes) + 1):
        results.append(engine.update_with_notes(notes[:note_count]))

    assert [result.current_measure for result in results] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert results[-1].current_note_index == 7
    assert results[-1].confidence_score >= 0.8
    assert results[-1].tracking_status == "locked"


def test_tracker_prefers_normal_forward_progression():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )

    first = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])
    second = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B", "D", "C", "A"])

    assert first.current_note_index == 5
    assert second.current_note_index == 8
    assert second.current_measure == 3
    assert second.tracking_status == "locked"


def test_tracker_stays_locked_through_one_wrong_note():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])
    result = engine.update_with_notes(["E", "D#", "E", "F", "E", "B"])

    assert result.current_measure == 2
    assert result.current_note_index == 5
    assert result.tracking_status == "locked"


def test_tracker_marks_ambiguous_input_uncertain():
    engine = StrobatoEngine(
        score=_score(
            [
                ["C", "D", "E"],
                ["F", "G", "A"],
                ["C", "D", "E"],
                ["B", "C", "D"],
            ]
        )
    )

    result = engine.update_with_notes(["C", "D", "E"])

    assert result.tracking_status == "uncertain"


def test_tracker_marks_no_match_lost_but_remembers_last_position():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    locked = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])
    lost = engine.update_with_notes(["X", "Y", "Z", "Q", "R"])

    assert locked.tracking_status == "locked"
    assert lost.tracking_status == "lost"
    assert lost.current_note_index == locked.current_note_index
    assert lost.current_measure == locked.current_measure


def test_tracker_recovers_after_being_lost():
    engine = StrobatoEngine(score=Path("examples/simple_score.musicxml"))

    engine.update_with_notes(["X", "Y", "Z", "Q", "R"])
    recovered = engine.update_with_notes(["D", "C", "A"])

    assert recovered.current_measure == 3
    assert recovered.current_note_index == 8
    assert recovered.tracking_status in {"locked", "uncertain"}


def test_page_turn_only_triggers_when_crossing_page_threshold():
    engine = StrobatoEngine(
        score=Path("examples/simple_score.musicxml"),
        measures_per_page=2,
    )

    measure_2 = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B"])
    measure_3 = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B", "D"])
    still_measure_3 = engine.update_with_notes(["E", "D#", "E", "D#", "E", "B", "D", "C", "A"])

    assert measure_2.page_turn_signal is False
    assert measure_3.page_turn_signal is True
    assert still_measure_3.page_turn_signal is False
