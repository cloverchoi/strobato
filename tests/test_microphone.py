from strobato_sdk.microphone import (
    DemoFrequencyNoteInput,
    LiveMicrophoneNoteInput,
    NoteEventCompressor,
    NoteBuffer,
    PitchEstimate,
    PitchStabilizer,
    estimate_dominant_frequency,
)


class TinyNumpy:
    @staticmethod
    def asarray(values, dtype=float):
        return TinyArray([dtype(value) for value in values])


class TinyArray:
    def __init__(self, values):
        self.values = values
        self.size = len(values)


def test_live_microphone_note_input_starts_empty_without_opening_microphone():
    microphone = LiveMicrophoneNoteInput()

    assert microphone.get_note_window() == []


def test_estimate_dominant_frequency_returns_none_for_empty_frame():
    assert estimate_dominant_frequency([], sample_rate=44100, numpy_module=TinyNumpy) is None


def test_note_buffer_debounces_repeated_notes():
    note_buffer = NoteBuffer(window_size=4, debounce_seconds=0.5)

    assert note_buffer.add_note("E4", detected_at=1.0) is True
    assert note_buffer.add_note("E4", detected_at=1.1) is False
    assert note_buffer.add_note("D#4", detected_at=1.2) is True
    assert note_buffer.get_note_window() == ["E4", "D#4"]
    assert note_buffer.get_metrics()["rejected_detection_count"] == 1


def test_note_buffer_keeps_a_clean_rolling_window():
    note_buffer = NoteBuffer(window_size=3, debounce_seconds=0.0)

    for index, note_name in enumerate(["E4", "D#4", "E4", "B3"]):
        note_buffer.add_note(note_name, detected_at=float(index))

    assert note_buffer.get_note_window() == ["D#4", "E4", "B3"]
    assert note_buffer.get_metrics()["accepted_note_count"] == 4


def test_note_event_compressor_turns_many_repeated_c4_detections_into_one_event():
    compressor = NoteEventCompressor(repeat_gap_seconds=0.3)

    assert compressor.should_add_event("C4", detected_at=0.0) is True
    assert compressor.should_add_event("C4", detected_at=0.1) is False
    assert compressor.should_add_event("C4", detected_at=0.2) is False
    assert compressor.should_add_event("C4", detected_at=0.3) is False
    assert compressor.compressed_duplicate_count == 3


def test_note_buffer_compresses_many_repeated_c4_detections_into_one_event():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index in range(8):
        note_buffer.add_note("C4", detected_at=index * 0.1)

    assert note_buffer.get_note_window() == ["C4"]
    assert note_buffer.get_raw_note_window() == ["C4"] * 8
    assert note_buffer.get_metrics()["compressed_duplicate_count"] == 7


