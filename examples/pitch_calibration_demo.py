from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from strobato_sdk.microphone import (
    NoteBuffer,
    PitchStabilizer,
    estimate_pitch_frequency,
)
from strobato_sdk.pitch import normalize_note_name


CALIBRATION_NOTES = ["C4", "D4", "E4", "F4", "G4"]


@dataclass
class FrameResult:
    target_note: str
    frame_number: int
    raw_frequency_hz: float | None
    raw_note: str | None
    stabilized_note: str | None
    confidence: float
    accepted: bool
    rejected: bool
    rejection_reason: str
    octave_corrected: bool
    octave_correction_skipped_reason: str


@dataclass
class NoteCalibrationResult:
    target_note: str
    frame_results: list[FrameResult]
    final_detected_note: str | None
    average_confidence: float
    matched_expected: bool


def main() -> None:
    args = _parse_args()
    print("Experimental Strobato piano pitch calibration")
    print("---------------------------------------------")
    print("This does not use the score follower.")
    print("It only checks what the microphone pitch layer hears for one known note at a time.")
    print()
    print("For each note, press Enter, then play or hold that one piano note clearly.")
    print("Use a quiet room and keep the microphone close to the piano if possible.")
    print()

    try:
        sounddevice, numpy = _load_recording_dependencies()
    except ModuleNotFoundError:
        print("Pitch calibration requires optional microphone dependencies.")
        print("Install them with:")
        print("  python3 -m pip install sounddevice numpy")
        return

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[NoteCalibrationResult] = []
    for target_note in CALIBRATION_NOTES:
        input(f"Press Enter when ready to record {target_note}...")
        print(f"Recording {target_note} for {args.seconds:.1f} seconds...")
        samples = _record_audio(
            sounddevice=sounddevice,
            numpy=numpy,
            seconds=args.seconds,
            sample_rate=args.sample_rate,
        )
        result = _calibrate_note(
            target_note=target_note,
            samples=samples,
            numpy=numpy,
            sample_rate=args.sample_rate,
            frame_size=args.frame_size,
            hop_size=args.hop_size,
            volume_threshold=args.volume_threshold,
            minimum_pitch_confidence=args.minimum_pitch_confidence,
        )
        results.append(result)
        _print_note_result(result)
        print()

    _write_csv(output_path, results)
    _print_summary(results, output_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record known piano notes and inspect raw/stabilized pitch detection."
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=3.0,
        help="How long to record each note.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/pitch_calibration.csv"),
        help="CSV path for calibration results.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Microphone sample rate.",
    )
    parser.add_argument(
        "--frame-size",
        type=int,
        default=4096,
        help="Number of audio samples analyzed per pitch estimate.",
    )
    parser.add_argument(
        "--hop-size",
        type=int,
        default=2048,
        help="How far to move between audio analysis frames.",
    )
    parser.add_argument(
        "--volume-threshold",
        type=float,
        default=0.01,
        help="Reject frames quieter than this rough volume level.",
    )
    parser.add_argument(
        "--minimum-pitch-confidence",
        type=float,
        default=0.35,
        help="Reject pitch estimates below this confidence.",
    )
    return parser.parse_args()


def _load_recording_dependencies():
    import numpy
    import sounddevice

    return sounddevice, numpy


