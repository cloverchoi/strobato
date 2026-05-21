from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree
from urllib.parse import urlparse

from strobato_sdk import StrobatoEngine, parse_musicxml
from strobato_sdk.microphone import (
    LiveMicrophoneNoteInput,
    MicrophoneDependencyError,
    MicrophoneStartError,
)
from strobato_sdk.pitch import normalize_note_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORE_PATH = ROOT / "examples" / "c_major_longer_test.musicxml"


class DemoState:
    """Keeps the visual demo state separate from the SDK internals."""

    def __init__(
        self,
        score_path: Path,
        live_mode: bool = False,
        latency_mode: str = "stable",
    ) -> None:
        self.score_path = score_path
        self.live_mode = live_mode
        self.latency_mode = latency_mode
        self.frontend_poll_interval_ms = _frontend_poll_interval_ms(latency_mode)
        self.microphone_frame_size = _microphone_frame_size(latency_mode)
        self.candidate_frames = _candidate_frames(latency_mode)
        self.startup_frames = _startup_frames(latency_mode)
        self.measures_per_page = 2
        self.engine = StrobatoEngine(measures_per_page=self.measures_per_page)
        self.engine.load_score(score_path)
        self.score = parse_musicxml(score_path)
        self.measure_notes = _read_measure_display_notes(score_path)
        self.note_windows = _build_replay_windows(self.measure_notes)
        self.note_input: LiveMicrophoneNoteInput | None = None
        self.step_index = -1
        self.last_notes: list[str] = []
        self.last_label = "Ready"
        self.visual_current_measure: int | None = None
        self.visual_current_note_index: int | None = None
        self.visual_confidence_score = 0.0
        self.visual_page_turn_signal = False
        self.visual_tracking_status = "searching"
        self.accepted_advance_reason = "waiting"
        self.rejected_early_advance_count = 0
        if live_mode:
            self.note_input = LiveMicrophoneNoteInput(
                window_size=12,
                frame_size=self.microphone_frame_size,
                stable_detection_count=self.candidate_frames,
                startup_stable_detection_count=self.startup_frames,
                repeat_gap_seconds=0.35,
            )
            self.note_input.start()

    def reset(self) -> dict:
        self.engine.reset()
        self.step_index = -1
        self.last_notes = []
        self.last_label = "Ready"
        self.visual_current_measure = None
        self.visual_current_note_index = None
        self.visual_confidence_score = 0.0
        self.visual_page_turn_signal = False
        self.visual_tracking_status = "searching"
        self.accepted_advance_reason = "reset"
        self.rejected_early_advance_count = 0
        return self.snapshot()

    def next_note_window(self) -> dict:
        if self.live_mode:
            return self.snapshot()
        next_step_index = (self.step_index + 1) % len(self.note_windows)
        if next_step_index == 0:
            self.engine.reset()
        self.step_index = next_step_index
        step = self.note_windows[self.step_index]
        self.last_notes = step["notes"]
        self.last_label = step["label"]
        self.engine.update_with_notes(self.last_notes)
        return self.snapshot()

    def snapshot(self) -> dict:
        if self.live_mode and self.note_input is not None:
            live_notes = self.note_input.get_note_window()
            if live_notes and live_notes != self.last_notes:
                self.last_notes = live_notes
                self.last_label = "Live microphone input"
                result = self.engine.update_with_notes(self.last_notes)
                if self.latency_mode == "balanced":
                    self._apply_balanced_visual_guard(result)
                else:
                    self._accept_engine_result(
                        result.current_measure,
                        result.current_note_index,
                        result.confidence_score,
                        result.page_turn_signal,
                        result.tracking_status,
                        "engine_update",
                    )

        return {
            "score": {
                "measures": [
                    {
                        "number": measure["number"],
                        "notes": measure["notes"],
                    }
                    for measure in self.measure_notes
                ]
            },
            "last_label": self.last_label,
            "last_notes": self.last_notes,
            "current_measure": self._current_measure_for_display(),
            "current_note_index": self._current_note_index_for_display(),
            "confidence_score": self._confidence_for_display(),
            "page_turn_signal": self._page_turn_for_display(),
            "tracking_status": self._tracking_status_for_display(),
            "current_page": self._current_page_for_display(),
            "next_step": (self.step_index + 2)
            if self.step_index + 1 < len(self.note_windows)
            else 1,
            "replay_step": self.step_index + 1 if self.step_index >= 0 else 0,
            "total_steps": len(self.note_windows),
            "live_mode": self.live_mode,
            "latency_mode": self.latency_mode,
            "frontend_poll_interval_ms": self.frontend_poll_interval_ms,
            "estimated_update_latency_ms": self._estimated_update_latency_ms(),
            "expected_next_note": self._expected_next_note(),
            "accepted_advance_reason": self.accepted_advance_reason,
            "rejected_early_advance_count": self.rejected_early_advance_count,
            "score_name": self.score_path.name,
        }

    def _apply_balanced_visual_guard(self, result) -> None:
        candidate_measure = result.current_measure
        last_note = self.last_notes[-1] if self.last_notes else ""
        expected_next_note = self._expected_next_note()

        if candidate_measure is None:
            self.accepted_advance_reason = "no_candidate_measure"
            return

        if self.visual_current_measure is None:
            expected_start_note = self._first_note_for_measure(candidate_measure)
            if _notes_match(last_note, expected_start_note):
                self._accept_engine_result(
                    result.current_measure,
                    result.current_note_index,
                    result.confidence_score,
                    result.page_turn_signal,
                    result.tracking_status,
                    "matched_start_note",
                )
            else:
                self._reject_early_advance("startup_note_mismatch")
            return

        if candidate_measure == self.visual_current_measure:
            self._accept_engine_result(
                result.current_measure,
                result.current_note_index,
                result.confidence_score,
                False,
                result.tracking_status,
                "same_measure_update",
            )
            return

        if candidate_measure <= self.visual_current_measure:
            self.accepted_advance_reason = "held_previous_measure"
            return

        if candidate_measure > self.visual_current_measure + 1:
            self._reject_early_advance("blocked_multi_measure_skip")
            return

        if result.tracking_status == "lost":
            self._reject_early_advance("tracker_lost")
            return

        if not _notes_match(last_note, expected_next_note):
            self._reject_early_advance("expected_next_note_mismatch")
            return

        self._accept_engine_result(
            result.current_measure,
            result.current_note_index,
            result.confidence_score,
            result.page_turn_signal,
            result.tracking_status,
            "matched_expected_next_note",
        )

    def _accept_engine_result(
        self,
        current_measure: int | None,
        current_note_index: int | None,
        confidence_score: float,
        page_turn_signal: bool,
        tracking_status: str,
        reason: str,
    ) -> None:
        self.visual_current_measure = current_measure
        self.visual_current_note_index = current_note_index
        self.visual_confidence_score = confidence_score
        self.visual_page_turn_signal = page_turn_signal
        self.visual_tracking_status = tracking_status
        self.accepted_advance_reason = reason

    def _reject_early_advance(self, reason: str) -> None:
        self.rejected_early_advance_count += 1
        self.visual_confidence_score = max(
            self.visual_confidence_score,
            self.engine.get_confidence(),
        )
        if self.visual_tracking_status == "searching":
            self.visual_tracking_status = self.engine.get_tracking_status()
        self.accepted_advance_reason = reason

    def _current_measure_for_display(self) -> int | None:
        if self.live_mode and self.latency_mode == "balanced":
            return self.visual_current_measure
        return self.engine.get_current_measure()

    def _current_note_index_for_display(self) -> int | None:
        if self.live_mode and self.latency_mode == "balanced":
            return self.visual_current_note_index
        return self.engine.get_current_note_index()

    def _confidence_for_display(self) -> float:
        if self.live_mode and self.latency_mode == "balanced":
            return self.visual_confidence_score
        return self.engine.get_confidence()

    def _page_turn_for_display(self) -> bool:
        if self.live_mode and self.latency_mode == "balanced":
            return self.visual_page_turn_signal
        return self.engine.should_turn_page()

    def _tracking_status_for_display(self) -> str:
        if self.live_mode and self.latency_mode == "balanced":
            return self.visual_tracking_status
        return self.engine.get_tracking_status()

    def _current_page_for_display(self) -> int | None:
        current_measure = self._current_measure_for_display()
        if current_measure is None:
            return None
        return ((current_measure - 1) // self.measures_per_page) + 1

    def _expected_next_note(self) -> str:
        if self.visual_current_measure is None:
            return self._first_note_for_measure(1)
        return self._first_note_for_measure(self.visual_current_measure + 1)

    def _first_note_for_measure(self, measure_number: int | None) -> str:
        if measure_number is None:
            return ""
        for measure in self.measure_notes:
            if measure["number"] == measure_number and measure["notes"]:
                return measure["notes"][0]
        return ""

    def _estimated_update_latency_ms(self) -> int:
        audio_frame_ms = 0
        if self.live_mode and self.note_input is not None:
            audio_frame_ms = round(
                (self.note_input.frame_size / self.note_input.sample_rate) * 1000
            )
        return int(audio_frame_ms + self.frontend_poll_interval_ms)


STATE: DemoState | None = None


class DemoRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(INDEX_HTML)
            return
        if path == "/api/state":
            self._send_json(_state().snapshot())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/next":
            self._send_json(_state().next_note_window())
            return
        if path == "/api/reset":
            self._send_json(_state().reset())
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, body: dict) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _state() -> DemoState:
    if STATE is None:
        raise RuntimeError("Demo state has not been initialized.")
    return STATE


