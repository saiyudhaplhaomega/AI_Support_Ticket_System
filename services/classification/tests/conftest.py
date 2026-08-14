"""Test env — set required secrets *before* app.main is imported anywhere,
since config validation runs at module import time (fail-fast on startup).

Uses direct assignment (not `setdefault`): some ambient shells/CI runners
export `OPENAI_API_KEY=""` as an unset placeholder, and `setdefault` would
leave that empty value in place since the key already exists.
"""
import os

os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY") or "test-openai-key"
os.environ["MINIMAX_API_KEY"] = os.environ.get("MINIMAX_API_KEY") or "test-minimax-key"
os.environ["AI_CLASSIFY_API_KEY"] = os.environ.get("AI_CLASSIFY_API_KEY") or "test-bearer-key"
os.environ["QDRANT_URL"] = os.environ.get("QDRANT_URL") or "http://localhost:6333"
os.environ["AI_QDRANT_API_KEY"] = os.environ.get("AI_QDRANT_API_KEY") or "test-qdrant-token"
