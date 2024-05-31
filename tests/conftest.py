from dataclasses import dataclass
from pathlib import Path
import hashlib
import sys
from pytest import fixture
from sqlmodel import Session

# extend the path to include the src directory
sys.path.append(str(Path(Path(__file__).parent.parent / "src").absolute()))

# pylint: disable=wrong-import-position; needed to import the classes from the src directory
from frontend.indexing_interface import IndexingInterface
from backend.whisper_interface import WhisperInterface


@fixture(scope="session")
def example_file() -> Path:
    """Return a Path object to a sample audio file."""
    return Path("tests/assets/240530_1653.wav")


@fixture(scope="session")
def transcribed_file() -> str:
    """Return the expected transcribed text from the example file."""
    return "I think it's in part, there's just config drift and things in there that kind of come along. And there's lots of little updates here that you don't really have any control over. So I propose to build it better."


@fixture(scope="session")
def whisper_interface():
    """Return a WhisperInterface object."""
    return WhisperInterface()


@fixture(scope="session")
def whisper_transcribed(whisper_interface, example_file):
    """Return the transcribed text from the example file using the WhisperInterface object."""
    return whisper_interface.transcribe(example_file).get("text").strip()


@fixture
def db():
    """Return an IndexingInterface object with an in-memory database."""
    return IndexingInterface(conn_str="sqlite://")


@dataclass
class DbObj:
    db_obj: IndexingInterface
    session: Session


@fixture
def session(db):
    """Return a session object."""
    with Session(db.engine) as db_session:
        yield DbObj(db, db_session)


@staticmethod
def get_md5sum(input_string):
    """Return the md5 checksum for the input string."""
    # Step 1: Create an md5 hash object
    md5_hash = hashlib.md5()

    # Step 2: Encode the string to bytes
    encoded_string = input_string.encode("utf-8")

    # Step 3: Update the hash object with the encoded string
    md5_hash.update(encoded_string)

    # Step 4: Get the hexadecimal representation of the checksum
    md5_checksum = md5_hash.hexdigest()

    return md5_checksum
