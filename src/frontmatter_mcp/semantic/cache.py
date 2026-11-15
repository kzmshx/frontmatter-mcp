"""Cache module for chunk embeddings using DuckDB."""

from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
from numpy.typing import NDArray

from frontmatter_mcp.semantic.chunking import Chunk
from frontmatter_mcp.semantic.model import EmbeddingModel

# Cache database filename
CACHE_DB_NAME = "embeddings.duckdb"
# Bump when the tables or what goes into a vector change; the cache is rebuilt
SCHEMA_VERSION = "2"

_READONLY_ERRORS = (
    duckdb.IOException,  # database is locked by another process
    duckdb.CatalogException,  # tables don't exist yet
    duckdb.ConnectionException,  # can't open read-only while writing
)


@dataclass
class ChunkRows:
    """All indexed chunks, column by column (row i is one chunk)."""

    paths: list[str]
    lines: NDArray[np.int64]
    headings: list[str]
    texts: list[str]
    vectors: NDArray[np.float32]

    def __len__(self) -> int:
        return len(self.paths)


class EmbeddingCache:
    """DuckDB-based cache for chunk embeddings.

    Tables:
        files(path, mtime): every indexed file, including ones with no chunks
        chunks(path, idx, line, heading, text, vector): one row per chunk
        metadata(key, value): schema version, model, dimension, document prefix
    """

    def __init__(self, cache_dir: Path, model: EmbeddingModel) -> None:
        """Initialize the embedding cache.

        The database connection is lazy-initialized on first access.
        This allows the model to be loaded only when actually needed.

        Args:
            cache_dir: Directory to store the cache database.
            model: Embedding model (used for model name, dimension, and prefix).
        """
        self._cache_dir = cache_dir
        self._model = model
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def cache_path(self) -> Path:
        """Get the path to the cache database."""
        return self._cache_dir / CACHE_DB_NAME

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get the database connection, creating it if necessary."""
        if self._conn is None:
            self._connect()
        assert self._conn is not None
        return self._conn

    def _expected_metadata(self) -> dict[str, str]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_name": self._model.name,
            "dimension": str(self._model.get_dimension()),
            "document_prefix": getattr(self._model, "document_prefix", ""),
        }

    def _connect(self) -> None:
        """Connect, and rebuild the tables if they were made for another setup."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.cache_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        stored = dict(self._conn.execute("SELECT key, value FROM metadata").fetchall())
        expected = self._expected_metadata()
        if stored != expected:
            self._conn.execute("DROP TABLE IF EXISTS embeddings")  # schema v1
            self._conn.execute("DROP TABLE IF EXISTS chunks")
            self._conn.execute("DROP TABLE IF EXISTS files")
            self._conn.execute("DELETE FROM metadata")
            self._conn.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                list(expected.items()),
            )
        dim = expected["dimension"]
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime DOUBLE)"
        )
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                path TEXT,
                idx INTEGER,
                line INTEGER,
                heading TEXT,
                text TEXT,
                vector FLOAT[{dim}]
            )
        """)

    def clear(self) -> None:
        """Clear all cached files and chunks."""
        self.conn.execute("DELETE FROM chunks")
        self.conn.execute("DELETE FROM files")

    def set_file(
        self,
        path: str,
        mtime: float,
        chunks: list[Chunk],
        vectors: NDArray[np.float32],
    ) -> None:
        """Replace the chunks of one file.

        Args:
            path: File path relative to the base directory.
            mtime: File modification time.
            chunks: Chunks of the file (may be empty).
            vectors: One vector per chunk.
        """
        conn = self.conn
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM chunks WHERE path = ?", [path])
            if chunks:
                conn.executemany(
                    "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        [path, i, c.line, c.heading, c.text, vectors[i].tolist()]
                        for i, c in enumerate(chunks)
                    ],
                )
            conn.execute(
                "INSERT OR REPLACE INTO files (path, mtime) VALUES (?, ?)",
                [path, mtime],
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise

    def delete(self, path: str) -> None:
        """Delete a file and its chunks."""
        self.conn.execute("DELETE FROM chunks WHERE path = ?", [path])
        self.conn.execute("DELETE FROM files WHERE path = ?", [path])

    def get_all_paths_with_mtime(self) -> dict[str, float]:
        """Get all indexed paths with their modification times."""
        rows = self.conn.execute("SELECT path, mtime FROM files").fetchall()
        return {row[0]: row[1] for row in rows}

    def get_stale_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that are new or changed since they were indexed."""
        cached = self.get_all_paths_with_mtime()
        return [
            path
            for path, mtime in current_files.items()
            if (cached_mtime := cached.get(path)) is None or cached_mtime < mtime
        ]

    def get_deleted_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that are indexed but no longer exist."""
        cached = self.get_all_paths_with_mtime()
        return [path for path in cached if path not in current_files]

    def count(self) -> int:
        """Get the number of indexed files."""
        result = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()
        return result[0] if result else 0

    def chunk_count(self) -> int:
        """Get the number of indexed chunks."""
        result = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return result[0] if result else 0

    def load_chunks_readonly(self) -> ChunkRows | None:
        """Load every chunk through a read-only connection.

        A separate read-only connection avoids lock conflicts with another
        process that holds the write lock.

        Returns:
            All chunks, or None if the cache doesn't exist or can't be read.
        """
        if not self.cache_path.exists():
            return None
        try:
            with duckdb.connect(str(self.cache_path), read_only=True) as conn:
                rows = conn.execute(
                    "SELECT path, line, heading, text, vector FROM chunks "
                    "ORDER BY path, idx"
                ).fetchall()
        except _READONLY_ERRORS:
            return None
        dim = self._model.get_dimension()
        return ChunkRows(
            paths=[r[0] for r in rows],
            lines=np.array([r[1] for r in rows], dtype=np.int64),
            headings=[r[2] for r in rows],
            texts=[r[3] for r in rows],
            vectors=(
                np.array([r[4] for r in rows], dtype=np.float32)
                if rows
                else np.zeros((0, dim), dtype=np.float32)
            ),
        )

    def get_all_readonly(self) -> dict[str, np.ndarray]:
        """Get one vector per file (the normalized mean of its chunks).

        Backs the `embedding` column of the query tool.

        Returns:
            Dictionary mapping path to vector. Empty if the cache can't be read.
        """
        rows = self.load_chunks_readonly()
        if rows is None or not len(rows):
            return {}
        result: dict[str, np.ndarray] = {}
        paths = np.array(rows.paths)
        for path in dict.fromkeys(rows.paths):
            mean = rows.vectors[paths == path].mean(axis=0)
            norm = float(np.linalg.norm(mean))
            result[path] = mean / norm if norm else mean
        return result

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
