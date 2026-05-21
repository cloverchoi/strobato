from pathlib import Path

from strobato_sdk import build_score_reference_map, parse_musicxml


def test_score_reference_map_flattens_musicxml_notes():
    score = parse_musicxml(Path("examples/simple_score.musicxml"))
    reference_map = build_score_reference_map(score, measures_per_page=2)

    assert reference_map.pitches == ("E", "D#", "E", "D#", "E", "B", "D", "C", "A")
    assert reference_map.notes[0].note_index == 0
    assert reference_map.notes[0].measure_number == 1
    assert reference_map.notes[0].duration == 1.0
    assert reference_map.notes[5].note_index == 5
    assert reference_map.notes[5].measure_number == 2
    assert reference_map.notes[6].page_number == 2


def test_score_reference_map_links_measures_to_note_indexes():
    score = parse_musicxml(Path("examples/simple_score.musicxml"))
    reference_map = build_score_reference_map(score, measures_per_page=2)

    measure_2 = reference_map.measures[1]
    measure_3 = reference_map.measures[2]

    assert measure_2.measure_number == 2
    assert measure_2.start_note_index == 3
    assert measure_2.end_note_index == 5
    assert measure_2.note_names == ("D#", "E", "B")
    assert measure_3.page_number == 2
