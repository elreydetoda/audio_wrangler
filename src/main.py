#!/usr/bin/env python3

import logging
from pathlib import Path
import re
from time import monotonic
from argparse import ArgumentParser
from typing import Dict, Iterable, Set
from asyncio import create_task

from sqlmodel import Session, select
from whisper.utils import get_writer
from textual import on
from textual.app import App
from textual.widgets import (
    Header,
    Footer,
    Button,
    Static,
    Label,
    ContentSwitcher,
    DirectoryTree,
    DataTable,
)
from textual.widgets.data_table import DuplicateKey
from textual.containers import (
    ScrollableContainer,
    Grid,
    Container,
    Horizontal,
    VerticalScroll,
    Vertical,
)
from textual.reactive import reactive
from textual.logging import TextualHandler
from httpx import AsyncClient

from models.db_models import FilesMetadata
from backend.whisper_interface import WhisperInterface
from frontend.indexing_interface import IndexingInterface


# Define the pattern
BREAK_PATTERN = re.compile(r"([Ee]-*|)(break|brake)[\W\s]*", re.IGNORECASE)
COMMON_AUDIO_N_VIDEO_FORMATS = {
    # https://github.com/h2non/filetype.py?tab=readme-ov-file#video
    "3gp",
    "mp4",
    "m4v",
    "mkv",
    "webm",
    "mov",
    "avi",
    "wmv",
    "mpg",
    "flv",
    # https://github.com/h2non/filetype.py?tab=readme-ov-file#audio
    "aac",
    "mid",
    "mp3",
    "m4a",
    "ogg",
    "flac",
    "wav",
    "amr",
    "aiff",
}

logging.basicConfig(level="NOTSET", handlers=[TextualHandler()])


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


class AudioDirectoryTree(DirectoryTree):

    def __init__(
        self,
        *args,
        session: Session,
        in_db=True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._session = session
        self._in_db = in_db

    def filter_paths(
        self,
        paths: Iterable[Path],
        only_files=False,
    ) -> Iterable[Path]:

        paths = {
            path
            for path in paths
            if not IndexingInterface.get_index(self._session, path)
        }
        if only_files:
            paths = {path for path in paths if path.is_file()}
        return self.filter_media_files(paths)

    @staticmethod
    def filter_media_files(
        paths: Iterable[Path],
    ) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.suffix.strip(".") in COMMON_AUDIO_N_VIDEO_FORMATS or path.is_dir()
        ]


class AudioWranglerIndexer(Static):

    # not_indexed_file: reactive[Set[Path]] = reactive(set())

    def __init__(
        self,
        *args,
        audio_dir: Path,
        index_obj: IndexingInterface,
        **kwargs,
    ):
        self._audio_dir = audio_dir
        self._index_obj = index_obj
        self._session = Session(self._index_obj.engine)
        super().__init__(*args, **kwargs)

    def compose(self):
        with Grid(id="indexer-grid"):
            with Horizontal(id="indexer-left"):
                yield AudioDirectoryTree(
                    self._audio_dir,
                    session=self._session,
                    id="indexer-directory-tree",
                )
                yield Button("Add All Files", id="add-all-files")
            yield DataTable(id="indexer-table")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(*("File Path", "Indexed"))
        # self.update_table = self.set_interval(
        #     5,
        # )

    @on(AudioDirectoryTree.FileSelected, "#indexer-directory-tree")
    def start_file_processing(self, event: AudioDirectoryTree.FileSelected) -> None:
        dt = self.query_one(DataTable)
        if event.path.is_file():
            file_path_str = str(event.path)
            try:
                self._session.add(
                    FilesMetadata(filename=file_path_str, processed=False)
                )
                self._session.commit()
                dt.add_row(
                    *(file_path_str, "yes"),
                    key=file_path_str,
                )
                logging.debug("File %s added to table", file_path_str)
            except DuplicateKey:
                dt.scroll_visible(file_path_str)
                logging.debug("File %s already in table", file_path_str)

    @on(Button.Pressed, "#add-all-files")
    def add_all_files(self):
        dt = self.query_one(DataTable)
        dt.clear()
        self.on_mount()
        all_files = set(self._audio_dir.glob("**/*"))
        all_files.update(self._audio_dir.glob("./*"))

        files = self.query_one(AudioDirectoryTree).filter_paths(
            all_files,
            only_files=True,
        )
        # files = AudioDirectoryTree.filter_media_files(
        #     all_files,
        #     only_files=True,
        # )
        for filez in files:
            dt.add_row(*(str(filez), "yes"), key=str(filez))
            self._session.add(FilesMetadata(filename=str(filez), processed=False))

        self._session.commit()

        self.query_one("#add-all-files").disabled = True

    # def watch_not_indexed_file(self):
    #     logging.debug("########## REACHED ##########")
    #     fmt_str = "\n".join([str(filez) for filez in self.not_indexed_file])
    #     self.query_one(DataTable).add_row()


