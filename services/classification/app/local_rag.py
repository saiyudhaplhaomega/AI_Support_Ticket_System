"""Credential-free deterministic RAG reference implementation.

This module is deliberately independent of OpenAI and Qdrant.  It provides a
repeatable local path for fixture data, contract tests, and new products before
they choose a hosted embedding/vector-store adapter.  Production adapters can
implement :class:`Embedder` and :class:`VectorStore` without changing callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2b
from math import sqrt
from pathlib import Path
import re
from typing import Protocol


DEFAULT_CHUNK_WORDS = 120
DEFAULT_CHUNK_OVERLAP_WORDS = 24
DEFAULT_TOP_K = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.28
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class DocumentChunk:
    """A chunk ready to embed, with stable source metadata for auditability."""

    id: str
    content: str
    metadata: dict[str, str | int]


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    content: str
    metadata: dict[str, str | int]
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    matches: list[RetrievedChunk]
    low_confidence: bool
    fallback: str | None


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None: ...

    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]: ...


class DeterministicHashEmbedder:
    """A local, stable signed-hash embedding; it never needs credentials."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            vector[index] += 1.0 if value & 1 else -1.0
        norm = sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class InMemoryVectorStore:
    """Credential-free upsert/search adapter used by offline ingestion tests."""

    def __init__(self) -> None:
        self._points: dict[str, tuple[DocumentChunk, list[float]]] = {}

    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal lengths")
        for chunk, vector in zip(chunks, vectors):
            self._points[chunk.id] = (chunk, vector)

    def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        scored = [
            RetrievedChunk(chunk.id, chunk.content, chunk.metadata, _cosine(vector, stored_vector))
            for chunk, stored_vector in self._points.values()
        ]
        return sorted(scored, key=lambda item: (-item.score, item.id))[:limit]


def chunk_markdown(path: Path, *, chunk_words: int = DEFAULT_CHUNK_WORDS,
                   overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS) -> list[DocumentChunk]:
    """Split a reviewed Markdown/text source into overlapping word chunks."""
    if chunk_words < 1 or not 0 <= overlap_words < chunk_words:
        raise ValueError("chunk_words must be positive and overlap must be smaller")
    content = path.read_text(encoding="utf-8").strip()
    words = content.split()
    if not words:
        return []
    title = next((line.lstrip("#").strip() for line in content.splitlines() if line.startswith("#")), path.stem)
    source = _source_path(path)
    step = chunk_words - overlap_words
    chunks: list[DocumentChunk] = []
    for index, start in enumerate(range(0, len(words), step)):
        section = words[start:start + chunk_words]
        if not section:
            break
        chunks.append(DocumentChunk(
            id=f"{source}#{index}",
            content=" ".join(section),
            metadata={"source": source, "title": title, "chunk_index": index},
        ))
        if start + chunk_words >= len(words):
            break
    return chunks


def ingest_directory(directory: Path, embedder: Embedder, store: VectorStore) -> int:
    """Read ``.md``/``.txt`` knowledge sources, embed them, and upsert locally."""
    chunks = [chunk for path in sorted(directory.rglob("*")) if path.suffix.lower() in {".md", ".txt"}
              for chunk in chunk_markdown(path)]
    store.upsert(chunks, [embedder.embed(chunk.content) for chunk in chunks])
    return len(chunks)


def retrieve(query: str, embedder: Embedder, store: VectorStore, *, top_k: int = DEFAULT_TOP_K,
             threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> RetrievalResult:
    """Return at most three relevant matches, or the explicit review fallback."""
    if not query.strip():
        raise ValueError("query must not be blank")
    if not 1 <= top_k <= DEFAULT_TOP_K:
        raise ValueError(f"top_k must be between 1 and {DEFAULT_TOP_K}")
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between -1 and 1")
    matches = store.search(embedder.embed(query), top_k)
    if not matches or matches[0].score < threshold:
        return RetrievalResult(matches=[], low_confidence=True, fallback="manual_review")
    return RetrievalResult(matches=matches, low_confidence=False, fallback=None)


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _source_path(path: Path) -> str:
    """Keep source identifiers portable when callers supply an absolute path."""
    parts = path.as_posix().split("/knowledge-base/", maxsplit=1)
    return f"knowledge-base/{parts[1]}" if len(parts) == 2 else path.as_posix()


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions must match")
    return sum(a * b for a, b in zip(left, right))
