from pathlib import Path
from pydantic import field_validator
from sqlmodel import SQLModel, Field


class FilesMetadata(SQLModel, table=True):
    filename: str = Field(primary_key=True, unique=True)
    summary: str | None = None
    processed: bool
