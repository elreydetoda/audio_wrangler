from os import getenv
from pathlib import Path
import sqlite3
from typing import Any, List
from sqlmodel import SQLModel, Session, col, create_engine, select

# pylint: disable=unused-import
from models.db_models import FilesMetadata


class IndexingInterface:
    def __init__(self, conn_str="sqlite:///index.db"):
        debugging = False
        if getenv("PYTEST_VERSION"):
            debugging = True
        self.engine = create_engine(conn_str, echo=debugging)
        SQLModel.metadata.create_all(self.engine)

    @staticmethod
    def _convert_data(data_convert: Any) -> Any:
        if isinstance(data_convert, Path):
            return str(data_convert)
        return data_convert

    def get_index(self, session: Session, file_path):
        file_path = self._convert_data(file_path)
        return session.exec(
            select(FilesMetadata).where(FilesMetadata.filename == file_path)
        ).first()

    def bulk_validate(self, session: Session, file_paths: List[Path]):
        """Check if all files are in the database. If partial match, raise an error."""
        file_paths: List[str] = [
            self._convert_data(file_path) for file_path in file_paths
        ]
        db_results = [
            filez.filename
            for filez in session.exec(
                # pylint: disable=no-member; pylint is not recognizing the table .in_ method https://github.com/tiangolo/sqlmodel/issues/353#issuecomment-1146059605
                select(FilesMetadata).where(col(FilesMetadata.filename).in_(file_paths))
            ).all()
        ]

        if all(filez in db_results for filez in file_paths):
            return True

        # raising error for partial match, and display the files that are not in the db
        not_in_results = list(set(file_paths).difference(db_results))
        raise ValueError(
            f"Not all files are in the database:\n{'\n'.join(not_in_results)}"
        )

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