def _resolve_score_path(score_path: Path) -> Path:
    if score_path.is_absolute():
        return score_path
    if score_path.exists():
        return score_path.resolve()
    return (ROOT / score_path).resolve()


def _read_measure_display_notes(score_path: Path) -> list[dict]:
    tree = ElementTree.parse(score_path)
    root = tree.getroot()
    measures = []
    for fallback_number, measure_element in enumerate(
        root.findall(".//{*}measure"), start=1
    ):
        number_text = measure_element.get("number")
        number = int(number_text) if number_text and number_text.isdigit() else fallback_number
        notes = []
        for note_element in measure_element.findall("{*}note"):
            if note_element.find("{*}rest") is not None:
                continue
            pitch_element = note_element.find("{*}pitch")
            if pitch_element is None:
                continue
            step = _element_text(pitch_element, "step")
            octave = _element_text(pitch_element, "octave")
            alter = _element_text(pitch_element, "alter")
            if step is None:
                continue
            accidental = {"1": "#", "-1": "b"}.get(alter or "", "")
            notes.append(f"{step.upper()}{accidental}{octave or ''}")
        measures.append({"number": number, "notes": notes})
    return measures


def _element_text(parent: ElementTree.Element, name: str) -> str | None:
    child = parent.find(f"{{*}}{name}")
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _build_replay_windows(measures: list[dict]) -> list[dict]:
    windows = []
    running_notes: list[str] = []
    for measure in measures:
        running_notes.extend(measure["notes"])
        note_label = ", ".join(measure["notes"]) if measure["notes"] else "rest"
        windows.append(
            {
                "label": f"Replay through measure {measure['number']}: {note_label}",
                "notes": list(running_notes),
            }
        )
    return windows