def test_note_buffer_holding_c4_for_several_seconds_produces_one_event():
    note_buffer = NoteBuffer(
        window_size=20,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index in range(30):
        note_buffer.add_note("C4", detected_at=index * 0.2)

    assert note_buffer.get_note_window() == ["C4"]
    assert note_buffer.get_metrics()["compressed_duplicate_count"] == 29


def test_note_buffer_accepts_repeated_c4_then_d4_as_two_events():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index in range(4):
        note_buffer.add_note("C4", detected_at=index * 0.1)
    for index in range(4, 8):
        note_buffer.add_note("D4", detected_at=index * 0.1)

    assert note_buffer.get_note_window() == ["C4", "D4"]


def test_note_buffer_allows_same_note_again_after_pause():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("C4", detected_at=0.0)
    note_buffer.add_note("C4", detected_at=0.2)
    note_buffer.add_note(None, detected_at=0.8, rejection_reason="below_volume_threshold")
    note_buffer.add_note(None, detected_at=1.2, rejection_reason="below_volume_threshold")
    note_buffer.add_note("C4", detected_at=1.3)

    assert note_buffer.get_note_window() == ["C4", "C4"]


def test_note_buffer_does_not_repeat_same_note_just_because_time_passed():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("C4", detected_at=0.0)
    note_buffer.add_note("C4", detected_at=4.0)

    assert note_buffer.get_note_window() == ["C4"]


def test_note_buffer_requires_continuous_silence_before_same_note_repeat():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("E4", detected_at=0.0)
    note_buffer.add_note(None, detected_at=0.2, rejection_reason="below_volume_threshold")
    note_buffer.add_note("E4", detected_at=0.3)
    note_buffer.add_note("E4", detected_at=0.7)

    assert note_buffer.get_note_window() == ["E4"]


def test_note_buffer_held_e4_with_one_below_volume_frame_stays_one_event():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("E4", detected_at=0.0)
    note_buffer.add_note(None, detected_at=0.4, rejection_reason="below_volume_threshold")
    note_buffer.add_note("E4", detected_at=0.9)

    assert note_buffer.get_note_window() == ["E4"]
    assert note_buffer.get_metrics()["continuous_silence_duration"] == 0.0


def test_note_buffer_held_e4_with_two_short_below_volume_frames_stays_one_event():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("E4", detected_at=0.0)
    note_buffer.add_note(None, detected_at=0.4, rejection_reason="below_volume_threshold")
    note_buffer.add_note(None, detected_at=0.5, rejection_reason="below_volume_threshold")
    note_buffer.add_note("E4", detected_at=1.0)

    assert note_buffer.get_note_window() == ["E4"]
    assert note_buffer.get_metrics()["continuous_silence_duration"] == 0.0


def test_note_buffer_held_e4_long_clear_silence_then_e4_repeats():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("E4", detected_at=0.0)
    note_buffer.add_note(None, detected_at=0.4, rejection_reason="below_volume_threshold")
    note_buffer.add_note(None, detected_at=0.8, rejection_reason="below_volume_threshold")
    note_buffer.add_note("E4", detected_at=1.0)

    assert note_buffer.get_note_window() == ["E4", "E4"]


def test_note_buffer_keeps_clean_ascending_scale_as_five_events():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index, note_name in enumerate(["C4", "D4", "E4", "F4", "G4"]):
        note_buffer.add_note(note_name, detected_at=index * 0.2)

    assert note_buffer.get_note_window() == ["C4", "D4", "E4", "F4", "G4"]


def test_note_buffer_suppresses_same_note_repeats_inside_melody():
    note_buffer = NoteBuffer(
        window_size=10,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index, note_name in enumerate(["C4", "D4", "E4", "E4", "E4", "F4", "G4"]):
        note_buffer.add_note(note_name, detected_at=index * 0.2)

    assert note_buffer.get_note_window() == ["C4", "D4", "E4", "F4", "G4"]


def test_note_buffer_keeps_long_held_g4_as_one_event():
    note_buffer = NoteBuffer(
        window_size=10,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    for index in range(20):
        note_buffer.add_note("G4", detected_at=index * 0.25)

    assert note_buffer.get_note_window() == ["G4"]


def test_note_buffer_still_allows_same_note_after_clear_silence():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
    )

    note_buffer.add_note("C4", detected_at=0.0)
    note_buffer.add_note(None, detected_at=0.2, rejection_reason="below_volume_threshold")
    note_buffer.add_note(None, detected_at=0.6, rejection_reason="below_volume_threshold")
    note_buffer.add_note("C4", detected_at=0.7)

    assert note_buffer.get_note_window() == ["C4", "C4"]


def test_note_buffer_startup_c7_followed_by_stable_c4_becomes_c4():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        stable_detection_count=2,
        startup_stable_detection_count=3,
    )

    for detected_at, note_name in [
        (0.0, "C7"),
        (0.1, "C4"),
        (0.2, "C4"),
        (0.3, "C4"),
    ]:
        note_buffer.add_note(note_name, detected_at=detected_at)

    metrics = note_buffer.get_metrics()
    assert note_buffer.get_note_window() == ["C4"]
    assert metrics["warmup_active"] is False
    assert metrics["rejected_startup_glitch_count"] == 1


def test_note_buffer_clean_startup_c4_becomes_c4_after_warmup_confirmation():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        stable_detection_count=2,
        startup_stable_detection_count=3,
    )

    assert note_buffer.add_note("C4", detected_at=0.0) is False
    assert note_buffer.add_note("C4", detected_at=0.1) is False
    assert note_buffer.add_note("C4", detected_at=0.2) is True

    assert note_buffer.get_note_window() == ["C4"]
    assert note_buffer.get_metrics()["warmup_active"] is False


def test_note_buffer_warmup_does_not_block_normal_scale_progression():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        stable_detection_count=2,
        startup_stable_detection_count=3,
    )
    frames = [
        "C4",
        "C4",
        "C4",
        "D4",
        "D4",
        "E4",
        "E4",
        "F4",
        "F4",
        "G4",
        "G4",
    ]

    for index, note_name in enumerate(frames):
        note_buffer.add_note(note_name, detected_at=index * 0.1)

    assert note_buffer.get_note_window() == ["C4", "D4", "E4", "F4", "G4"]


