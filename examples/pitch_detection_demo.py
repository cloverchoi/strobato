"""Tiny pitch helper demo using fake frequency values."""

from strobato_sdk import frequency_to_note_name


def main() -> None:
    fake_frequencies = [440.0, 261.63, 329.63, 392.0, 0.0]

    print("Strobato pitch detection demo")
    print("-----------------------------")

    for frequency in fake_frequencies:
        note_name = frequency_to_note_name(frequency)
        print(f"{frequency:>7.2f} Hz -> {note_name}")


if __name__ == "__main__":
    main()
