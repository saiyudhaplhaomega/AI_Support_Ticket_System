import pytest
from pydantic import ValidationError

from app.schemas import ClassifyTicketInput, ClassifyTicketOutputData, RagLookupInput


def test_classify_input_rejects_blank_text():
    with pytest.raises(ValidationError):
        ClassifyTicketInput(text="   ")


def test_classify_input_accepts_minimal():
    m = ClassifyTicketInput(text="my invoice is wrong")
    assert m.context is None
    assert m.locale is None


def test_classify_output_confidence_bounds():
    base = dict(category="billing", urgency="low", sentiment="neutral", summary="refund question")
    with pytest.raises(ValidationError):
        ClassifyTicketOutputData(**base, confidence=1.5)
    with pytest.raises(ValidationError):
        ClassifyTicketOutputData(**base, confidence=-0.1)
    ok = ClassifyTicketOutputData(**base, confidence=0.9)
    assert ok.confidence == 0.9


def test_rag_input_rejects_blank_query():
    with pytest.raises(ValidationError):
        RagLookupInput(query="")


def test_rag_input_top_k_bounds():
    with pytest.raises(ValidationError):
        RagLookupInput(query="q", top_k=0)
    ok = RagLookupInput(query="q", top_k=10)
    assert ok.top_k == 10
