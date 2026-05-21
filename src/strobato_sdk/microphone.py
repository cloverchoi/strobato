"""Experimental live microphone note detection.

This module is intentionally small and optional. It is not used by the default
SDK path, and it only runs when a developer explicitly starts the microphone
demo.

Microphone input arrives as many tiny audio frames. Each frame is a short slice
of sound samples. This prototype estimates pitch with autocorrelation, converts
that frequency to a note name with pitch.py, stabilizes octave jumps, and keeps
a rolling window of recent notes.

Real-world piano detection is hard because piano notes decay, include overtones,
often overlap as chords, and can be noisy in a room. This first version is only
for simple monophonic experiments.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque

from strobato_sdk.pitch import frequency_to_midi, frequency_to_note_name, midi_to_note_name


class MicrophoneDependencyError(RuntimeError):
    """Raised when optional microphone dependencies are not installed."""


class MicrophoneStartError(RuntimeError):
    """Raised when the microphone cannot be opened or started."""


@dataclass
class NoteEventCompressor:
    """Turns repeated frame detections into musical note events.

    A held piano note can be detected dozens of times while it rings. The score
    follower wants one C4 event, not C4 C4 C4 C4. This compressor only allows
    the same note through again after a longer pause, which suggests the player
    intentionally repeated it. Time alone is not enough, because a held piano
    note can ring for several seconds.
    """

    repeat_gap_seconds: float = 0.35
    last_event_note: str | None = None
    last_event_at: float = 0.0
    silence_started_at: float | None = None
    last_silence_at: float | None = None
    compressed_duplicate_count: int = 0
    last_compression_reason: str = ""

    def observe_silence(self, detected_at: float) -> None:
        """Remember that the microphone heard a quiet gap."""
        if self.silence_started_at is None:
            self.silence_started_at = detected_at
        self.last_silence_at = detected_at

    def should_add_event(self, note_name: str, detected_at: float) -> bool:
        if note_name != self.last_event_note:
            self.last_event_note = note_name
            self.last_event_at = detected_at
            self._clear_silence()
            self.last_compression_reason = ""
            return True

        had_clear_silence = (
            self.continuous_silence_duration() >= self.repeat_gap_seconds
        )
        if had_clear_silence:
            self.last_event_at = detected_at
            self._clear_silence()
            self.last_compression_reason = ""
            return True

        # Sound resumed before the quiet gap was long enough, so this was not
        # a real silence between two intentional repeats.
        self._clear_silence()
        self.compressed_duplicate_count += 1
        self.last_compression_reason = "compressed_held_note"
        return False

    def continuous_silence_duration(self) -> float:
        if self.silence_started_at is None or self.last_silence_at is None:
            return 0.0
        return max(self.last_silence_at - self.silence_started_at, 0.0)

    def _clear_silence(self) -> None:
        self.silence_started_at = None
        self.last_silence_at = None

    def reset(self) -> None:
        self.last_event_note = None
        self.last_event_at = 0.0
        self._clear_silence()
        self.compressed_duplicate_count = 0
        self.last_compression_reason = ""


@dataclass
class NoteBuffer:
    """Debounces noisy note detections into a clean rolling note window.

    Raw microphone output can report the same note many times per second. The
    score follower needs musical note events, not every audio-frame estimate, so
    this buffer avoids duplicate spam and smooths small bursts of unstable
    detections.
    """

    window_size: int = 12
    debounce_seconds: float = 0.25
    minimum_note_duration_seconds: float = 0.08
    stable_detection_count: int = 1
    startup_stable_detection_count: int = 1
    repeat_gap_seconds: float = 0.35
    _notes: Deque[str] = field(default_factory=deque, init=False)
    _raw_notes: Deque[str] = field(default_factory=deque, init=False)
    _last_accepted_note: str | None = field(default=None, init=False)
    _last_accepted_at: float = field(default=0.0, init=False)
    _pending_note: str | None = field(default=None, init=False)
    _pending_count: int = field(default=0, init=False)
    _pending_started_at: float | None = field(default=None, init=False)
    _compressor: NoteEventCompressor = field(init=False)
    raw_detection_count: int = 0
    accepted_note_count: int = 0
    rejected_detection_count: int = 0
    rejected_startup_glitch_count: int = 0
    rejected_transition_glitch_count: int = 0
    octave_correction_count: int = 0
    last_raw_frequency: float | None = None
    last_raw_note: str | None = None
    last_stabilized_note: str | None = None
    last_rejection_reason: str = ""
    last_octave_correction_skipped_reason: str = ""
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self._compressor = NoteEventCompressor(
            repeat_gap_seconds=self.repeat_gap_seconds
        )

    def add_note(
        self,
        note_name: str | None,
        detected_at: float | None = None,
        raw_frequency: float | None = None,
        raw_note: str | None = None,
        octave_corrected: bool = False,
        octave_correction_skipped_reason: str = "",
        confidence: float | None = None,
        rejection_reason: str = "",
    ) -> bool:
        """Try to add one detected note to the rolling window.

        Returns true only when the note is accepted as a new musical event.
        """
        self.last_raw_frequency = raw_frequency
        self.last_raw_note = raw_note
        self.last_stabilized_note = note_name
        self.last_rejection_reason = rejection_reason
        self.last_octave_correction_skipped_reason = octave_correction_skipped_reason
        if octave_corrected:
            self.octave_correction_count += 1

        detected_at = detected_at if detected_at is not None else time.monotonic()
        if note_name is None:
            self.rejected_detection_count += 1
            if _is_silence_rejection(rejection_reason):
                self._compressor.observe_silence(detected_at)
                self._pending_note = None
                self._pending_count = 0
                self._pending_started_at = None
            return False

        self.raw_detection_count += 1
        self._raw_notes.append(note_name)
        while len(self._raw_notes) > self.window_size:
            self._raw_notes.popleft()

        if note_name == self._pending_note:
            self._pending_count += 1
        else:
            self._count_transition_glitch_if_needed()
            self._pending_note = note_name
            self._pending_count = 1
            self._pending_started_at = detected_at

        required_detection_count = self._required_detection_count()
        if self._pending_count < required_detection_count:
            self.rejected_detection_count += 1
            self.last_rejection_reason = "waiting_for_stable_repeated_detection"
            return False

        repeated_duration = (
            note_name == self._last_accepted_note
            and detected_at - self._last_accepted_at < self.minimum_note_duration_seconds
        )
        if repeated_duration:
            self.rejected_detection_count += 1
            self.last_rejection_reason = "below_minimum_note_duration"
            return False

        repeated_too_soon = (
            note_name == self._last_accepted_note
            and detected_at - self._last_accepted_at < self.debounce_seconds
        )
        if repeated_too_soon:
            self.rejected_detection_count += 1
            self.last_rejection_reason = "debounced_duplicate_note"
            return False

        if not self._compressor.should_add_event(note_name, detected_at):
            self.rejected_detection_count += 1
            self.last_rejection_reason = self._compressor.last_compression_reason
            return False

        self._notes.append(note_name)
        while len(self._notes) > self.window_size:
            self._notes.popleft()

        self._last_accepted_note = note_name
        self._last_accepted_at = detected_at
        self._pending_note = None
        self._pending_count = 0
        self._pending_started_at = None
        self.accepted_note_count += 1
        self.last_rejection_reason = ""
        return True

    def _count_transition_glitch_if_needed(self) -> None:
        if self._pending_note is None:
            return
        if self._pending_count >= self._required_detection_count():
            return
        if self._warmup_active():
            self.rejected_startup_glitch_count += 1
            return
        self.rejected_transition_glitch_count += 1

    def _required_detection_count(self) -> int:
        if self._warmup_active():
            return max(self.stable_detection_count, self.startup_stable_detection_count)
        return self.stable_detection_count

    def _warmup_active(self) -> bool:
        return self.accepted_note_count == 0

    def get_note_window(self) -> list[str]:
        return list(self._notes)

    def get_raw_note_window(self) -> list[str]:
        return list(self._raw_notes)

    def reset(self) -> None:
        self._notes.clear()
        self._raw_notes.clear()
        self._last_accepted_note = None
        self._last_accepted_at = 0.0
        self._pending_note = None
        self._pending_count = 0
        self._pending_started_at = None
        self._compressor.reset()
        self.raw_detection_count = 0
        self.accepted_note_count = 0
        self.rejected_detection_count = 0
        self.rejected_startup_glitch_count = 0
        self.rejected_transition_glitch_count = 0
        self.octave_correction_count = 0
        self.last_raw_frequency = None
        self.last_raw_note = None
        self.last_stabilized_note = None
        self.last_rejection_reason = ""
        self.last_octave_correction_skipped_reason = ""
        self.started_at = time.monotonic()

    def get_metrics(self) -> dict[str, float | int | list[str] | str | None]:
        elapsed = max(time.monotonic() - self.started_at, 1.0)
        return {
            "raw_detection_count": self.raw_detection_count,
            "accepted_note_count": self.accepted_note_count,
            "rejected_detection_count": self.rejected_detection_count,
            "rejected_startup_glitch_count": self.rejected_startup_glitch_count,
            "rejected_transition_glitch_count": self.rejected_transition_glitch_count,
            "octave_correction_count": self.octave_correction_count,
            "compressed_duplicate_count": self._compressor.compressed_duplicate_count,
            "note_detection_rate": round(self.accepted_note_count / elapsed, 2),
            "raw_detection_rate": round(self.raw_detection_count / elapsed, 2),
            "note_buffer": self.get_note_window(),
            "raw_note_buffer": self.get_raw_note_window(),
            "warmup_active": self._warmup_active(),
            "continuous_silence_duration": round(
                self._compressor.continuous_silence_duration(), 3
            ),
            "candidate_note": self._pending_note,
            "candidate_duration": self._candidate_duration(),
            "last_raw_frequency": self.last_raw_frequency,
            "last_raw_note": self.last_raw_note,
            "last_stabilized_note": self.last_stabilized_note,
            "last_rejection_reason": self.last_rejection_reason,
            "last_octave_correction_skipped_reason": self.last_octave_correction_skipped_reason,
        }

    def _candidate_duration(self) -> float:
        if self._pending_started_at is None:
            return 0.0
        return round(max(time.monotonic() - self._pending_started_at, 0.0), 3)


def _is_silence_rejection(rejection_reason: str) -> bool:
    return rejection_reason in {
        "below_volume_threshold",
        "empty_audio_frame",
        "no_correlation",
        "no_frequency",
    }


@dataclass(frozen=True)
class PitchEstimate:
    frequency_hz: float | None
    confidence: float
    method: str
    rejection_reason: str = ""


@dataclass(frozen=True)
class StabilizedPitch:
    raw_frequency_hz: float | None
    raw_note: str | None
    stabilized_note: str | None
    confidence: float
    octave_corrected: bool = False
    octave_correction_skipped_reason: str = ""
    rejection_reason: str = ""


@dataclass
class PitchStabilizer:
    """Smooths octave jumps after raw frequency estimation.

    Piano overtones can make a detector hear C5 or C6 when the player meant C4.
    This stabilizer prefers octave continuity with the last accepted note.
    """

    minimum_confidence: float = 0.35
    max_octave_jump: int = 9
    stable_raw_count: int = 3
    high_confidence_threshold: float = 0.7
    last_midi: int | None = None
    _recent_raw_midis: Deque[int] = field(default_factory=deque, init=False)

    def stabilize(self, estimate: PitchEstimate) -> StabilizedPitch:
        raw_note = frequency_to_note_name(estimate.frequency_hz)
        raw_midi = frequency_to_midi(estimate.frequency_hz)

        if estimate.frequency_hz is None or raw_note is None or raw_midi is None:
            return StabilizedPitch(
                raw_frequency_hz=estimate.frequency_hz,
                raw_note=raw_note,
                stabilized_note=None,
                confidence=estimate.confidence,
                rejection_reason=estimate.rejection_reason or "no_frequency",
            )

        if estimate.confidence < self.minimum_confidence:
            return StabilizedPitch(
                raw_frequency_hz=estimate.frequency_hz,
                raw_note=raw_note,
                stabilized_note=None,
                confidence=estimate.confidence,
                rejection_reason="low_pitch_confidence",
            )

        self._remember_raw_midi(raw_midi)
        stabilized_midi = raw_midi
        octave_corrected = False
        octave_correction_skipped_reason = ""
        if self.last_midi is not None:
            raw_jump = abs(raw_midi - self.last_midi)
            raw_pitch_is_stable = self._raw_pitch_is_stable(raw_midi, estimate.confidence)
            if raw_jump > self.max_octave_jump and raw_pitch_is_stable:
                self.last_midi = raw_midi
                return StabilizedPitch(
                    raw_frequency_hz=estimate.frequency_hz,
                    raw_note=raw_note,
                    stabilized_note=raw_note,
                    confidence=estimate.confidence,
                    octave_correction_skipped_reason="raw_pitch_stable",
                )

            if raw_jump > self.max_octave_jump:
                candidates = [raw_midi + (12 * octave_shift) for octave_shift in range(-4, 5)]
                stabilized_midi = min(candidates, key=lambda midi: abs(midi - self.last_midi))
                octave_corrected = stabilized_midi != raw_midi

            if abs(stabilized_midi - self.last_midi) > self.max_octave_jump:
                return StabilizedPitch(
                    raw_frequency_hz=estimate.frequency_hz,
                    raw_note=raw_note,
                    stabilized_note=None,
                    confidence=estimate.confidence,
                    octave_corrected=octave_corrected,
                    rejection_reason="unstable_large_pitch_jump",
                )

        self.last_midi = stabilized_midi
        return StabilizedPitch(
            raw_frequency_hz=estimate.frequency_hz,
            raw_note=raw_note,
            stabilized_note=midi_to_note_name(stabilized_midi),
            confidence=estimate.confidence,
            octave_corrected=octave_corrected,
            octave_correction_skipped_reason=octave_correction_skipped_reason,
        )

    def _remember_raw_midi(self, raw_midi: int) -> None:
        self._recent_raw_midis.append(raw_midi)
        while len(self._recent_raw_midis) > self.stable_raw_count:
            self._recent_raw_midis.popleft()

    def _raw_pitch_is_stable(self, raw_midi: int, confidence: float) -> bool:
        if confidence < self.high_confidence_threshold:
            return False
        if len(self._recent_raw_midis) < self.stable_raw_count:
            return False
        return all(abs(recent_midi - raw_midi) <= 1 for recent_midi in self._recent_raw_midis)


@dataclass
class LiveMicrophoneNoteInput:
    """Optional live note source that matches the NoteInput interface.

    Call start() to begin listening and get_note_window() to read recent detected
    note names. The implementation uses sounddevice for microphone capture and
    numpy for autocorrelation-based frequency estimation.
    """

    sample_rate: int = 44100
    frame_size: int = 4096
    window_size: int = 12
    debounce_seconds: float = 0.25
    minimum_note_duration_seconds: float = 0.08
    repeat_gap_seconds: float = 0.35
    stable_detection_count: int = 2
    startup_stable_detection_count: int = 3
    minimum_pitch_confidence: float = 0.35
    max_octave_jump: int = 9
    min_frequency_hz: float = 60.0
    max_frequency_hz: float = 2000.0
    volume_threshold: float = 0.01
    _stream: object | None = field(default=None, init=False)
    _buffer: NoteBuffer = field(init=False)
    _stabilizer: PitchStabilizer = field(init=False)

    def __post_init__(self) -> None:
        self._buffer = NoteBuffer(
            window_size=self.window_size,
            debounce_seconds=self.debounce_seconds,
            minimum_note_duration_seconds=self.minimum_note_duration_seconds,
            stable_detection_count=self.stable_detection_count,
            startup_stable_detection_count=self.startup_stable_detection_count,
            repeat_gap_seconds=self.repeat_gap_seconds,
        )
        self._stabilizer = PitchStabilizer(
            minimum_confidence=self.minimum_pitch_confidence,
            max_octave_jump=self.max_octave_jump,
        )

    def start(self) -> None:
        """Start listening to the default microphone.

        This imports optional packages only when live microphone mode is used,
        so the normal simulated SDK works without installing audio dependencies.
        """
        sounddevice, numpy = _load_audio_dependencies()

        def audio_callback(indata, frames, time, status) -> None:  # type: ignore[no-untyped-def]
            del frames, time
            if status:
                return

            samples = indata[:, 0] if getattr(indata, "ndim", 1) > 1 else indata
            estimate = estimate_pitch_frequency(
                samples,
                sample_rate=self.sample_rate,
                min_frequency_hz=self.min_frequency_hz,
                max_frequency_hz=self.max_frequency_hz,
                volume_threshold=self.volume_threshold,
                numpy_module=numpy,
            )
            stabilized = self._stabilizer.stabilize(estimate)
            self._buffer.add_note(
                stabilized.stabilized_note,
                raw_frequency=stabilized.raw_frequency_hz,
                raw_note=stabilized.raw_note,
                octave_corrected=stabilized.octave_corrected,
                octave_correction_skipped_reason=stabilized.octave_correction_skipped_reason,
                confidence=stabilized.confidence,
                rejection_reason=stabilized.rejection_reason,
            )

        try:
            self._stream = sounddevice.InputStream(
                channels=1,
                callback=audio_callback,
                blocksize=self.frame_size,
                samplerate=self.sample_rate,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise MicrophoneStartError(
                "Could not start microphone input. Check that a microphone is "
                "connected, allowed by your system privacy settings, and not "
                "already in use by another app."
            ) from exc

    def stop(self) -> None:
        """Stop listening and release the microphone."""
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def get_note_window(self) -> list[str]:
        """Return the latest rolling stream of detected note names."""
        return self._buffer.get_note_window()

    def get_metrics(self) -> dict[str, float | int | list[str] | str | None]:
        """Return lightweight debug metrics for demos."""
        return self._buffer.get_metrics()

    def add_detected_frequency(self, frequency_hz: float, detected_at: float | None = None) -> bool:
        """Feed a fake detected frequency through the same debouncing path.

        This supports demo mode and tests without requiring live microphone
        hardware.
        """
        stabilized = self._stabilizer.stabilize(
            PitchEstimate(frequency_hz=frequency_hz, confidence=1.0, method="fake")
        )
        return self._buffer.add_note(
            stabilized.stabilized_note,
            detected_at=detected_at,
            raw_frequency=stabilized.raw_frequency_hz,
            raw_note=stabilized.raw_note,
            octave_corrected=stabilized.octave_corrected,
            octave_correction_skipped_reason=stabilized.octave_correction_skipped_reason,
            confidence=stabilized.confidence,
            rejection_reason=stabilized.rejection_reason,
        )


@dataclass
class DemoFrequencyNoteInput:
    """Replay fake frequencies over time through the same note buffer.

    This is useful for investor demos and local testing when no microphone is
    available. It simulates the output of a pitch detector, not a real audio
    recording.
    """

    frequencies_hz: list[float]
    interval_seconds: float = 0.55
    window_size: int = 8
    debounce_seconds: float = 0.2
    minimum_note_duration_seconds: float = 0.08
    repeat_gap_seconds: float = 0.35
    _buffer: NoteBuffer = field(init=False)
    _stabilizer: PitchStabilizer = field(init=False)
    _index: int = field(default=0, init=False)
    _last_emit_at: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._buffer = NoteBuffer(
            window_size=self.window_size,
            debounce_seconds=self.debounce_seconds,
            minimum_note_duration_seconds=self.minimum_note_duration_seconds,
            stable_detection_count=1,
            startup_stable_detection_count=1,
            repeat_gap_seconds=self.repeat_gap_seconds,
        )
        self._stabilizer = PitchStabilizer(minimum_confidence=0.0)

    def tick(self, now: float | None = None) -> bool:
        """Advance the fake performance when enough time has passed."""
        now = now if now is not None else time.monotonic()
        if self._index >= len(self.frequencies_hz):
            return False
        if self._last_emit_at and now - self._last_emit_at < self.interval_seconds:
            return False

        frequency = self.frequencies_hz[self._index]
        self._index += 1
        self._last_emit_at = now
        stabilized = self._stabilizer.stabilize(
            PitchEstimate(frequency_hz=frequency, confidence=1.0, method="demo")
        )
        return self._buffer.add_note(
            stabilized.stabilized_note,
            now,
            raw_frequency=stabilized.raw_frequency_hz,
            raw_note=stabilized.raw_note,
            octave_corrected=stabilized.octave_corrected,
            octave_correction_skipped_reason=stabilized.octave_correction_skipped_reason,
            confidence=stabilized.confidence,
            rejection_reason=stabilized.rejection_reason,
        )

    def get_note_window(self) -> list[str]:
        return self._buffer.get_note_window()

    def get_metrics(self) -> dict[str, float | int | list[str]]:
        metrics = self._buffer.get_metrics()
        metrics["demo_step"] = self._index
        metrics["demo_total_steps"] = len(self.frequencies_hz)
        return metrics


def estimate_pitch_frequency(
    samples,
    sample_rate: int,
    min_frequency_hz: float = 60.0,
    max_frequency_hz: float = 2000.0,
    volume_threshold: float = 0.01,
    numpy_module=None,
) -> PitchEstimate:
    """Estimate pitch with autocorrelation.

    Autocorrelation looks for repeating wave periods in the audio frame. It is
    usually steadier than simply picking the loudest FFT bin, especially when a
    piano note has strong overtones.
    """
    numpy = numpy_module or _load_numpy()
    audio = numpy.asarray(samples, dtype=float)
    if audio.size == 0:
        return PitchEstimate(None, 0.0, "autocorrelation", "empty_audio_frame")

    audio = audio - numpy.mean(audio)
    if float(numpy.sqrt(numpy.mean(audio * audio))) < volume_threshold:
        return PitchEstimate(None, 0.0, "autocorrelation", "below_volume_threshold")

    window = numpy.hanning(audio.size)
    windowed_audio = audio * window
    correlation = numpy.correlate(windowed_audio, windowed_audio, mode="full")
    correlation = correlation[correlation.size // 2 :]
    if correlation.size == 0 or correlation[0] <= 0:
        return PitchEstimate(None, 0.0, "autocorrelation", "no_correlation")

    min_lag = max(1, int(sample_rate / max_frequency_hz))
    max_lag = min(correlation.size - 1, int(sample_rate / min_frequency_hz))
    if max_lag <= min_lag:
        return PitchEstimate(None, 0.0, "autocorrelation", "invalid_lag_range")

    search_region = correlation[min_lag:max_lag]
    if search_region.size == 0:
        return PitchEstimate(None, 0.0, "autocorrelation", "empty_lag_region")

    peak_offset = int(numpy.argmax(search_region))
    peak_lag = min_lag + peak_offset
    confidence = float(correlation[peak_lag] / correlation[0])
    if peak_lag <= 0:
        return PitchEstimate(None, confidence, "autocorrelation", "invalid_peak_lag")

    frequency = float(sample_rate / peak_lag)
    return PitchEstimate(frequency, confidence, "autocorrelation")


def estimate_dominant_frequency(
    samples,
    sample_rate: int,
    min_frequency_hz: float = 60.0,
    max_frequency_hz: float = 2000.0,
    volume_threshold: float = 0.01,
    numpy_module=None,
) -> float | None:
    """Compatibility wrapper returning only the estimated frequency."""
    estimate = estimate_pitch_frequency(
        samples,
        sample_rate=sample_rate,
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
        volume_threshold=volume_threshold,
        numpy_module=numpy_module,
    )
    return estimate.frequency_hz


def estimate_fft_dominant_frequency(
    samples,
    sample_rate: int,
    min_frequency_hz: float = 60.0,
    max_frequency_hz: float = 2000.0,
    volume_threshold: float = 0.01,
    numpy_module=None,
) -> float | None:
    """Older simple FFT method kept for comparison/debugging."""
    numpy = numpy_module or _load_numpy()
    audio = numpy.asarray(samples, dtype=float)
    if audio.size == 0:
        return None

    audio = audio - numpy.mean(audio)
    if float(numpy.sqrt(numpy.mean(audio * audio))) < volume_threshold:
        return None

    window = numpy.hanning(audio.size)
    spectrum = numpy.abs(numpy.fft.rfft(audio * window))
    frequencies = numpy.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    frequency_mask = (frequencies >= min_frequency_hz) & (frequencies <= max_frequency_hz)

    if not numpy.any(frequency_mask):
        return None

    masked_spectrum = spectrum[frequency_mask]
    masked_frequencies = frequencies[frequency_mask]
    strongest_index = int(numpy.argmax(masked_spectrum))
    return float(masked_frequencies[strongest_index])


def _load_audio_dependencies():
    try:
        import numpy
        import sounddevice
    except ModuleNotFoundError as exc:
        raise MicrophoneDependencyError(
            "Live microphone mode requires optional packages. Install them with: "
            "python3 -m pip install sounddevice numpy"
        ) from exc

    return sounddevice, numpy


def _load_numpy():
    try:
        import numpy
    except ModuleNotFoundError as exc:
        raise MicrophoneDependencyError(
            "Frequency estimation requires numpy. Install it with: "
            "python3 -m pip install numpy"
        ) from exc

    return numpy
