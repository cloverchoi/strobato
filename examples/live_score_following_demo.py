from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from strobato_sdk import StrobatoEngine
from strobato_sdk.microphone import (
    DemoFrequencyNoteInput,
    LiveMicrophoneNoteInput,
    MicrophoneDependencyError,
    MicrophoneStartError,
)


DEMO_FREQUENCIES = [
    329.63,  # E4
    311.13,  # D#4
    329.63,  # E4
    311.13,  # D#4
    329.63,  # E4
    246.94,  # B3
    293.66,  # D4
    261.63,  # C4
    220.00,  # A3
]


@dataclass
class CsvLogger:
    file_handle: object
    writer: csv.DictWriter

    def close(self) -> None:
        self.file_handle.close()

    def write_row(
        self,
        timestamp_seconds: float,
        note_window: list[str],
        current_measure: int | None,
        current_note_index: int | None,
        confidence_score: float,
        tracking_status: str,
        page_turn_signal: bool,
        input_metrics: dict,
    ) -> None:
        self.writer.writerow(
            {
                "timestamp_seconds": f"{timestamp_seconds:.3f}",
                "detected_note_window": " ".join(note_window),
                "current_measure": current_measure if current_measure is not None else "",
                "current_note_index": current_note_index if current_note_index is not None else "",
                "confidence_score": f"{confidence_score:.2f}",
                "tracking_status": tracking_status,
                "page_turn_signal": page_turn_signal,
                "raw_detected_frequency": input_metrics.get("last_raw_frequency") or "",
                "raw_detected_note": input_metrics.get("last_raw_note") or "",
                "stabilized_note": input_metrics.get("last_stabilized_note") or "",
                "raw_note_buffer": " ".join(input_metrics.get("raw_note_buffer") or []),
                "candidate_note": input_metrics.get("candidate_note") or "",
                "candidate_duration": input_metrics.get("candidate_duration") or 0.0,
                "warmup_active": input_metrics.get("warmup_active"),
                "continuous_silence_duration": (
                    input_metrics.get("continuous_silence_duration") or 0.0
                ),
                "rejected_detection_count": input_metrics.get("rejected_detection_count") or 0,
                "rejected_startup_glitch_count": (
                    input_metrics.get("rejected_startup_glitch_count") or 0
                ),
                "rejected_transition_glitch_count": (
                    input_metrics.get("rejected_transition_glitch_count") or 0
                ),
                "compressed_duplicate_count": (
                    input_metrics.get("compressed_duplicate_count") or 0
                ),
                "octave_correction_count": input_metrics.get("octave_correction_count") or 0,
                "octave_correction_skipped_reason": (
                    input_metrics.get("last_octave_correction_skipped_reason") or ""
                ),
                "last_rejection_reason": input_metrics.get("last_rejection_reason") or "",
            }
        )
        self.file_handle.flush()


def main() -> None:
    args = _parse_args()
    print("Experimental Strobato live score-following demo")
    print("------------------------------------------------")
    print("Flow: audio/fake frequencies -> detected notes -> StrobatoEngine -> score position")
    print()
    print("This is a prototype, not production piano transcription.")
    print("Limitations:")
    print("  - monophonic only; play one clear note at a time")
    print("  - autocorrelation pitch estimation in microphone mode")
    print("  - noisy rooms can confuse detection")
    print("  - no chord detection yet")
    print("  - not production-ready")
    print()

    score_path = _resolve_score_path(args.score)
    engine = StrobatoEngine(score=score_path, measures_per_page=2)
    note_input = _create_note_input(args)
    if note_input is None:
        return

    print("Press Ctrl+C to stop.")
    print(f"Score: {score_path}")
    print()

    log_file = _open_log_file(args.log)
    try:
        try:
            _run_loop(engine, note_input, demo_mode=args.demo, log_file=log_file)
        except KeyboardInterrupt:
            print("\nStopping live score-following demo.")
    finally:
        if log_file is not None:
            log_file.close()
        if hasattr(note_input, "stop"):
            note_input.stop()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experimental Strobato microphone-to-score-following demo."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Replay fake frequencies instead of opening a microphone.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=8,
        help="Number of accepted notes to keep in the rolling note window.",
    )
    parser.add_argument(
        "--score",
        type=Path,
        default=Path(__file__).with_name("simple_score.musicxml"),
        help="MusicXML score to follow.",
    )
    parser.add_argument(
        "--repeat-gap-seconds",
        type=float,
        default=0.35,
        help="Quiet gap required before the same note can count as a new event.",
    )
    parser.add_argument(
        "--candidate-frames",
        type=int,
        default=2,
        help="Consistent frames required before accepting a new live microphone note.",
    )
    parser.add_argument(
        "--startup-frames",
        type=int,
        default=3,
        help="Consistent frames required before accepting the first live microphone note.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="Optional CSV path for saving detected notes and tracking output.",
    )
    return parser.parse_args()


