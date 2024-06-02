#!/usr/bin/env python3

from pathlib import Path
import re

from sqlmodel import Session
from whisper.utils import get_writer
from textual import on
from textual.app import App
from textual.widgets import Header, Footer, Button, Static
from textual.containers import ScrollableContainer

from models.db_models import FilesMetadata
from backend.whisper_interface import WhisperInterface
from frontend.indexing_interface import IndexingInterface


# Define the pattern
BREAK_PATTERN = re.compile(r"([Ee]-*|)(break|brake)[\W\s]*", re.IGNORECASE)


def modify_text_output(file_written: Path) -> None:
    minified_lines = " ".join(file_written.read_text().split("\n"))
    file_written.write_text(BREAK_PATTERN.sub("\n", minified_lines))
    return file_written


def process_transcription(wsp: WhisperInterface, input_file: Path) -> Path:
    output_formats = {"txt", "vtt"}  # or "vtt", "tsv", "json", or "all"

    transcribed_text = wsp.transcribe(input_file)

    for output_format in output_formats:
        writer = get_writer(output_format, str(input_file.parent))
        writer(transcribed_text, str(input_file))

    return modify_text_output(input_file.with_suffix(".txt"))


class AudioWrangler(Static):
    # handling messages in textual
    @on(Button.Pressed, "#first")
    def first_pressed_method(self):
        self.app.exit()

    @on(Button.Pressed, "#second")
    def second_pressed_method(self):
        self.add_class("hidden")

    def compose(self):
        yield Button("First", id="first")
        yield Button("Second", id="second")
        # yield Button("Third", variant="error", id="stop", classes="hidden")


class AudioWranglerApp(App):
    BINDINGS = [
        # ("keybinding", "function_name", "description")
        # ("d","toggle_dark_mode", "Toggle dark mode")
    ]

    CSS_PATH = "frontend/style.tcss"

    def compose(self):
        yield Header()
        yield Footer()
        with ScrollableContainer(id="wranglers"):
            yield AudioWrangler()
            yield AudioWrangler()


def main():
    # all_files = Path("/tmp/").glob("*")
    # wsp = WhisperInterface()
    # index = IndexingInterface()

    # while all_files:
    #     batch = list(islice(all_files, 10))
    #     if not batch:
    #         break

    #     print(f"Processing batch of {len(batch)} files")
    #     for file in batch:
    #         if index.get_index(str(file)):
    #             continue

    #         print(f"Processing {file}")
    # input_file = Path("tests/assets/240530_1653.wav")
    # print(input_file)
    # wsp = WhisperInterface()
    # print(process_transcription(wsp, input_file))
    # index = IndexingInterface()
    # session = Session(index.engine)
    # session.add(FilesMetadata(filename=str(input_file), processed=True))
    # session.commit()
    # print(index.bulk_validate(session, [input_file]))
    # print(index.get_index(session, input_file))
    AudioWranglerApp().run()


if __name__ == "__main__":
    main()
