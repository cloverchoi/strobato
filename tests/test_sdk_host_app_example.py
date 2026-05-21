from examples.sdk_host_app_example import (
    format_host_app_update,
    host_app_decision,
    run_host_app_example,
)
from strobato_sdk.models import SyncResult


def test_host_app_example_tracks_to_final_measure():
    updates = run_host_app_example()
    final_result = updates[-1]["result"]
    final_decision = updates[-1]["decision"]

    assert final_result.current_measure == 8
    assert final_result.current_note_index == 7
    assert final_result.tracking_status == "locked"
    assert final_decision["highlight_measure"] == 8


def test_host_app_decision_turns_page_when_sdk_signals_it():
    result = SyncResult(
        current_measure=3,
        current_note_index=2,
        confidence_score=0.82,
        page_turn_signal=True,
        tracking_status="locked",
    )

    decision = host_app_decision(result)

    assert decision["highlight_measure"] == 3
    assert decision["turn_page"] is True
    assert decision["screen_state"] == "following"


def test_host_app_decision_waits_when_confidence_is_low():
    result = SyncResult(
        current_measure=4,
        current_note_index=3,
        confidence_score=0.2,
        page_turn_signal=False,
        tracking_status="lost",
    )

    decision = host_app_decision(result)

    assert decision["highlight_measure"] is None
    assert decision["turn_page"] is False
    assert decision["screen_state"] == "listening for recovery"


def test_host_app_example_formats_clean_output():
    result = SyncResult(
        current_measure=2,
        current_note_index=1,
        confidence_score=0.781,
        page_turn_signal=False,
        tracking_status="locked",
    )
    decision = host_app_decision(result)

    output = format_host_app_update(2, ["C4", "D4"], result, decision)

    assert "Host update 2" in output
    assert "current_measure: 2" in output
    assert "confidence_score: 0.78" in output
    assert "host_highlight_measure: 2" in output
    assert "host_page_action: stay on page" in output
