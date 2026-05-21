from pathlib import Path

from strobato_sdk import parse_musicxml


def test_parse_musicxml_extracts_measure_numbers_and_pitch_names():
    score = parse_musicxml(Path("examples/simple_score.musicxml"))

    assert [measure.number for measure in score.measures] == [1, 2, 3]
    assert [note.pitch for note in score.notes[:6]] == ["E", "D#", "E", "D#", "E", "B"]
    assert score.notes[-1].measure_number == 3
