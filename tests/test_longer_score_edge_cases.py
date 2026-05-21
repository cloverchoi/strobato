from pathlib import Path

from strobato_sdk import StrobatoEngine, build_score_reference_map, parse_musicxml


LONG_SCORE = Path("examples/longer_sample_score.musicxml")


def test_longer_score_has_repeated_patterns_and_simulated_pages():
    score = parse_musicxml(LONG_SCORE)
    reference_map = build_score_reference_map(score, measures_per_page=3)

    assert len(reference_map.measures) == 10
    assert reference_map.measures[0].note_names == ("C", "D", "E", "F")
    assert reference_map.measures[3].note_names == ("C", "D", "E", "F")
    assert reference_map.measures[6].note_names == ("C", "D", "E", "F")
    assert reference_map.measures[0].page_number == 1
    assert reference_map.measures[3].page_number == 2
    assert reference_map.measures[6].page_number == 3


def test_repeated_passage_prefers_nearby_forward_position():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C"])
    engine.update_with_notes(["E", "F", "G", "A"])
    repeated_phrase = engine.update_with_notes(["C", "D", "E", "F"])

    assert repeated_phrase.current_measure == 4
    assert repeated_phrase.current_note_index == 15
    assert repeated_phrase.page_turn_signal is True


def test_tempo_variation_with_uneven_note_window_lengths_still_tracks_forward():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    short_window = engine.update_with_notes(["C", "D", "E"])
    longer_window = engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C"])
    uneven_window = engine.update_with_notes(["F", "G", "A", "C", "D", "E", "F"])

    assert short_window.current_measure == 1
    assert longer_window.current_measure == 2
    assert uneven_window.current_measure == 4
    assert uneven_window.current_note_index == 15


def test_burst_of_wrong_notes_does_not_drag_tracker_far_away():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    locked = engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C"])
    noisy = engine.update_with_notes(["X", "Y", "Z", "Q", "R", "T"])

    assert locked.current_measure == 2
    assert noisy.tracking_status == "lost"
    assert noisy.current_measure == locked.current_measure
    assert noisy.current_note_index == locked.current_note_index


def test_skipped_notes_still_keep_plausible_position():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C"])
    result = engine.update_with_notes(["E", "G", "A"])

    assert result.current_measure == 3
    assert result.current_note_index == 11
    assert result.tracking_status in {"locked", "uncertain"}


def test_microphone_duplicate_notes_do_not_force_false_progress():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    result = engine.update_with_notes(["C4", "C4", "D4", "E4", "F4"])

    assert result.current_measure == 1
    assert result.current_note_index == 3
    assert result.page_turn_signal is False


def test_page_turn_signal_when_crossing_simulated_page_boundary():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    page_1 = engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C", "E", "F", "G", "A"])
    page_2 = engine.update_with_notes(["C", "D", "E", "F"])

    assert page_1.current_measure == 3
    assert page_1.page_turn_signal is False
    assert page_2.current_measure == 4
    assert page_2.page_turn_signal is True


def test_brief_noisy_match_on_later_page_does_not_false_page_turn():
    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)

    locked_page_1 = engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C", "E", "F", "G", "A"])
    noisy_later_phrase = engine.update_with_notes(["C", "D", "E", "F"])

    assert locked_page_1.current_measure == 3
    assert noisy_later_phrase.current_measure == 4
    assert noisy_later_phrase.page_turn_signal is True

    engine = StrobatoEngine(score=LONG_SCORE, measures_per_page=3)
    engine.update_with_notes(["C", "D", "E", "F", "G", "A", "B", "C"])
    engine.update_with_notes(["E", "F", "G", "A"])
    stable_before_noise = engine.update_with_notes(["C", "D", "E", "F"])
    brief_noisy_jump = engine.update_with_notes(["G", "A", "B", "C"])

    assert stable_before_noise.current_measure == 4
    assert stable_before_noise.page_turn_signal is True
    assert brief_noisy_jump.current_measure in {4, 5}
    assert brief_noisy_jump.page_turn_signal is False
