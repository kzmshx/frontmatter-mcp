"""On-disk store of document chunks and their vectors (DuckDB)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from frontmatter_mcp.semantic.chunking import Chunk
from frontmatter_mcp.semantic.models import EmbeddingModel

# Database filename. Kept from the first version: a rebuild deletes the file by
# this name, so renaming it would leave the old file behind
STORE_DB_NAME = "embeddings.duckdb"
# Bump when the tables or what goes into a vector change; the store is rebuilt
SCHEMA_VERSION = "3"

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


class ChunkStore:
    """DuckDB store of indexed files, their chunks, and chunk vectors.

    Tables:
        indexed_files(path, mtime): every indexed file, including ones with no
            chunks
        chunks(path, idx, line, heading, text, vector): one row per chunk
        metadata(key, value): schema version, model, dimension, document prefix
    """

    def __init__(self, cache_dir: Path, model: EmbeddingModel) -> None:
        """Initialize the store.

        The database connection is lazy-initialized on first access.
        This allows the model to be loaded only when actually needed.

        Args:
            cache_dir: Directory for the database file.
            model: Embedding model (used for model name, dimension, and prefix).
        """
        self._cache_dir = cache_dir
        self._model = model
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def path(self) -> Path:
        """Path of the database file."""
        return self._cache_dir / STORE_DB_NAME

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
            "document_prefix": self._model.document_prefix,
        }

    def _remove_files(self) -> None:
        for path in (self.path, Path(f"{self.path}.wal")):
            path.unlink(missing_ok=True)

    def _connect(self) -> None:
        """Connect, starting a fresh file if the cache was made for another setup.

        Deleting the file (rather than dropping tables) matters: DuckDB does not
        shrink a database file, so dropped data would keep taking disk space.
        """
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        expected = self._expected_metadata()
        self._conn = duckdb.connect(str(self.path))
        try:
            stored = dict(
                self._conn.execute("SELECT key, value FROM metadata").fetchall()
            )
        except duckdb.CatalogException:
            stored = {}
        if any(stored.get(k) != v for k, v in expected.items()):
            self._conn.close()
            self._remove_files()
            self._conn = duckdb.connect(str(self.path))
            self._conn.execute(
                "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)"
            )
            self._conn.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                list(expected.items()),
            )
        dim = expected["dimension"]
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS indexed_files "
            "(path TEXT PRIMARY KEY, mtime DOUBLE)"
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

    def replace_files(
        self,
        entries: list[tuple[str, float, list[Chunk], NDArray[np.float32]]],
    ) -> None:
        """Replace the chunks of several files in one transaction.

        Rows go in as one Arrow table rather than row by row, which is an
        order of magnitude faster for vectors.

        Args:
            entries: (path relative to the base directory, mtime, chunks, one
                vector per chunk) for each file.
        """
        if not entries:
            return
        dim = self._model.get_dimension()
        paths, idxs, lines, headings, texts, vecs = [], [], [], [], [], []
        for path, _, chunks, vectors in entries:
            for i, chunk in enumerate(chunks):
                paths.append(path)
                idxs.append(i)
                lines.append(chunk.line)
                headings.append(chunk.heading)
                texts.append(chunk.text)
            if len(chunks):
                vecs.append(np.asarray(vectors[: len(chunks)], dtype=np.float32))
        flat = np.concatenate(vecs).ravel() if vecs else np.zeros(0, np.float32)
        table = pa.table(
            {
                "path": pa.array(paths, pa.string()),
                "idx": pa.array(idxs, pa.int32()),
                "line": pa.array(lines, pa.int32()),
                "heading": pa.array(headings, pa.string()),
                "text": pa.array(texts, pa.string()),
                "vector": pa.FixedSizeListArray.from_arrays(pa.array(flat), dim),
            }
        )
        files = pa.table(
            {
                "path": pa.array([e[0] for e in entries], pa.string()),
                "mtime": pa.array([e[1] for e in entries], pa.float64()),
            }
        )
        conn = self.conn
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.register("new_files", files)
            conn.register("new_chunks", table)
            conn.execute(
                "DELETE FROM chunks WHERE path IN (SELECT path FROM new_files)"
            )
            conn.execute(f"""
                INSERT INTO chunks
                SELECT path, idx, line, heading, text, vector::FLOAT[{dim}]
                FROM new_chunks
            """)
            conn.execute(
                "INSERT OR REPLACE INTO indexed_files SELECT path, mtime FROM new_files"
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.unregister("new_chunks")
            conn.unregister("new_files")

    def delete_file(self, path: str) -> None:
        """Delete a file and its chunks."""
        self.conn.execute("DELETE FROM chunks WHERE path = ?", [path])
        self.conn.execute("DELETE FROM indexed_files WHERE path = ?", [path])

    def indexed_mtimes(self) -> dict[str, float]:
        """Get all indexed paths with their modification times."""
        rows = self.conn.execute("SELECT path, mtime FROM indexed_files").fetchall()
        return {row[0]: row[1] for row in rows}

    def stale_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that are new or changed since they were indexed."""
        cached = self.indexed_mtimes()
        return [
            path for path, mtime in current_files.items() if cached.get(path) != mtime
        ]

    def deleted_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that are indexed but no longer exist."""
        cached = self.indexed_mtimes()
        return [path for path in cached if path not in current_files]

    def load_chunks(self) -> ChunkRows | None:
        """Load every chunk without taking the write lock.

        In the process that is indexing, DuckDB refuses a second (read-only)
        connection to the same file, so a cursor on the open connection is
        used instead; it sees committed rows. Other processes open the file
        read-only.

        Returns:
            All chunks, or None if the cache doesn't exist or can't be read.
        """
        conn = self._conn
        if conn is not None:
            try:
                return self._read_chunks(conn.cursor())
            except duckdb.Error:
                pass  # closed by the indexer meanwhile; open the file instead
        if not self.path.exists():
            return None
        try:
            with duckdb.connect(str(self.path), read_only=True) as ro:
                return self._read_chunks(ro)
        except _READONLY_ERRORS:
            return None

    def _read_chunks(self, conn: duckdb.DuckDBPyConnection) -> ChunkRows:
        relation: Any = conn.sql(
            "SELECT path, line, heading, text, vector FROM chunks ORDER BY path, idx"
        )
        # DuckDB 2 has to_arrow_table; 1.x has arrow()
        to_arrow = getattr(relation, "to_arrow_table", None) or relation.arrow
        table = to_arrow()
        if isinstance(table, pa.RecordBatchReader):
            table = table.read_all()
        dim = self._model.get_dimension()
        # Read the vectors straight into one float32 array; going through Python
        # lists would create a float object per number (hundreds of MB)
        vector_column = table.column("vector").combine_chunks()
        flat = vector_column.flatten().to_numpy(zero_copy_only=False)
        return ChunkRows(
            paths=table.column("path").to_pylist(),
            lines=table.column("line").to_numpy(zero_copy_only=False).astype(np.int64),
            headings=table.column("heading").to_pylist(),
            texts=table.column("text").to_pylist(),
            vectors=np.ascontiguousarray(flat, dtype=np.float32).reshape(-1, dim),
        )

    def compact_if_needed(
        self, growth: float = 1.25, min_growth_bytes: int = 8 * 2**20
    ) -> bool:
        """Rewrite the database file once it has grown well past its compact size.

        Replacing a file's chunks leaves partly used and free blocks behind;
        DuckDB reuses some of them but never shrinks the file. Copying the
        live data into a new file brings it back to its compact size, which is
        remembered for the next check.

        Args:
            growth: Rewrite when the file is larger than this many times the
                size it had right after the last rewrite...
            min_growth_bytes: ...and at least this many bytes larger, so small
                caches are not rewritten over a few blocks.

        Returns:
            True if the file was rewritten.
        """
        self.conn.execute("CHECKPOINT")
        size = self.path.stat().st_size
        row = self.conn.execute(
            "SELECT value FROM metadata WHERE key = 'compact_size'"
        ).fetchone()
        if row is not None:
            base = int(row[0])
            if size <= base * growth or size - base < min_growth_bytes:
                return False

        compact = self.path.with_name(self.path.name + ".compact")
        compact.unlink(missing_ok=True)
        name = self.conn.execute("SELECT current_database()").fetchone()
        assert name is not None
        quoted = str(compact).replace("'", "''")
        self.conn.execute(f"ATTACH '{quoted}' AS compact_target")
        self.conn.execute(f'COPY FROM DATABASE "{name[0]}" TO compact_target')
        self.conn.execute("DETACH compact_target")
        self.close()
        os.replace(compact, self.path)
        Path(f"{self.path}.wal").unlink(missing_ok=True)

        self.conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('compact_size', ?)",
            [str(self.path.stat().st_size)],
        )
        self.conn.execute("CHECKPOINT")
        return True

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