def test_note_buffer_rejects_short_transition_glitch_between_notes():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
        stable_detection_count=2,
    )

    for detected_at, note_name in [
        (0.0, "C4"),
        (0.1, "C4"),
        (0.3, "D4"),
        (0.4, "D4"),
        (0.6, "D#4"),
        (0.7, "E4"),
        (0.8, "E4"),
    ]:
        note_buffer.add_note(note_name, detected_at=detected_at)

    assert note_buffer.get_note_window() == ["C4", "D4", "E4"]
    assert note_buffer.get_metrics()["rejected_transition_glitch_count"] == 1


def test_note_buffer_with_confirmation_keeps_held_e4_as_one_event():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
        stable_detection_count=2,
    )

    for index in range(12):
        note_buffer.add_note("E4", detected_at=index * 0.1)

    assert note_buffer.get_note_window() == ["E4"]
    assert note_buffer.get_metrics()["compressed_duplicate_count"] == 9


def test_note_buffer_with_confirmation_keeps_scale_clean():
    note_buffer = NoteBuffer(
        window_size=8,
        debounce_seconds=0.0,
        repeat_gap_seconds=0.3,
        stable_detection_count=2,
    )
    frames = [
        "C4",
        "C4",
        "D4",
        "D4",
        "E4",
        "E4",
        "F4",
        "F4",
        "G4",
        "G4",
    ]

    for index, note_name in enumerate(frames):
        note_buffer.add_note(note_name, detected_at=index * 0.1)

    assert note_buffer.get_note_window() == ["C4", "D4", "E4", "F4", "G4"]


def test_demo_frequency_input_replays_fake_frequencies():
    note_input = DemoFrequencyNoteInput(
        frequencies_hz=[440.0, 261.63],
        interval_seconds=0.5,
        debounce_seconds=0.0,
    )

    assert note_input.tick(now=1.0) is True
    assert note_input.tick(now=1.1) is False
    assert note_input.tick(now=1.6) is True
    assert note_input.get_note_window() == ["A4", "C4"]


def test_pitch_stabilizer_corrects_octave_jump_to_nearby_note():
    stabilizer = PitchStabilizer(minimum_confidence=0.1)

    first = stabilizer.stabilize(PitchEstimate(261.63, 0.9, "test"))
    second = stabilizer.stabilize(PitchEstimate(1046.5, 0.9, "test"))

    assert first.stabilized_note == "C4"
    assert second.raw_note == "C6"
    assert second.stabilized_note == "C4"
    assert second.octave_corrected is True


def test_pitch_stabilizer_keeps_stable_raw_d4_instead_of_forcing_d5():
    stabilizer = PitchStabilizer(minimum_confidence=0.1)

    seed = stabilizer.stabilize(PitchEstimate(587.33, 0.92, "test"))
    first_d4 = stabilizer.stabilize(PitchEstimate(293.66, 0.94, "test"))
    second_d4 = stabilizer.stabilize(PitchEstimate(291.0, 0.93, "test"))
    stable_d4 = stabilizer.stabilize(PitchEstimate(292.0, 0.95, "test"))

    assert seed.stabilized_note == "D5"
    assert first_d4.stabilized_note == "D5"
    assert second_d4.stabilized_note == "D5"
    assert stable_d4.raw_note == "D4"
    assert stable_d4.stabilized_note == "D4"
    assert stable_d4.octave_corrected is False
    assert stable_d4.octave_correction_skipped_reason == "raw_pitch_stable"


def test_pitch_stabilizer_keeps_known_calibration_notes_when_raw_pitch_is_clean():
    expected_notes = [
        (261.63, "C4"),
        (293.66, "D4"),
        (329.63, "E4"),
        (349.23, "F4"),
        (392.0, "G4"),
    ]

    for frequency, note_name in expected_notes:
        stabilizer = PitchStabilizer(minimum_confidence=0.1)
        result = stabilizer.stabilize(PitchEstimate(frequency, 0.95, "test"))

        assert result.stabilized_note == note_name
        assert result.octave_corrected is False


def test_pitch_stabilizer_corrects_isolated_octave_harmonic_spike():
    stabilizer = PitchStabilizer(minimum_confidence=0.1)

    stabilizer.stabilize(PitchEstimate(293.66, 0.95, "test"))
    stabilizer.stabilize(PitchEstimate(292.0, 0.95, "test"))
    harmonic_spike = stabilizer.stabilize(PitchEstimate(587.33, 0.9, "test"))

    assert harmonic_spike.raw_note == "D5"
    assert harmonic_spike.stabilized_note == "D4"
    assert harmonic_spike.octave_corrected is True


def test_pitch_stabilizer_rejects_low_confidence_frequency():
    stabilizer = PitchStabilizer(minimum_confidence=0.5)

    result = stabilizer.stabilize(PitchEstimate(440.0, 0.2, "test"))

    assert result.stabilized_note is None
    assert result.rejection_reason == "low_pitch_confidence"
