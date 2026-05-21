"""MusicXML parsing for the first MVP.

This parser intentionally extracts only what the simulated score follower needs:
measure numbers, pitch names, and rough MusicXML duration values. It skips
rests, voices, dynamics, layout, and every other detail until the MVP proves
useful.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from strobato_sdk.models import Measure, NoteEvent, Score

_ALTER_TO_SYMBOL = {
    -2: "bb",
    -1: "b",
    0: "",
    1: "#",
    2: "##",
}


def parse_musicxml(path: str | Path) -> Score:
    tree = ElementTree.parse(path)
    root = tree.getroot()

    measures: list[Measure] = []
    for fallback_number, measure_element in enumerate(
        root.findall(".//{*}measure"), start=1
    ):
        number = _parse_measure_number(
            measure_element.get("number"),
            fallback=fallback_number,
        )
        notes = tuple(_parse_notes(measure_element, number))
        measures.append(Measure(number=number, notes=notes))

    return Score(measures=tuple(measures))


def _parse_notes(measure_element: ElementTree.Element, measure_number: int) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for note_element in measure_element.findall("{*}note"):
        if note_element.find("{*}rest") is not None:
            continue

        pitch_element = note_element.find("{*}pitch")
        if pitch_element is None:
            continue

        step = _element_text(pitch_element, "step")
        alter_text = _element_text(pitch_element, "alter")
        if not step:
            continue

        alter = int(alter_text) if alter_text else 0
        pitch = f"{step.upper()}{_ALTER_TO_SYMBOL.get(alter, '')}"
        duration = _parse_duration(_element_text(note_element, "duration"))
        notes.append(
            NoteEvent(
                pitch=pitch,
                measure_number=measure_number,
                duration=duration,
            )
        )

    return notes


def _element_text(parent: ElementTree.Element, name: str) -> str | None:
    child = parent.find(f"{{*}}{name}")
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _parse_measure_number(value: str | None, fallback: int) -> int:
    if value is None:
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _parse_duration(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
