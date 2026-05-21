import time

from strobato_sdk.microphone import LiveMicrophoneNoteInput, MicrophoneDependencyError


def main() -> None:
    print("Experimental Strobato live microphone demo")
    print("-------------------------------------------")
    print("This is a simple monophonic prototype, not production piano transcription.")
    print("Play one clear note at a time near your microphone.")
    print("Press Ctrl+C to stop.")
    print()

    microphone = LiveMicrophoneNoteInput()

    try:
        microphone.start()
    except MicrophoneDependencyError as exc:
        print(exc)
        return

    try:
        last_window: list[str] = []
        while True:
            note_window = microphone.get_note_window()
            if note_window and note_window != last_window:
                print("Detected notes:", ", ".join(note_window))
                last_window = note_window
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping microphone demo.")
    finally:
        microphone.stop()


if __name__ == "__main__":
    main()
