from pathlib import Path

import pytest

from app.local_rag import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DeterministicHashEmbedder,
    DocumentChunk,
    InMemoryVectorStore,
    chunk_markdown,
    ingest_directory,
    retrieve,
)


class FixedEmbedder:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0] if text == "known" else [0.0, 1.0]


def test_ingest_fictional_kb_has_source_metadata_and_is_deterministic():
    root = Path(__file__).resolve().parents[3] / "knowledge-base" / "noavia"
    store = InMemoryVectorStore()
    count = ingest_directory(root, DeterministicHashEmbedder(), store)

    assert count >= 8
    first = chunk_markdown(root / "password-reset.md")[0]
    assert first.id == "knowledge-base/noavia/password-reset.md#0"
    assert first.metadata == {
        "source": "knowledge-base/noavia/password-reset.md",
        "title": "Resetting your NOAVIA password",
        "chunk_index": 0,
    }


def test_retrieval_returns_at_most_top_three_ranked_matches():
    store = InMemoryVectorStore()
    chunks = [DocumentChunk(str(index), f"document {index}", {"source": "fixture"}) for index in range(4)]
    store.upsert(chunks, [[0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.6, 0.4]])

    result = retrieve("known", FixedEmbedder(), store, threshold=0.0)

    assert [match.id for match in result.matches] == ["0", "1", "2"]
    assert result.low_confidence is False
    assert result.fallback is None


def test_low_confidence_returns_no_context_and_manual_review_fallback():
    store = InMemoryVectorStore()
    store.upsert([DocumentChunk("a", "unrelated", {})], [[0.0, 1.0]])

    result = retrieve("known", FixedEmbedder(), store, threshold=DEFAULT_CONFIDENCE_THRESHOLD)

    assert result.matches == []
    assert result.low_confidence is True
    assert result.fallback == "manual_review"


def test_upsert_replaces_a_chunk_and_retrieve_validates_contract():
    store = InMemoryVectorStore()
    chunk = DocumentChunk("same", "first", {})
    store.upsert([chunk], [[1.0, 0.0]])
    store.upsert([DocumentChunk("same", "replacement", {})], [[0.0, 1.0]])

    assert store.search([0.0, 1.0], 3)[0].content == "replacement"
    with pytest.raises(ValueError, match="top_k"):
        retrieve("known", FixedEmbedder(), store, top_k=4)
    with pytest.raises(ValueError, match="blank"):
        retrieve(" ", FixedEmbedder(), store)
