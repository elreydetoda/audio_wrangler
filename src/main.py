#!/usr/bin/env python3

from pathlib import Path
import re

from sqlmodel import Session
from whisper.utils import get_writer
from whisper_interface import WhisperInterface
from indexing_interface import IndexingInterface


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
    input_file = Path("tests/assets/240530_1653.wav")
    print(input_file)
    wsp = WhisperInterface()
    print(process_transcription(wsp, input_file))
    index = IndexingInterface()
    session = Session(index.engine)
    print(index.get_index(session, input_file))
    print(index.bulk_validate(session, [input_file]))
    index.add_to_index(session, input_file, True)
    print(index.bulk_validate(session, [input_file]))
    print(index.get_index(session, input_file))


if __name__ == "__main__":
    main()