class AudioWrangerJobs(Static):
    def __init__(
        self,
        *args,
        index_obj: IndexingInterface,
        api_host: str,
        **kwargs,
    ):
        self._index_obj = index_obj
        self._api_host = api_host
        self._session = Session(self._index_obj.engine)
        super().__init__(*args, **kwargs)

    def compose(self):
        with Horizontal(id="jobs"):
            with Vertical(id="jobs-new"):
                yield DataTable(id="jobs-new-table")
                with Container():
                    yield Button("Start Jobs", id="start-jobs")
            yield DataTable(id="jobs-running-table")

    def on_mount(self):
        new_table = self.query_one("#jobs-new-table", DataTable)
        new_table.add_columns(*("File Path", "Processed"))
        self.check_new_jobs()
        self.set_interval(5, self.check_new_jobs)

        current_jobs_table = self.query_one("#jobs-running-table", DataTable)
        current_jobs_table.add_columns(*("File Name", "State", "Task ID"))
        self.launch_async_task()
        self.set_interval(5, self.launch_async_task)

    def check_new_jobs(self) -> None:
        new_table = self.query_one("#jobs-new-table", DataTable)
        new_jobs = self._session.exec(
            select(FilesMetadata).where(FilesMetadata.processed == False)
        ).all()
        for new_job in new_jobs:
            try:
                new_table.add_row(*(new_job.filename, "no"), key=new_job.filename)
            except DuplicateKey:
                logging.debug("File %s already in table", new_job.filename)

    def launch_async_task(self) -> None:
        create_task(self.check_current_jobs())

    async def check_current_jobs(self) -> None:
        url = f"{self._api_host}/tasks"
        async with AsyncClient() as client:
            # this is tasks in: src/backend/app.py
            results: Dict[
                str,
                Dict[
                    str,
                    str
                    | Dict[
                        str,
                        str | list,
                    ],
                ],
            ] = (await client.get(url)).json()

        current_jobs_table = self.query_one("#jobs-running-table", DataTable)
        current_jobs_table.clear()
        if results:
            # current_jobs_table.add_columns(*("File Name", "State", "Task ID"))
            for k, v in results.items():
                try:
                    current_jobs_table.add_row(*(v["filename"], v["state"], k), key=k)
                except DuplicateKey:
                    logging.debug("Task %s already in table", k)


class AudioWranglerApp(App):

    def __init__(
        self,
        *args,
        api_host: str,
        audio_dir: Path,
        index_obj: IndexingInterface,
        **kwargs,
    ):
        self._api_host = api_host
        self._audio_dir = audio_dir
        self._index_obj = index_obj
        super().__init__(*args, **kwargs)

    BINDINGS = [
        # ("keybinding", "function_name", "description")
        ("d", "toggle_dark_mode", "Toggle dark mode"),
        ("q", "exit", "Exit"),
        # ("a", "add_audiowrangler", "Add"),
        # ("r", "remove_audiowrangler", "Remove"),
        # actual function needs to have a prefix of action_<above_name>
    ]

    CSS_PATH = "frontend/style.tcss"

    def compose(self):
        yield Header()
        yield Footer()
        with Horizontal(id="main"):
            # with Container(id="data-wranglers"):
            with VerticalScroll(id="wranglers"):
                # yield Label(self._api_host)
                # yield Label(str(self._audio_dir))
                # yield AudioWrangler()
                # yield AudioWrangler()
                yield Button(
                    "Index",
                    id="indexer",
                    classes="content-switcher-button",
                )
                yield Button(
                    "Current Jobs",
                    id="current-jobs",
                    classes="content-switcher-button",
                )
                yield Button(
                    "File Metadata",
                    id="metadata",
                    classes="content-switcher-button",
                )
            with ContentSwitcher(id="data-view", initial="indexer"):
                with Horizontal(id="indexer"):
                    yield AudioWranglerIndexer(
                        audio_dir=self._audio_dir,
                        index_obj=self._index_obj,
                    )
                yield AudioWrangerJobs(
                    id="current-jobs",
                    index_obj=self._index_obj,
                    api_host=self._api_host,
                )
                yield Label("Data View: File Metadata", id="metadata")

    def action_toggle_dark_mode(self):
        self.dark = not self.dark

    def action_exit(self):
        self.exit()

    # def action_add_audiowrangler(self):
    #     audiowrangler = AudioWrangler()
    #     conttainer = self.query_one("#wranglers")
    #     conttainer.mount(audiowrangler)
    #     audiowrangler.scroll_visible()

    # def action_remove_audiowrangler(self):
    #     wranglers = self.query(AudioWrangler)
    #     if wranglers:
    #         wranglers.last().remove()
    @on(Button.Pressed, ".content-switcher-button")
    def update_content_switcher(self, event: Button.Pressed) -> None:
        self.query_one(ContentSwitcher).current = event.button.id


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
    index_obj = IndexingInterface()

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
    AudioWranglerApp(
        api_host=args.api_endpoint,
        audio_dir=args.audio_dir,
        index_obj=index_obj,
    ).run()


if __name__ == "__main__":
    main()