def _frontend_poll_interval_ms(latency_mode: str) -> int:
    if latency_mode == "fast":
        return 250
    if latency_mode == "balanced":
        return 500
    return 2500


def _microphone_frame_size(latency_mode: str) -> int:
    if latency_mode in {"balanced", "fast"}:
        return 2048
    return 4096


def _candidate_frames(latency_mode: str) -> int:
    if latency_mode == "fast":
        return 1
    return 2


def _startup_frames(latency_mode: str) -> int:
    if latency_mode == "fast":
        return 2
    return 3


def _notes_match(played_note: str, expected_note: str) -> bool:
    return normalize_note_name(played_note, ignore_octave=False) == normalize_note_name(
        expected_note,
        ignore_octave=False,
    )


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Host Sheet Music App</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #202326;
      --muted: #68727a;
      --line: #d8dee3;
      --paper: #f3f5f7;
      --surface: #ffffff;
      --accent: #1f7a5c;
      --accent-soft: #e4f3ec;
      --turn: #b94f12;
      --staff: #c9d0d6;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      width: min(1160px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0;
    }

    .app-shell {
      min-height: calc(100vh - 48px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }

    .app-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      border-bottom: 1px solid var(--line);
      padding: 14px 18px;
      background: #fbfcfd;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .app-mark {
      width: 32px;
      height: 32px;
      border-radius: 6px;
      border: 1px solid #bbc5cd;
      background: linear-gradient(180deg, #ffffff, #e8edf1);
      display: grid;
      place-items: center;
      font-weight: 800;
    }

    .app-title {
      font-size: 18px;
      font-weight: 760;
      line-height: 1.2;
    }

    .piece-title {
      margin-top: 2px;
      color: var(--muted);
      font-size: 13px;
    }

    h1 {
      margin: 0 0 6px;
      font-size: 30px;
      line-height: 1.1;
      letter-spacing: 0;
    }

    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }

    .live-indicator {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 30px;
      border: 1px solid #bad8ca;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #19543f;
      padding: 0 12px;
      font-size: 13px;
      font-weight: 760;
      white-space: nowrap;
    }

    .live-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
    }

    .content {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 18px;
      padding: 18px;
    }

    .viewer {
      min-height: 520px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(#ffffff, #ffffff) padding-box,
        linear-gradient(180deg, #ffffff, #edf1f4) border-box;
      padding: 22px;
    }

    .viewer-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 22px;
    }

    .viewer-title {
      font-size: 20px;
      font-weight: 780;
    }

    .viewer-meta {
      color: var(--muted);
      font-size: 13px;
      margin-top: 3px;
    }

    .replay-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 28px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #ffffff;
      color: var(--muted);
      padding: 0 10px;
      font-size: 12px;
      font-weight: 760;
      margin-top: 10px;
    }

    .replay-pill.running {
      border-color: #bad8ca;
      background: var(--accent-soft);
      color: #19543f;
    }

    .controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    button {
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
      font-weight: 650;
      padding: 0 14px;
      cursor: pointer;
    }

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #ffffff;
    }

    .debug-panel {
      align-self: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      padding: 14px;
    }

    .debug-title {
      font-size: 13px;
      font-weight: 760;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
      margin-bottom: 10px;
    }

    .status-row {
      display: grid;
      gap: 8px;
      margin-bottom: 14px;
    }

    .status {
      min-height: 70px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      padding: 12px;
    }

    .label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
    }

    .value {
      margin-top: 6px;
      font-size: 18px;
      font-weight: 750;
      line-height: 1.1;
    }

    .score {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin: 0;
    }

    .measure {
      min-height: 280px;
      border: 2px solid var(--line);
      border-radius: 8px;
      background:
        repeating-linear-gradient(
          to bottom,
          transparent 0,
          transparent 24px,
          var(--staff) 25px,
          transparent 26px,
          transparent 38px
        ),
        var(--surface);
      padding: 18px;
      transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
    }

    .measure.active {
      border-color: var(--accent);
      background:
        repeating-linear-gradient(
          to bottom,
          rgba(31, 122, 92, 0.03) 0,
          rgba(31, 122, 92, 0.03) 24px,
          var(--staff) 25px,
          rgba(31, 122, 92, 0.03) 26px,
          rgba(31, 122, 92, 0.03) 38px
        ),
        var(--accent-soft);
      transform: translateY(-2px);
      animation: pulseMeasure 700ms ease;
    }

    @keyframes pulseMeasure {
      0% {
        box-shadow: 0 0 0 0 rgba(31, 122, 92, 0.0);
      }
      45% {
        box-shadow: 0 0 0 6px rgba(31, 122, 92, 0.16);
      }
      100% {
        box-shadow: 0 0 0 0 rgba(31, 122, 92, 0.0);
      }
    }

    .measure-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-weight: 750;
      margin-bottom: 18px;
    }

    .badge {
      border-radius: 999px;
      background: #edf1f4;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      padding: 4px 8px;
    }

    .measure.active .badge {
      background: var(--accent);
      color: #ffffff;
    }

    .notes {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 62px;
    }

    .note {
      min-width: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      padding: 8px 10px;
      text-align: center;
      font-weight: 700;
    }

    .feed {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      padding: 12px;
    }

    .feed-notes {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      min-height: 36px;
    }

    .powered {
      padding-top: 14px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .turn {
      color: var(--turn);
    }

    .reader-status-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
    }

    .state-pill,
    .page-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 32px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #ffffff;
      color: var(--muted);
      padding: 0 12px;
      font-size: 13px;
      font-weight: 780;
      white-space: nowrap;
    }

    .state-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #8a949c;
    }

    .state-pill.listening .state-dot {
      background: #2f79b8;
    }

    .state-pill.locked {
      border-color: #bad8ca;
      background: var(--accent-soft);
      color: #19543f;
    }

    .state-pill.locked .state-dot {
      background: var(--accent);
    }

    .state-pill.uncertain {
      border-color: #e1c779;
      background: #fff7db;
      color: #7b5a08;
    }

    .state-pill.uncertain .state-dot {
      background: #c48b10;
    }

    .state-pill.lost {
      border-color: #e2b3a3;
      background: #fff0ea;
      color: #8c351a;
    }

    .state-pill.lost .state-dot {
      background: #b94f12;
    }

    .viewer {
      position: relative;
      background: #e7ebef;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
    }

    .content {
      grid-template-columns: minmax(0, 1fr) 320px;
    }

    .score {
      position: relative;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid #cdd4da;
      border-radius: 8px;
      background: #dfe5e9;
      padding: 18px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
    }

    .measure {
      position: relative;
      min-height: 230px;
      border-width: 1px;
      background:
        linear-gradient(90deg, transparent calc(100% - 2px), #8f989f calc(100% - 2px), #8f989f 100%),
        repeating-linear-gradient(
          to bottom,
          transparent 0,
          transparent 27px,
          var(--staff) 28px,
          transparent 29px,
          transparent 39px
        ),
        #fffdfa;
      box-shadow: 0 10px 22px rgba(33, 43, 52, 0.08);
    }

    .measure.active {
      box-shadow: 0 12px 28px rgba(31, 122, 92, 0.22);
      outline: 3px solid rgba(31, 122, 92, 0.22);
      outline-offset: 2px;
    }

    .page-change-indicator {
      position: absolute;
      top: 82px;
      right: 30px;
      z-index: 2;
      border: 1px solid #d8c08b;
      border-radius: 999px;
      background: #fff8df;
      color: #6f4f05;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 800;
      opacity: 0;
      transform: translateY(-8px);
      transition: opacity 220ms ease, transform 220ms ease;
      pointer-events: none;
    }

    .page-change-indicator.show {
      opacity: 1;
      transform: translateY(0);
    }

    .debug-panel {
      position: sticky;
      top: 18px;
      background: #f8fafb;
    }

    .debug-title {
      color: var(--ink);
      font-size: 14px;
      text-transform: none;
    }

    .state-summary {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 12px;
      margin-bottom: 12px;
    }

    .state-summary p {
      margin-top: 8px;
      font-size: 12px;
    }

    .status {
      min-height: 64px;
    }

    .value {
      font-size: 16px;
      word-break: break-word;
    }

    @media (max-width: 900px) {
      .content {
        grid-template-columns: 1fr;
      }

      .app-header,
      .viewer-toolbar {
        flex-direction: column;
        align-items: stretch;
      }

      .controls {
        justify-content: flex-start;
      }

      .score {
        grid-template-columns: 1fr;
      }

      .measure {
        min-height: 190px;
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="app-shell">
      <header class="app-header">
        <div class="brand">
          <div class="app-mark">H</div>
          <div>
            <div class="app-title">Host Sheet Music App</div>
            <div class="piece-title" id="piece-title">Loaded MusicXML score</div>
          </div>
        </div>
        <div class="live-indicator"><span class="live-dot"></span>Live Follow: On</div>
      </header>

      <div class="content">
        <section class="viewer" aria-label="Sheet music viewer">
          <div class="viewer-toolbar">
            <div>
              <div class="viewer-title">Sheet Music Viewer</div>
              <div class="viewer-meta">Live-following layer embedded in the host reader</div>
              <div class="replay-pill" id="replay-status">Replay: starting</div>
            </div>
            <div class="controls">
              <button class="primary" id="replay-button">Pause Replay</button>
              <button id="next-button">Next replay note window</button>
              <button id="reset-button">Reset</button>
            </div>
          </div>

          <div class="reader-status-bar" aria-label="Reader tracking state">
            <div class="state-pill listening" id="ai-state-indicator">
              <span class="state-dot"></span>
              <span id="ai-state-text">Listening</span>
            </div>
            <div class="page-chip" id="current-page-chip">Page -</div>
          </div>

          <div class="page-change-indicator" id="page-change-indicator">Page changed</div>
          <section class="score" id="score" aria-label="Score measures"></section>
        </section>

        <aside class="debug-panel" aria-label="AI tracking status">
          <div class="debug-title">AI Tracking Status</div>

          <div class="state-summary">
            <div class="state-pill listening" id="panel-state-indicator">
              <span class="state-dot"></span>
              <span id="panel-state-text">Listening</span>
            </div>
            <p>Strobato reads the incoming notes and tells the host app where the musician appears to be in the score.</p>
          </div>

          <section class="status-row" aria-label="SDK output">
            <div class="status">
              <div class="label">Current measure</div>
              <div class="value" id="current-measure">-</div>
            </div>
            <div class="status">
              <div class="label">Current note index</div>
              <div class="value" id="current-note-index">-</div>
            </div>
            <div class="status">
              <div class="label">Confidence score</div>
              <div class="value" id="confidence-score">0.00</div>
            </div>
            <div class="status">
              <div class="label">Page turn signal</div>
              <div class="value" id="page-turn-signal">false</div>
            </div>
            <div class="status">
              <div class="label">Tracking status</div>
              <div class="value" id="tracking-status">searching</div>
            </div>
            <div class="status">
              <div class="label">Replay step</div>
              <div class="value" id="replay-step">0 / 0</div>
            </div>
            <div class="status">
              <div class="label">Latency mode</div>
              <div class="value" id="latency-mode">stable</div>
            </div>
            <div class="status">
              <div class="label">Estimated update latency</div>
              <div class="value" id="estimated-latency">-</div>
            </div>
            <div class="status">
              <div class="label">Expected next note</div>
              <div class="value" id="expected-next-note">-</div>
            </div>
            <div class="status">
              <div class="label">Advance reason</div>
              <div class="value" id="advance-reason">waiting</div>
            </div>
            <div class="status">
              <div class="label">Rejected early advances</div>
              <div class="value" id="rejected-early-advances">0</div>
            </div>
          </section>

          <section class="feed" aria-label="Simulated note input">
            <div class="label">Compressed note window</div>
            <div class="value" id="window-label">Ready</div>
            <div class="feed-notes" id="last-notes"></div>
          </section>

          <div class="powered">Powered by Strobato SDK</div>
        </aside>
      </div>
    </div>
  </main>

  <script>
    const scoreEl = document.querySelector("#score");
    const pieceTitleEl = document.querySelector("#piece-title");
    const currentMeasureEl = document.querySelector("#current-measure");
    const currentNoteIndexEl = document.querySelector("#current-note-index");
    const confidenceEl = document.querySelector("#confidence-score");
    const pageTurnEl = document.querySelector("#page-turn-signal");
    const trackingStatusEl = document.querySelector("#tracking-status");
    const aiStateIndicatorEl = document.querySelector("#ai-state-indicator");
    const aiStateTextEl = document.querySelector("#ai-state-text");
    const panelStateIndicatorEl = document.querySelector("#panel-state-indicator");
    const panelStateTextEl = document.querySelector("#panel-state-text");
    const currentPageChipEl = document.querySelector("#current-page-chip");
    const pageChangeIndicatorEl = document.querySelector("#page-change-indicator");
    const replayStatusEl = document.querySelector("#replay-status");
    const replayStepEl = document.querySelector("#replay-step");
    const latencyModeEl = document.querySelector("#latency-mode");
    const estimatedLatencyEl = document.querySelector("#estimated-latency");
    const expectedNextNoteEl = document.querySelector("#expected-next-note");
    const advanceReasonEl = document.querySelector("#advance-reason");
    const rejectedEarlyAdvancesEl = document.querySelector("#rejected-early-advances");
    const windowLabelEl = document.querySelector("#window-label");
    const notesEl = document.querySelector("#last-notes");
    const replayButton = document.querySelector("#replay-button");
    const nextButton = document.querySelector("#next-button");
    const resetButton = document.querySelector("#reset-button");
    const REPLAY_INTERVAL_MS = 1100;
    let replayRunning = true;
    let replayTimer = null;
    let pollTimer = null;
    let activePollIntervalMs = null;
    let latestState = null;
    let lastRenderedPage = null;
    let pageChangeTimer = null;

    async function fetchState() {
      try {
        const response = await fetch("/api/state");
        render(await response.json());
      } catch (error) {
        console.error("Strobato visual demo state update failed", error);
        setReplayRunning(false);
      }
    }

    async function postAction(path) {
      try {
        const response = await fetch(path, { method: "POST" });
        render(await response.json());
      } catch (error) {
        console.error("Strobato visual demo replay update failed", error);
        setReplayRunning(false);
      }
    }

    function setReplayRunning(nextValue) {
      replayRunning = nextValue;
      if (replayRunning && !latestState?.live_mode) {
        replayButton.textContent = "Pause Replay";
        startReplayLoop();
      } else {
        replayButton.textContent = latestState?.live_mode ? "Live Mode" : "Start Replay";
        stopReplayLoop();
      }
      updateReplayStatus();
    }

    function startReplayLoop() {
      stopReplayLoop();
      replayTimer = window.setInterval(() => {
        if (replayRunning && !latestState?.live_mode) {
          postAction("/api/next");
        }
      }, REPLAY_INTERVAL_MS);
    }

    function stopReplayLoop() {
      if (replayTimer !== null) {
        window.clearInterval(replayTimer);
        replayTimer = null;
      }
    }

    function startPolling(intervalMs) {
      if (pollTimer !== null && activePollIntervalMs === intervalMs) {
        return;
      }
      if (pollTimer !== null) {
        window.clearInterval(pollTimer);
      }
      activePollIntervalMs = intervalMs;
      pollTimer = window.setInterval(fetchState, intervalMs);
      console.log(`Strobato visual polling every ${intervalMs}ms`);
    }

    function updateReplayStatus() {
      const isLive = Boolean(latestState?.live_mode);
      const statusText = isLive
        ? "Live microphone mode"
        : `replay_running: ${String(replayRunning)}`;
      replayStatusEl.textContent = statusText;
      replayStatusEl.classList.toggle("running", replayRunning || isLive);
    }

    function displayTrackingState(state) {
      if (state.tracking_status === "locked") {
        return "locked";
      }
      if (state.tracking_status === "uncertain") {
        return "uncertain";
      }
      if (state.tracking_status === "lost") {
        return "lost";
      }
      return "listening";
    }

    function updateStateIndicator(element, textElement, displayState) {
      element.classList.remove("listening", "locked", "uncertain", "lost");
      element.classList.add(displayState);
      textElement.textContent = displayState.charAt(0).toUpperCase() + displayState.slice(1);
    }

    function updatePageIndicator(state) {
      const currentPage = state.current_page ?? "-";
      currentPageChipEl.textContent = `Page ${currentPage}`;

      if (state.current_page && lastRenderedPage !== null && state.current_page !== lastRenderedPage) {
        showPageChange(`Page ${state.current_page}`);
      } else if (state.page_turn_signal && state.current_page) {
        showPageChange(`Page ${state.current_page}`);
      }

      if (state.current_page) {
        lastRenderedPage = state.current_page;
      }
    }

    function showPageChange(label) {
      pageChangeIndicatorEl.textContent = `${label} ready`;
      pageChangeIndicatorEl.classList.add("show");
      if (pageChangeTimer !== null) {
        window.clearTimeout(pageChangeTimer);
      }
      pageChangeTimer = window.setTimeout(() => {
        pageChangeIndicatorEl.classList.remove("show");
      }, 900);
    }

    function render(state) {
      latestState = state;
      const trackingDisplayState = displayTrackingState(state);
      currentMeasureEl.textContent = state.current_measure ?? "-";
      pieceTitleEl.textContent = state.score_name;
      currentNoteIndexEl.textContent = state.current_note_index ?? "-";
      confidenceEl.textContent = Number(state.confidence_score).toFixed(2);
      pageTurnEl.textContent = String(state.page_turn_signal);
      trackingStatusEl.textContent = state.tracking_status;
      replayStepEl.textContent = `${state.replay_step} / ${state.total_steps}`;
      latencyModeEl.textContent = state.latency_mode;
      estimatedLatencyEl.textContent = `${state.estimated_update_latency_ms}ms`;
      expectedNextNoteEl.textContent = state.expected_next_note || "-";
      advanceReasonEl.textContent = state.accepted_advance_reason;
      rejectedEarlyAdvancesEl.textContent = state.rejected_early_advance_count;
      pageTurnEl.classList.toggle("turn", state.page_turn_signal);
      updateStateIndicator(aiStateIndicatorEl, aiStateTextEl, trackingDisplayState);
      updateStateIndicator(panelStateIndicatorEl, panelStateTextEl, trackingDisplayState);
      updatePageIndicator(state);
      windowLabelEl.textContent = state.last_label;
      nextButton.disabled = state.live_mode;
      replayButton.disabled = state.live_mode;
      nextButton.textContent = state.live_mode ? "Live microphone mode" : "Next replay note window";
      updateReplayStatus();
      startPolling(state.frontend_poll_interval_ms);

      scoreEl.innerHTML = "";
      state.score.measures.forEach((measure) => {
        const measureEl = document.createElement("article");
        measureEl.className = "measure";
        if (measure.number === state.current_measure) {
          measureEl.classList.add("active");
        }

        const notes = measure.notes
          .map((note) => `<span class="note">${note}</span>`)
          .join("");

        measureEl.innerHTML = `
          <div class="measure-title">
            <span>Measure ${measure.number}</span>
            <span class="badge">${measure.number === state.current_measure ? "Detected" : "Score"}</span>
          </div>
          <div class="notes">${notes}</div>
        `;
        scoreEl.appendChild(measureEl);
      });

      notesEl.innerHTML = "";
      if (state.last_notes.length === 0) {
        notesEl.innerHTML = '<span class="note">waiting</span>';
      } else {
        state.last_notes.forEach((note) => {
          const noteEl = document.createElement("span");
          noteEl.className = "note";
          noteEl.textContent = note;
          notesEl.appendChild(noteEl);
        });
      }
    }

    nextButton.addEventListener("click", () => {
      setReplayRunning(false);
      postAction("/api/next");
    });
    replayButton.addEventListener("click", () => setReplayRunning(!replayRunning));
    resetButton.addEventListener("click", async () => {
      await postAction("/api/reset");
      setReplayRunning(true);
      postAction("/api/next");
    });

    fetchState().then(() => {
      if (!latestState?.live_mode) {
        console.log("Strobato visual replay started");
        postAction("/api/next");
        startReplayLoop();
      }
    });
  </script>
</body>
</html>
"""


def main() -> None:
    global STATE
    args = _parse_args()
    score_path = _resolve_score_path(args.score)
    try:
        STATE = DemoState(
            score_path=score_path,
            live_mode=args.live,
            latency_mode=args.latency_mode,
        )
    except MicrophoneDependencyError as exc:
        print(exc)
        print("Install dependencies with:")
        print("  python3 -m pip install sounddevice numpy")
        return
    except MicrophoneStartError as exc:
        print(exc)
        return

    server = ThreadingHTTPServer(("127.0.0.1", args.port), DemoRequestHandler)
    print(f"Host Sheet Music App visual demo running at http://127.0.0.1:{args.port}")
    print(f"Score: {score_path}")
    print(f"Input mode: {'live microphone' if args.live else 'replay'}")
    print(f"Latency mode: {args.latency_mode}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    finally:
        if STATE.note_input is not None:
            STATE.note_input.stop()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visual host-app demo powered by the Strobato SDK."
    )
    parser.add_argument(
        "--score",
        type=Path,
        default=DEFAULT_SCORE_PATH,
        help="MusicXML score to display and follow.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use experimental live microphone input instead of replay mode.",
    )
    parser.add_argument(
        "--latency-mode",
        choices=("stable", "balanced", "fast"),
        default="stable",
        help="Use stable, balanced, or fast live demo timing.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local web server port.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
