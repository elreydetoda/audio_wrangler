from pathlib import Path
import sqlite3
from typing import List
from sqlmodel import SQLModel, Session, col, create_engine, select

# pylint: disable=unused-import
from models.db_models import FilesMetadata


class IndexingInterface:
    def __init__(self, conn_str="sqlite:///index.db"):
        self.engine = create_engine(conn_str, echo=True)
        SQLModel.metadata.create_all(self.engine)

    def _convert_data(self, file_path: Path) -> str:
        if isinstance(file_path, Path):
            return str(file_path)

    def get_index(self, session: Session, file_path):
        file_path = self._convert_data(file_path)
        return session.exec(
            select(FilesMetadata).where(FilesMetadata.filename == file_path)
        ).first()

    def bulk_validate(self, session: Session, file_paths: List[Path]):
        file_paths = [self._convert_data(file_path) for file_path in file_paths]
        db_results = [
            filez.filename
            for filez in session.exec(
                select(FilesMetadata).where(col(FilesMetadata.filename).in_(file_paths))
            ).all()
        ]
        return all(filez in db_results for filez in file_paths)

    def add_to_index(
        self,
        session: Session,
        file_path: Path,
        transcribed: bool,
    ) -> None:
        file_path = self._convert_data(file_path)
        session.add(
            FilesMetadata(
                filename=file_path,
                processed=transcribed,
            )
        )
        session.commit()
