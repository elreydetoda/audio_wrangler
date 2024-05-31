#!/usr/bin/env python3

from pathlib import Path
from itertools import islice
from whisper_interface import WhisperInterface
from indexing_interface import IndexingInterface


def process_transcription(wsp: WhisperInterface, input_file: Path) -> Path:
    transcribed_text = wsp.transcribe(input_file).get("text").strip()
    output_file = Path(input_file.parent / str(input_file.stem + ".txt"))
    output_file.write_text(transcribed_text, encoding="utf-8")
    return output_file


def main():
    all_files = Path("/tmp/").glob("*")
    wsp = WhisperInterface()
    index = IndexingInterface()

    while all_files:
        batch = list(islice(all_files, 10))
        if not batch:
            break

        print(f"Processing batch of {len(batch)} files")
        for file in batch:
            if index.get_index(str(file)):
                continue

            print(f"Processing {file}")
    # input_file = Path("tests/assets/240530_1653.wav")
    # print(input_file)
    # wsp = WhisperInterface()
    # transcription_path = print(process_transcription(wsp, input_file))
    # index = IndexingInterface()
    # index.add_to_index(input_file, 1)


if __name__ == "__main__":
    main()
