from pathlib import Path

from examples.visual_demo import (
    DemoState,
    _build_replay_windows,
    _candidate_frames,
    _frontend_poll_interval_ms,
)


SCORE_PATH = Path("examples/c_major_longer_test.musicxml")


def test_visual_demo_snapshot_exposes_sdk_status_fields():
    state = DemoState(SCORE_PATH, live_mode=False, latency_mode="balanced")
    snapshot = state.snapshot()

    assert snapshot["latency_mode"] == "balanced"
    assert snapshot["current_measure"] is None
    assert snapshot["current_note_index"] is None
    assert snapshot["confidence_score"] == 0.0
    assert snapshot["page_turn_signal"] is False
    assert snapshot["tracking_status"] == "searching"
    assert snapshot["expected_next_note"] == "C4"
    assert snapshot["current_page"] is None


def test_visual_demo_replay_advances_through_loaded_score():
    state = DemoState(SCORE_PATH, live_mode=False, latency_mode="balanced")

    first_step = state.next_note_window()
    final_step = first_step
    for _ in range(7):
        final_step = state.next_note_window()

    assert first_step["current_measure"] == 1
    assert final_step["current_measure"] == 8
    assert final_step["current_page"] == 4
    assert final_step["tracking_status"] == "locked"


def test_visual_demo_latency_modes_keep_existing_timing_contract():
    assert _frontend_poll_interval_ms("stable") == 2500
    assert _frontend_poll_interval_ms("balanced") == 500
    assert _frontend_poll_interval_ms("fast") == 250
    assert _candidate_frames("stable") == 2
    assert _candidate_frames("balanced") == 2
    assert _candidate_frames("fast") == 1


def test_visual_demo_replay_windows_are_cumulative_note_windows():
    windows = _build_replay_windows(
        [
            {"number": 1, "notes": ["C4"]},
            {"number": 2, "notes": ["D4"]},
            {"number": 3, "notes": ["E4"]},
        ]
    )

    assert windows[0]["notes"] == ["C4"]
    assert windows[1]["notes"] == ["C4", "D4"]
    assert windows[2]["notes"] == ["C4", "D4", "E4"]