def _record_audio(sounddevice, numpy, seconds: float, sample_rate: int):
    try:
        recording = sounddevice.rec(
            int(seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sounddevice.wait()
    except Exception as exc:
        print("Could not record from the microphone.")
        print("Check microphone permissions, input device selection, and whether another app is using it.")
        raise SystemExit(1) from exc

    if getattr(recording, "ndim", 1) > 1:
        return recording[:, 0]
    return numpy.asarray(recording, dtype=float)


def _calibrate_note(
    target_note: str,
    samples,
    numpy,
    sample_rate: int,
    frame_size: int,
    hop_size: int,
    volume_threshold: float,
    minimum_pitch_confidence: float,
) -> NoteCalibrationResult:
    stabilizer = PitchStabilizer(minimum_confidence=minimum_pitch_confidence)
    note_buffer = NoteBuffer(
        window_size=20,
        debounce_seconds=0.12,
        minimum_note_duration_seconds=0.06,
        stable_detection_count=1,
    )
    frame_results: list[FrameResult] = []
    accepted_confidences: list[float] = []

    total_samples = len(samples)
    if total_samples < frame_size:
        frame_starts = [0]
    else:
        frame_starts = range(0, total_samples - frame_size + 1, hop_size)

    for frame_number, start in enumerate(frame_starts, start=1):
        frame = samples[start : start + frame_size]
        estimate = estimate_pitch_frequency(
            frame,
            sample_rate=sample_rate,
            volume_threshold=volume_threshold,
            numpy_module=numpy,
        )
        stabilized = stabilizer.stabilize(estimate)
        detected_at = start / sample_rate
        accepted = note_buffer.add_note(
            stabilized.stabilized_note,
            detected_at=detected_at,
            raw_frequency=stabilized.raw_frequency_hz,
            raw_note=stabilized.raw_note,
            octave_corrected=stabilized.octave_corrected,
            octave_correction_skipped_reason=stabilized.octave_correction_skipped_reason,
            confidence=stabilized.confidence,
            rejection_reason=stabilized.rejection_reason,
        )
        if accepted:
            accepted_confidences.append(stabilized.confidence)

        rejection_reason = (
            stabilized.rejection_reason
            or note_buffer.last_rejection_reason
            or estimate.rejection_reason
        )
        frame_results.append(
            FrameResult(
                target_note=target_note,
                frame_number=frame_number,
                raw_frequency_hz=stabilized.raw_frequency_hz,
                raw_note=stabilized.raw_note,
                stabilized_note=stabilized.stabilized_note,
                confidence=stabilized.confidence,
                accepted=accepted,
                rejected=not accepted,
                rejection_reason=rejection_reason,
                octave_corrected=stabilized.octave_corrected,
                octave_correction_skipped_reason=stabilized.octave_correction_skipped_reason,
            )
        )

    final_note = _most_common_note(
        [
            frame.stabilized_note
            for frame in frame_results
            if frame.stabilized_note is not None
        ]
    )
    average_confidence = (
        sum(accepted_confidences) / len(accepted_confidences)
        if accepted_confidences
        else 0.0
    )
    return NoteCalibrationResult(
        target_note=target_note,
        frame_results=frame_results,
        final_detected_note=final_note,
        average_confidence=average_confidence,
        matched_expected=final_note == target_note,
    )


def _most_common_note(notes: list[str]) -> str | None:
    if not notes:
        return None
    return Counter(notes).most_common(1)[0][0]


def _print_note_result(result: NoteCalibrationResult) -> None:
    raw_frequencies = [
        f"{frame.raw_frequency_hz:.1f}"
        for frame in result.frame_results
        if frame.raw_frequency_hz is not None
    ]
    raw_notes = [
        frame.raw_note
        for frame in result.frame_results
        if frame.raw_note is not None
    ]
    stabilized_notes = [
        frame.stabilized_note
        for frame in result.frame_results
        if frame.stabilized_note is not None
    ]
    rejected = [frame for frame in result.frame_results if frame.rejected]
    octave_corrections = [frame for frame in result.frame_results if frame.octave_corrected]
    stable_raw_skips = [
        frame
        for frame in result.frame_results
        if frame.octave_correction_skipped_reason == "raw_pitch_stable"
    ]

    print(f"Expected note: {result.target_note}")
    print(f"Raw frequency estimates: {_preview(raw_frequencies)}")
    print(f"Raw note estimates: {_preview(raw_notes)}")
    print(f"Stabilized note estimates: {_preview(stabilized_notes)}")
    print(f"Final stabilized note: {result.final_detected_note or 'none'}")
    print(f"Average accepted confidence: {result.average_confidence:.2f}")
    print(f"Rejected detections: {len(rejected)}")
    print(f"Octave corrections applied: {len(octave_corrections)}")
    print(f"Octave corrections skipped because raw pitch was stable: {len(stable_raw_skips)}")
    print(f"Matches expected note: {result.matched_expected}")


def _preview(values: list[str], limit: int = 16) -> str:
    if not values:
        return "none"
    preview = values[:limit]
    suffix = " ..." if len(values) > limit else ""
    return ", ".join(preview) + suffix


def _write_csv(output_path: Path, results: list[NoteCalibrationResult]) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=[
                "target_note",
                "frame_number",
                "raw_frequency_hz",
                "raw_note",
                "stabilized_note",
                "confidence",
                "accepted",
                "rejected",
                "rejection_reason",
                "octave_corrected",
                "octave_correction_skipped_reason",
                "final_detected_note",
                "matched_expected",
            ],
        )
        writer.writeheader()
        for result in results:
            for frame in result.frame_results:
                writer.writerow(
                    {
                        "target_note": frame.target_note,
                        "frame_number": frame.frame_number,
                        "raw_frequency_hz": (
                            f"{frame.raw_frequency_hz:.3f}"
                            if frame.raw_frequency_hz is not None
                            else ""
                        ),
                        "raw_note": frame.raw_note or "",
                        "stabilized_note": frame.stabilized_note or "",
                        "confidence": f"{frame.confidence:.3f}",
                        "accepted": frame.accepted,
                        "rejected": frame.rejected,
                        "rejection_reason": frame.rejection_reason,
                        "octave_corrected": frame.octave_corrected,
                        "octave_correction_skipped_reason": frame.octave_correction_skipped_reason,
                        "final_detected_note": result.final_detected_note or "",
                        "matched_expected": result.matched_expected,
                    }
                )


def _print_summary(results: list[NoteCalibrationResult], output_path: Path) -> None:
    correct_results = [result for result in results if result.matched_expected]
    octave_errors: Counter[str] = Counter()
    wrong_notes: Counter[str] = Counter()

    for result in results:
        detected = result.final_detected_note
        if detected is None or result.matched_expected:
            continue
        same_pitch_class = (
            normalize_note_name(detected, ignore_octave=True)
            == normalize_note_name(result.target_note, ignore_octave=True)
        )
        if same_pitch_class:
            octave_errors[f"{result.target_note} detected as {detected}"] += 1
        else:
            wrong_notes[f"{result.target_note} detected as {detected}"] += 1

    print("Calibration summary")
    print("-------------------")
    print(f"CSV saved to: {output_path}")
    print(f"Notes correctly detected: {len(correct_results)} / {len(results)}")
    print(f"Common octave errors: {_format_counter(octave_errors)}")
    print(f"Common wrong notes: {_format_counter(wrong_notes)}")
    if len(correct_results) >= 4:
        print("Good enough for score-following experiments: yes, cautiously.")
    else:
        print("Good enough for score-following experiments: not yet; pitch detection still needs work.")


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{label} ({count})" for label, count in counter.most_common())


if __name__ == "__main__":
    main()
