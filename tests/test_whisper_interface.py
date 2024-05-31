from conftest import get_md5sum


def test_whisper_interface(whisper_interface, whisper_transcribed, transcribed_file):
    assert whisper_interface._device in ["cpu", "cuda"]
    assert whisper_interface._model is not None
    assert whisper_transcribed == transcribed_file


def test_multiple_transcriptions(whisper_interface, example_file):
    """Get the md5sum for the transcribed text from each of the transcriptions."""
    multiple_files = []
    for _ in range(3):
        multiple_files.append(
            get_md5sum(whisper_interface.transcribe(example_file).get("text").strip())
        )
    assert all(multiple_files[0] == file for file in multiple_files)
