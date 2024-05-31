import sqlite3

DB_PATH = "index.db"


class IndexingInterface:
    def __init__(self):
        self._conn = sqlite3.connect(DB_PATH)
        self._cursor = self._conn.cursor()
        self._cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS file_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                transcribed BOOLEAN
            )
        """
        )
        self._conn.commit()

    def get_index(self, file_path):
        self._cursor.execute(
            "SELECT * FROM file_index WHERE file_path = ?", (file_path,)
        )
        return self._cursor.fetchone()

    def add_to_index(self, file_path, transcribed):
        self._cursor.execute(
            "INSERT INTO file_index VALUES (?, ?)", (file_path, transcribed)
        )
        self._conn.commit()

    def close(self):
        self._conn.close()

    def open(self, db_path=DB_PATH):
        self._conn = sqlite3.connect(db_path)
        self._cursor = self._conn.cursor()
