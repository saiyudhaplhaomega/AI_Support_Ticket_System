"""In-memory fakes for the OpenAI and Qdrant async clients, so tests exercise
real route/service/error-handling wiring without hitting the network.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.schemas import _ModelClassification


class FakeChatCompletions:
    def __init__(self, parsed: _ModelClassification | None = None, raise_exc: Exception | None = None):
        self._parsed = parsed
        self._raise = raise_exc

    async def parse(self, **kwargs):
        if self._raise:
            raise self._raise
        message = SimpleNamespace(parsed=self._parsed, refusal=None)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        usage = SimpleNamespace(model_dump=lambda: {"total_tokens": 42})
        return SimpleNamespace(choices=[choice], model="gpt-4o-mini", id="cmpl-test-1", usage=usage)


class FakeEmbeddings:
    def __init__(self, vector: list[float] | None = None, raise_exc: Exception | None = None):
        self._vector = vector or [0.1, 0.2, 0.3]
        self._raise = raise_exc

    async def create(self, **kwargs):
        if self._raise:
            raise self._raise
        input_ = kwargs.get("input")
        n = len(input_) if isinstance(input_, list) else 1
        return SimpleNamespace(data=[SimpleNamespace(embedding=self._vector) for _ in range(n)])


class FakeOpenAI:
    def __init__(
        self,
        parsed: _ModelClassification | None = None,
        vector: list[float] | None = None,
        chat_exc: Exception | None = None,
        embed_exc: Exception | None = None,
    ):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(parsed, chat_exc))
        self.embeddings = FakeEmbeddings(vector, embed_exc)


class FakeQdrant:
    def __init__(
        self,
        points: list | None = None,
        collection_exists: bool = True,
        query_exc: Exception | None = None,
        upsert_exc: Exception | None = None,
    ):
        self._points = points or []
        self._exists = collection_exists
        self._query_exc = query_exc
        self._upsert_exc = upsert_exc
        self.upserted: list[dict] = []

    async def collection_exists(self, name: str) -> bool:
        return self._exists

    async def query_points(self, **kwargs):
        if self._query_exc:
            raise self._query_exc
        return SimpleNamespace(points=self._points)

    async def create_collection(self, **kwargs) -> None:
        self._exists = True

    async def upsert(self, **kwargs) -> None:
        if self._upsert_exc:
            raise self._upsert_exc
        self.upserted.append(kwargs)

    async def get_collections(self):
        return SimpleNamespace(collections=[])

    async def close(self) -> None:
        pass


def fake_point(id_: str, score: float, payload: dict):
    return SimpleNamespace(id=id_, score=score, payload=payload)

class FakeMiniMax:
    """Credential-free MiniMax chat fake for classification/draft tests."""
    def __init__(self, parsed=None, raise_exc=None):
        self._parsed = parsed or {"category": "billing", "urgency": "medium", "sentiment": "negative", "confidence": 0.87, "summary": "Duplicate charge reported."}
        self._raise = raise_exc
        self.calls = []
    async def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise:
            raise self._raise
        return {"parsed": self._parsed, "model": "MiniMax-M3", "id": "minimax-test-1", "usage": {"total_tokens": 42}}