def _resolve_score_path(score_path: Path) -> Path:
    if score_path.is_absolute():
        return score_path
    if score_path.exists():
        return score_path
    example_relative_path = Path(__file__).parent / score_path
    if example_relative_path.exists():
        return example_relative_path
    return score_path


def _create_note_input(args: argparse.Namespace):
    if args.demo:
        print("Demo mode: replaying fake frequencies, no microphone required.")
        print()
        return DemoFrequencyNoteInput(
            frequencies_hz=DEMO_FREQUENCIES,
            window_size=args.window_size,
            interval_seconds=0.55,
            repeat_gap_seconds=args.repeat_gap_seconds,
        )

    microphone = LiveMicrophoneNoteInput(
        window_size=args.window_size,
        repeat_gap_seconds=args.repeat_gap_seconds,
        stable_detection_count=args.candidate_frames,
        startup_stable_detection_count=args.startup_frames,
    )
    try:
        microphone.start()
    except MicrophoneDependencyError as exc:
        print(exc)
        print()
        print("Install dependencies with:")
        print("  python3 -m pip install sounddevice numpy")
        print()
        print("Or run without microphone hardware:")
        print("  PYTHONPATH=src python3 examples/live_score_following_demo.py --demo")
        return None
    except MicrophoneStartError as exc:
        print(exc)
        print()
        print("You can still try demo mode:")
        print("  PYTHONPATH=src python3 examples/live_score_following_demo.py --demo")
        return None

    return microphone


def _open_log_file(log_path: Path | None):
    if log_path is None:
        return None

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handle = log_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        file_handle,
        fieldnames=[
            "timestamp_seconds",
            "detected_note_window",
            "current_measure",
            "current_note_index",
            "confidence_score",
            "tracking_status",
            "page_turn_signal",
            "raw_detected_frequency",
            "raw_detected_note",
            "stabilized_note",
            "raw_note_buffer",
            "candidate_note",
            "candidate_duration",
            "warmup_active",
            "continuous_silence_duration",
            "rejected_detection_count",
            "rejected_startup_glitch_count",
            "rejected_transition_glitch_count",
            "compressed_duplicate_count",
            "octave_correction_count",
            "octave_correction_skipped_reason",
            "last_rejection_reason",
        ],
    )
    writer.writeheader()
    print(f"Logging CSV output to {log_path}")
    print()
    return CsvLogger(file_handle=file_handle, writer=writer)


def _run_loop(engine: StrobatoEngine, note_input, demo_mode: bool, log_file=None) -> None:
    started_at = time.monotonic()
    update_count = 0
    locked_since: float | None = None
    last_status = engine.get_tracking_status()
    last_note_window: list[str] = []

    while True:
        if demo_mode:
            note_input.tick()

        note_window = note_input.get_note_window()
        if note_window and note_window != last_note_window:
            update_count += 1
            result = engine.update_with_notes(note_window)
            now = time.monotonic()

            if result.tracking_status == "locked":
                locked_since = locked_since or now
            else:
                locked_since = None

            transition = ""
            if result.tracking_status != last_status:
                transition = f" ({last_status} -> {result.tracking_status})"
            last_status = result.tracking_status

            input_metrics = note_input.get_metrics()
            elapsed = max(now - started_at, 1.0)
            update_frequency = update_count / elapsed
            lock_duration = (now - locked_since) if locked_since is not None else 0.0

            _print_status(
                note_window=note_window,
                current_measure=result.current_measure,
                current_note_index=result.current_note_index,
                confidence_score=result.confidence_score,
                tracking_status=f"{result.tracking_status}{transition}",
                page_turn_signal=result.page_turn_signal,
                update_frequency=update_frequency,
                lock_duration=lock_duration,
                input_metrics=input_metrics,
            )
            _write_log_row(
                log_file=log_file,
                timestamp_seconds=now - started_at,
                note_window=note_window,
                current_measure=result.current_measure,
                current_note_index=result.current_note_index,
                confidence_score=result.confidence_score,
                tracking_status=result.tracking_status,
                page_turn_signal=result.page_turn_signal,
                input_metrics=input_metrics,
            )
            last_note_window = note_window

        if demo_mode and _demo_finished(note_input, last_note_window):
            print("Demo performance complete.")
            return

        time.sleep(0.15)


