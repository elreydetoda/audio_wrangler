from pathlib import Path
import whisper
import torch


class WhisperInterface:
    """A class to interact with the whisper library."""

    def __init__(self):
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = whisper.load_model(
            name="medium.en",
            device=self._device,
        )
        # print(self._device)

    def transcribe(self, audio_path: Path):
        """Transcribe an audio file."""
        return whisper.transcribe(
            model=self._model,
            audio=str(audio_path),
            # verbose=True,
        )
