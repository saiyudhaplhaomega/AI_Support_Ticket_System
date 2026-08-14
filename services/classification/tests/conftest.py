"""Test env — set required secrets *before* app.main is imported anywhere,
since config validation runs at module import time (fail-fast on startup).

Always overwrites, never falls back to an ambient value: this suite must be
credential-free and must never let a real key from the calling shell/CI
environment (e.g. a developer's exported OPENAI_API_KEY) reach the app,
appear in a pytest failure traceback, or otherwise leak. Fixed placeholder
values only.
"""
import os

os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["MINIMAX_API_KEY"] = "test-minimax-key"
os.environ["AI_CLASSIFY_API_KEY"] = "test-bearer-key"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["AI_QDRANT_API_KEY"] = "test-qdrant-token"
