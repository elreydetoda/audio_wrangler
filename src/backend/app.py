from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Literal, Optional
import uuid, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, status
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, ValueTarget
from streaming_form_data.validators import (
    MaxSizeValidator,
    ValidationError as sfd_ValidationError,
)
from pydantic.dataclasses import dataclass as py_dataclass

# pylint: disable=import-error
from whisper_interface import WhisperInterface

# initially based on this article: https://medium.com/@fatikir15/decoding-speech-privately-a-journey-with-whisper-streamlit-and-fastapi-4ecba1650efb

# https://stackoverflow.com/a/73443824
MAX_FILE_SIZE = 1024 * 1024 * 1024 * 5  # = 5GB
MAX_REQUEST_BODY_SIZE = MAX_FILE_SIZE + 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(whisper_worker())

    # start the app
    yield

    for task in tasks.values():
        if task.path.exists():
            task.path.unlink()


app = FastAPI(lifespan=lifespan)
wsp = WhisperInterface()
## ChatGPT helped with the locking logic
# Task queue and lock
task_queue = asyncio.Queue()
processing_lock = asyncio.Lock()


@py_dataclass
class Task:
    state: (
        Literal["queued"]
        | Literal["processing"]
        | Literal["completed"]
        | Literal["failed"]
    )
    filename: str
    path: Path
    transcription: dict[str, str | list] | None = None
    error: Optional[str] = None


tasks: Dict[str, Task] = {}


class MaxBodySizeException(Exception):
    def __init__(self, body_len: str):
        self.body_len = body_len


class MaxBodySizeValidator:
    def __init__(self, max_size: int):
        self.body_len = 0
        self.max_size = max_size

    def __call__(self, chunk: bytes):
        self.body_len += len(chunk)
        if self.body_len > self.max_size:
            raise MaxBodySizeException(body_len=self.body_len)


async def whisper_manager(task_id: str):
    async with processing_lock:
        current_task = tasks.get(task_id)
        current_task.state = "processing"
        try:
            transcription = await asyncio.to_thread(wsp.transcribe, current_task.path)
            current_task.transcription = transcription
            current_task.state = "completed"
        except Exception as exc:
            current_task.error = {
                "error": f"Error type: {type(exc)}\nError output: {exc}"
            }
            current_task.state = "failed"


async def whisper_worker():
    while True:
        # Waits here until an item is available
        job_id: str = await task_queue.get()
        await whisper_manager(job_id)
        # Signal that the task is complete
        task_queue.task_done()


@app.post("/transcribe")
async def upload(background_tasks: BackgroundTasks, request: Request):
    print("processing")
    body_validator = MaxBodySizeValidator(MAX_REQUEST_BODY_SIZE)
    filename = request.headers.get("Filename")

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename header is missing",
        )
    try:
        filepath = NamedTemporaryFile(delete=False).name
        filez = FileTarget(filepath, validator=MaxSizeValidator(MAX_FILE_SIZE))
        data = ValueTarget()
        parser = StreamingFormDataParser(headers=request.headers)
        parser.register("file", filez)
        parser.register("data", data)

        async for chunk in request.stream():
            body_validator(chunk)
            parser.data_received(chunk)
    except ClientDisconnect:
        print("Client Disconnected")
    except MaxBodySizeException as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Maximum request body size limit ({MAX_REQUEST_BODY_SIZE} bytes) exceeded ({exc.body_len} bytes read)",
        ) from exc
    except sfd_ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Maximum file size limit ({MAX_FILE_SIZE} bytes) exceeded",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was an error uploading the file: {exc}",
        ) from exc

    if not filez.multipart_filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File is missing"
        )

    print(f"Uploaded file: {filez.multipart_filename}")
    print(f"Uploaded to: {filepath}")
    task_id = str(uuid.uuid4())
    tasks[task_id] = Task(state="queued", filename=filename, path=Path(filepath))
    # Add the job to the queue
    await task_queue.put(task_id)

    return {"message": f"Successfuly uploaded {filename}"}


@app.get("/tasks")
async def get_tasks():
    return tasks
