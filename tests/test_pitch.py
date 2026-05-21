from strobato_sdk import (
    frequency_to_midi,
    frequency_to_note_name,
    normalize_note_name,
    note_name_to_midi,
)


def test_440_hz_maps_to_a4():
    assert frequency_to_note_name(440.0) == "A4"
    assert frequency_to_midi(440.0) == 69


def test_middle_c_frequency_maps_to_c4():
    assert frequency_to_note_name(261.63) == "C4"


def test_invalid_or_empty_frequencies_return_none():
    assert frequency_to_note_name(None) is None
    assert frequency_to_note_name(0) is None
    assert frequency_to_note_name(-10) is None


def test_note_names_convert_to_midi_when_octave_is_present():
    assert note_name_to_midi("A4") == 69
    assert note_name_to_midi("C4") == 60
    assert note_name_to_midi("") is None


def test_octave_normalization_can_ignore_octaves():
    assert normalize_note_name("E") == "E"
    assert normalize_note_name("E4") == "E"
    assert normalize_note_name("E5") == "E"
    assert normalize_note_name("Eb4") == "D#"
    assert normalize_note_name("E4", ignore_octave=False) == "E4"
