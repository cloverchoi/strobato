"""Public entry point for the first Strobato SDK MVP."""

from strobato_sdk.audio import AudioNoteInput, NoteInput, SimulatedNoteInput
from strobato_sdk.engine import StrobatoEngine
from strobato_sdk.models import Measure, NoteEvent, Score, SyncResult
from strobato_sdk.musicxml import parse_musicxml
from strobato_sdk.pitch import (
    frequency_to_midi,
    frequency_to_note_name,
    midi_to_note_name,
    normalize_note_name,
    note_name_to_midi,
)
from strobato_sdk.score_map import (
    ExpectedNote,
    MeasureReference,
    ScoreReferenceMap,
    build_score_reference_map,
)
from strobato_sdk.microphone import (
    DemoFrequencyNoteInput,
    LiveMicrophoneNoteInput,
    MicrophoneDependencyError,
    MicrophoneStartError,
    NoteBuffer,
    estimate_dominant_frequency,
)

__all__ = [
    "Measure",
    "NoteEvent",
    "NoteInput",
    "Score",
    "AudioNoteInput",
    "DemoFrequencyNoteInput",
    "ExpectedNote",
    "MeasureReference",
    "MicrophoneDependencyError",
    "MicrophoneStartError",
    "NoteBuffer",
    "ScoreReferenceMap",
    "SimulatedNoteInput",
    "StrobatoEngine",
    "SyncResult",
    "LiveMicrophoneNoteInput",
    "build_score_reference_map",
    "estimate_dominant_frequency",
    "frequency_to_midi",
    "frequency_to_note_name",
    "midi_to_note_name",
    "normalize_note_name",
    "note_name_to_midi",
    "parse_musicxml",
]