def _print_status(
    note_window: list[str],
    current_measure: int | None,
    current_note_index: int | None,
    confidence_score: float,
    tracking_status: str,
    page_turn_signal: bool,
    update_frequency: float,
    lock_duration: float,
    input_metrics: dict,
) -> None:
    print("=== Strobato Live Follow Update ===")
    print(f"Compressed musical note window: {', '.join(note_window)}")
    print("Score position")
    print(f"  current_measure: {current_measure}")
    print(f"  current_note_index: {current_note_index}")
    print(f"  confidence_score: {confidence_score:.2f}")
    print(f"  tracking_status: {tracking_status}")
    print(f"  page_turn_signal: {page_turn_signal}")
    print("Debug metrics")
    print(f"  update_frequency: {update_frequency:.2f} updates/sec")
    print(f"  note_detection_rate: {input_metrics['note_detection_rate']} notes/sec")
    print(f"  raw_detection_rate: {input_metrics['raw_detection_rate']} detections/sec")
    print(f"  tracking_lock_duration: {lock_duration:.2f} sec")
    print(f"  current_note_buffer: {input_metrics['note_buffer']}")
    print(f"  raw_note_buffer: {input_metrics.get('raw_note_buffer')}")
    print(f"  warmup_active: {input_metrics.get('warmup_active')}")
    print(f"  continuous_silence_duration: {input_metrics.get('continuous_silence_duration')} sec")
    print(f"  candidate_note: {input_metrics.get('candidate_note') or '-'}")
    print(f"  candidate_duration: {input_metrics.get('candidate_duration')} sec")
    print("Pitch debug")
    print(f"  raw_detected_frequency: {input_metrics.get('last_raw_frequency')}")
    print(f"  raw_detected_note: {input_metrics.get('last_raw_note')}")
    print(f"  stabilized_note: {input_metrics.get('last_stabilized_note')}")
    print(f"  rejected_detections: {input_metrics.get('rejected_detection_count')}")
    print(f"  rejected_startup_glitches: {input_metrics.get('rejected_startup_glitch_count')}")
    print(
        "  rejected_transition_glitches: "
        f"{input_metrics.get('rejected_transition_glitch_count')}"
    )
    print(f"  compressed_duplicates: {input_metrics.get('compressed_duplicate_count')}")
    print(f"  octave_corrections: {input_metrics.get('octave_correction_count')}")
    print(
        "  octave_correction_skipped_reason: "
        f"{input_metrics.get('last_octave_correction_skipped_reason') or '-'}"
    )
    print(f"  last_rejection_reason: {input_metrics.get('last_rejection_reason') or '-'}")
    print()


def _write_log_row(
    log_file,
    timestamp_seconds: float,
    note_window: list[str],
    current_measure: int | None,
    current_note_index: int | None,
    confidence_score: float,
    tracking_status: str,
    page_turn_signal: bool,
    input_metrics: dict,
) -> None:
    if log_file is None:
        return

    log_file.write_row(
        timestamp_seconds=timestamp_seconds,
        note_window=note_window,
        current_measure=current_measure,
        current_note_index=current_note_index,
        confidence_score=confidence_score,
        tracking_status=tracking_status,
        page_turn_signal=page_turn_signal,
        input_metrics=input_metrics,
    )


def _demo_finished(note_input: DemoFrequencyNoteInput, last_note_window: list[str]) -> bool:
    metrics = note_input.get_metrics()
    return (
        bool(last_note_window)
        and metrics["demo_step"] == metrics["demo_total_steps"]
        and last_note_window == metrics["note_buffer"]
    )


if __name__ == "__main__":
    main()
