"""Cache module for embedding storage using DuckDB."""

from pathlib import Path

import duckdb
import numpy as np

from frontmatter_mcp.semantic.model import EmbeddingModel

# Cache database filename
CACHE_DB_NAME = "embeddings.duckdb"


class EmbeddingCache:
    """DuckDB-based cache for document embeddings."""

    def __init__(self, cache_dir: Path, model: EmbeddingModel) -> None:
        """Initialize the embedding cache.

        The database connection is lazy-initialized on first access.
        This allows the model to be loaded only when actually needed.

        Args:
            cache_dir: Directory to store the cache database.
            model: Embedding model (used for model name and dimension).
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

    def _connect(self) -> None:
        """Connect to the database and initialize schema."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.cache_path))
        self._init_schema()
        self._check_model_compatibility()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        dim = self._model.get_dimension()

        # Create embeddings table
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS embeddings (
                path TEXT PRIMARY KEY,
                mtime DOUBLE,
                vector FLOAT[{dim}]
            )
        """)

        # Create metadata table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Store model info if not exists
        result = self.conn.execute(
            "SELECT value FROM metadata WHERE key = 'model_name'"
        ).fetchone()
        if result is None:
            self.conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('model_name', ?)",
                [self._model.name],
            )
            self.conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('dimension', ?)",
                [str(dim)],
            )

    def _check_model_compatibility(self) -> None:
        """Check if cached embeddings are compatible with current model."""
        result = self.conn.execute(
            "SELECT value FROM metadata WHERE key = 'model_name'"
        ).fetchone()

        if result is not None and result[0] != self._model.name:
            # Model changed, clear cache
            self.clear()
            # Update metadata
            self.conn.execute(
                "UPDATE metadata SET value = ? WHERE key = 'model_name'",
                [self._model.name],
            )
            self.conn.execute(
                "UPDATE metadata SET value = ? WHERE key = 'dimension'",
                [str(self._model.get_dimension())],
            )

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self.conn.execute("DELETE FROM embeddings")

    def get(self, path: str) -> tuple[float, np.ndarray] | None:
        """Get cached embedding for a path.

        Args:
            path: File path.

        Returns:
            Tuple of (mtime, vector) if cached, None otherwise.
        """
        result = self.conn.execute(
            "SELECT mtime, vector FROM embeddings WHERE path = ?", [path]
        ).fetchone()

        if result is None:
            return None

        return result[0], np.array(result[1])

    def set(self, path: str, mtime: float, vector: np.ndarray) -> None:
        """Store embedding for a path.

        Args:
            path: File path.
            mtime: File modification time.
            vector: Embedding vector.
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO embeddings (path, mtime, vector)
            VALUES (?, ?, ?)
            """,
            [path, mtime, vector.tolist()],
        )

    def delete(self, path: str) -> None:
        """Delete cached embedding for a path.

        Args:
            path: File path.
        """
        self.conn.execute("DELETE FROM embeddings WHERE path = ?", [path])

    def get_all_paths_with_mtime(self) -> dict[str, float]:
        """Get all cached paths with their modification times.

        Returns:
            Dictionary mapping path to mtime.
        """
        results = self.conn.execute("SELECT path, mtime FROM embeddings").fetchall()
        return {row[0]: row[1] for row in results}

    def get_stale_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that need to be re-indexed.

        Args:
            current_files: Dictionary mapping path to current mtime.

        Returns:
            List of paths that are new or have changed.
        """
        cached = self.get_all_paths_with_mtime()
        stale = []

        for path, mtime in current_files.items():
            cached_mtime = cached.get(path)
            if cached_mtime is None or cached_mtime < mtime:
                stale.append(path)

        return stale

    def get_deleted_paths(self, current_files: dict[str, float]) -> list[str]:
        """Get paths that are cached but no longer exist.

        Args:
            current_files: Dictionary mapping path to current mtime.

        Returns:
            List of paths that should be removed from cache.
        """
        cached = self.get_all_paths_with_mtime()
        current_paths = set(current_files.keys())
        return [path for path in cached if path not in current_paths]

    def count(self) -> int:
        """Get the number of cached embeddings.

        Returns:
            Number of cached embeddings.
        """
        result = self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return result[0] if result else 0

    def get_all(self) -> dict[str, np.ndarray]:
        """Get all cached embeddings as a dictionary.

        Returns:
            Dictionary mapping path to embedding vector.
        """
        results = self.conn.execute("SELECT path, vector FROM embeddings").fetchall()
        return {row[0]: np.array(row[1]) for row in results}

    def get_all_readonly(self) -> dict[str, np.ndarray]:
        """Get all cached embeddings using a read-only connection.

        This method opens a separate read-only connection to avoid lock
        conflicts when another process holds the write lock.

        Returns:
            Dictionary mapping path to embedding vector.
            Empty dict if database doesn't exist or is locked.
        """
        if not self.cache_path.exists():
            return {}
        try:
            with duckdb.connect(str(self.cache_path), read_only=True) as conn:
                results = conn.execute("SELECT path, vector FROM embeddings").fetchall()
                return {row[0]: np.array(row[1]) for row in results}
        except (
            duckdb.IOException,
            duckdb.CatalogException,
            duckdb.ConnectionException,
        ):
            # IOException: database is locked by another process
            # CatalogException: embeddings table doesn't exist yet
            # ConnectionException: can't open read-only while write connection exists
            return {}

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
