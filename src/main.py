#!/usr/bin/env python3

from pathlib import Path
import re
from time import monotonic
from argparse import ArgumentParser

from sqlmodel import Session
from whisper.utils import get_writer
from textual import on
from textual.app import App
from textual.widgets import Header, Footer, Button, Static, Label
from textual.containers import ScrollableContainer
from textual.reactive import reactive

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


class TimeDisplay(Static):

    accumulated_time = 0
    time_elapsed = reactive(0)

    # handler method
    def on_mount(self):
        """handles when class is loaded/rendered"""
        self.update_timer = self.set_interval(
            1 / 60, self.update_time_elapsed, pause=True  # 60 fps
        )

    def update_time_elapsed(self):
        self.time_elapsed = self.accumulated_time + (monotonic() - self.start_time)

    def watch_time_elapsed(self):
        time = self.time_elapsed
        minutes, seconds = divmod(time, 60)
        hours, minutes = divmod(minutes, 60)
        self.update(f"{hours:02,.0f}:{minutes:02.0f}:{seconds:05.2f}")
        # self.update(str(time))

    def start(self):
        """"""
        self.start_time = monotonic()
        self.update_timer.resume()

    def stop(self):
        """"""
        self.accumulated_time = self.time_elapsed
        self.update_timer.pause()

    def reset(self):
        """"""
        self.accumulated_time = 0
        self.time_elapsed = 0


class AudioWrangler(Static):
    # handling messages in textual
    @on(Button.Pressed, "#first")
    def first_pressed_method(self):
        # self.app.exit()
        self.query_one(TimeDisplay).start()

    @on(Button.Pressed, "#second")
    def second_pressed_method(self):
        # self.add_class("hidden")
        # time_display = self.query_one(TimeDisplay)
        # time_display.time_elapsed = 7.3
        self.query_one(TimeDisplay).stop()

    def compose(self):
        yield Button("First", id="first")
        yield Button("Second", id="second")
        yield TimeDisplay("00:00:00.00")
        # yield Button("Third", variant="error", id="stop", classes="hidden")


class AudioWranglerApp(App):

    def __init__(self, *args, api_host: str, audio_dir: Path, **kwargs):
        self._api_host = api_host
        self._audio_dir = audio_dir
        super().__init__(*args, **kwargs)

    BINDINGS = [
        # ("keybinding", "function_name", "description")
        ("d", "toggle_dark_mode", "Toggle dark mode"),
        ("a", "add_audiowrangler", "Add"),
        ("r", "remove_audiowrangler", "Remove"),
        # actual function needs to have a prefix of action_<above_name>
    ]

    CSS_PATH = "frontend/style.tcss"

    def compose(self):
        yield Header()
        yield Footer()
        with ScrollableContainer(id="wranglers"):
            yield Label(self._api_host)
            yield Label(str(self._audio_dir))
            yield AudioWrangler()
            yield AudioWrangler()

    def action_toggle_dark_mode(self):
        self.dark = not self.dark

    def action_add_audiowrangler(self):
        audiowrangler = AudioWrangler()
        conttainer = self.query_one("#wranglers")
        conttainer.mount(audiowrangler)
        audiowrangler.scroll_visible()

    def action_remove_audiowrangler(self):
        wranglers = self.query(AudioWrangler)
        if wranglers:
            wranglers.last().remove()


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "api_endpoint", help="API endpoint for the speech-to-text service"
    )
    parser.add_argument(
        "audio_dir",
        type=Path,
        help="Directory containing the audio files to be processed",
    )
    args = parser.parse_args()
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
    AudioWranglerApp(api_host=args.api_endpoint, audio_dir=args.audio_dir).run()


if __name__ == "__main__":
    main()
